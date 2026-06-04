"""Version registration + fleet inference + figure link-back.

The ``register_version`` flow ties together the env probe, the repo clone, and
the path/semver helpers to write one ``versions/<vN.M>.md`` per attempt. It
reads ``capture_env``, ``_probe_full_pip_freeze``, and ``current_commit_sha``
via the parent package so tests can monkeypatch those on ``experiments``.
"""
from __future__ import annotations

import re
from datetime import datetime
from pathlib import Path
from typing import Literal

import research_assistant.experiments as _exp  # late attribute access for monkeypatchable hooks

from .models import GPUInfo, Machine
from .paths import (
    experiment_path,
    next_version,
    parse_semver,
    repo_clone_path,
    resolve_result_in_repo,
    version_path,
)


# ---------- YAML emission ----------

def _emit_yaml_scalar(v) -> str:
    if v is None:
        return "null"
    if isinstance(v, bool):
        return "true" if v else "false"
    if isinstance(v, (int, float)):
        return str(v)
    text = str(v)
    if not text:
        return '""'
    needs_quote = (
        any(c in text for c in ':#"\'\n\r\t[]{}|>&*!?%`,')
        or text.strip() != text
        or text in ("null", "true", "false", "yes", "no")
        or text[:1] in "@-"
    )
    if needs_quote:
        # Escape backslash + double quote first, then replace control chars
        # with YAML's recognized escape sequences so multi-line values
        # (description / notes / config_snapshot) round-trip through
        # PyYAML's double-quoted scalar without losing the line breaks.
        escaped = (
            text.replace("\\", "\\\\")
            .replace('"', '\\"')
            .replace("\n", "\\n")
            .replace("\r", "\\r")
            .replace("\t", "\\t")
        )
        return f'"{escaped}"'
    return text


def _emit_version_frontmatter(fm: dict) -> str:
    s = _emit_yaml_scalar
    lines = ["---"]

    def emit_scalar_kv(key: str, val) -> None:
        lines.append(f"{key}: {s(val)}")

    def emit_list_inline(key: str, items: list) -> None:
        if not items:
            lines.append(f"{key}: []")
        else:
            lines.append(f"{key}: [{', '.join(s(x) for x in items)}]")

    def emit_scalar_dict(key: str, d: dict) -> None:
        if not d:
            lines.append(f"{key}: {{}}")
            return
        lines.append(f"{key}:")
        for k, v in d.items():
            lines.append(f"  {k}: {s(v)}")

    emit_scalar_kv("version", fm["version"])
    emit_scalar_kv("description", fm["description"])
    lines.append(f"kind: {fm['kind']}")
    lines.append(f"status: {fm['status']}")
    for key in ("commit_sha", "config_snapshot", "result_file", "mirrored_to",
                "started_at", "finished_at"):
        emit_scalar_kv(key, fm.get(key))
    host = fm.get("host") or {}
    if not host or all(v is None for v in host.values()):
        lines.append("host: null")
    else:
        lines.append("host:")
        for hk in ("hostname", "os", "arch"):
            lines.append(f"  {hk}: {s(host.get(hk))}")
    gpu = fm.get("gpu") or []
    if not gpu:
        lines.append("gpu: []")
    else:
        lines.append("gpu:")
        for g in gpu:
            lines.append(f"  - name: {s(g.get('name'))}")
            lines.append(f"    count: {s(g.get('count', 1))}")
            if g.get("driver"):
                lines.append(f"    driver: {s(g['driver'])}")
    emit_scalar_kv("cuda", fm.get("cuda"))
    emit_scalar_kv("python", fm.get("python"))
    emit_scalar_dict("libraries", fm.get("libraries") or {})
    emit_scalar_kv("libraries_lockfile", fm.get("libraries_lockfile"))
    emit_list_inline("seeds", fm.get("seeds") or [])
    emit_scalar_dict("metrics", fm.get("metrics") or {})
    emit_list_inline("artifacts", fm.get("artifacts") or [])
    emit_scalar_kv("notes", fm.get("notes") or "")
    lines.append("---")
    return "\n".join(lines) + "\n"


# ---------- version registration ----------

def register_version(
    slug: str,
    version: str,
    description: str,
    *,
    kind: Literal["major", "minor"] = "minor",
    status: Literal["planned", "running", "completed", "failed", "abandoned"] = "completed",
    config: str | None = None,
    result_in_repo: str | None = None,
    seeds: list[int] | None = None,
    metrics: dict[str, float] | None = None,
    notes: str = "",
    started_at: str | None = None,
    finished_at: str | None = None,
    force: bool = False,
) -> Path:
    """Compose and write ``versions/<vN.M>.md`` for ``slug``.

    Refuses to overwrite an existing file unless ``force=True`` — surfaces the
    suggested next version in the exception message. ``next_version`` is the
    canonical suggestion source; this function accepts any well-formed
    ``vN.M`` so callers can deliberately skip numbers (e.g. ``v1.3`` -> ``v3.0``).

    ``status`` records the run outcome (default ``"completed"``); pass
    ``"failed"`` / ``"abandoned"`` / ``"running"`` / ``"planned"`` to register a
    non-successful or in-flight run without hand-editing the version file.

    ``started_at`` / ``finished_at`` are ISO-8601 strings the caller may pass
    when the run-time is known (e.g. CI captures both). When ``finished_at``
    is omitted the registration moment is used as a best-effort proxy — the
    ``Version`` model exposes both fields as ``datetime | None`` and a
    silently-None ``finished_at`` reads as "no timing data was ever known".
    """
    parse_semver(version)
    if kind not in ("major", "minor"):
        raise ValueError(f"unknown version kind: {kind!r}")
    _allowed_status = ("planned", "running", "completed", "failed", "abandoned")
    if status not in _allowed_status:
        raise ValueError(f"unknown version status: {status!r}")
    out_path = version_path(slug, version)
    if out_path.exists() and not force:
        suggestion = next_version(slug, "minor")
        raise FileExistsError(
            f"version {version} already exists for {slug}; "
            f"suggested next: {suggestion} (or pass force=True)"
        )
    out_path.parent.mkdir(parents=True, exist_ok=True)

    env = _exp.capture_env()
    commit_sha = _exp.current_commit_sha(slug)
    mirrored: Path | None = None
    if result_in_repo:
        src = resolve_result_in_repo(slug, result_in_repo)
        mirrored = _exp.mirror_results(
            slug, version, src,
            boundary_root=repo_clone_path(slug),
            force=force,
        )

    freeze = _exp._probe_full_pip_freeze()
    lockfile_rel: str | None = None
    if freeze:
        configs_dir = experiment_path(slug) / "configs"
        configs_dir.mkdir(parents=True, exist_ok=True)
        lock = configs_dir / f"{version}.requirements.txt"
        lock.write_text(freeze, encoding="utf-8")
        lockfile_rel = str(lock.relative_to(experiment_path(slug)))

    fm: dict = {
        "version": version,
        "description": description,
        "kind": kind,
        "status": status,
        "commit_sha": commit_sha,
        "config_snapshot": config,
        "result_file": result_in_repo,
        "mirrored_to": (
            str(mirrored.relative_to(experiment_path(slug))) if mirrored else None
        ),
        "started_at": started_at,
        "finished_at": finished_at or datetime.now().astimezone().isoformat(timespec="seconds"),
        "host": {
            "hostname": env.get("hostname"),
            "os": env.get("os"),
            "arch": env.get("arch"),
        },
        "gpu": env.get("gpu", []),
        "cuda": env.get("cuda"),
        "python": env.get("python"),
        "libraries": env.get("libraries", {}),
        "libraries_lockfile": lockfile_rel,
        "seeds": seeds or [],
        "metrics": metrics or {},
        "artifacts": [],
        "notes": notes,
    }
    body = _emit_version_frontmatter(fm) + (
        f"\n# {version} — {description}\n\n"
        "## Setup\n\n"
        "<exact commands / deviations from the config>\n\n"
        "## Observations\n\n"
        "<what worked, what surprised>\n\n"
        "## Diff vs prior version\n\n"
        "<for v1.1+ — what changed, why>\n"
    )
    out_path.write_text(body, encoding="utf-8")
    return out_path


# ---------- fleet inference ----------

def _heuristic_extract_host_and_gpus(text: str) -> tuple[str | None, list[GPUInfo]]:
    """Walk YAML frontmatter looking for ``host:`` + ``gpu:`` blocks.

    Same heuristic-grade approach :func:`stage_status` uses for ``url:`` and
    ``papers:`` — robust to the frontmatter shape :func:`register_version`
    writes today, may miss hand-edited files with unusual indentation.

    A frontmatter that opens with ``---`` but yields neither hostname nor any
    GPU rows is logged via :mod:`warnings` (``UserWarning``) so the
    ``/experiment feasibility`` interactive fallback knows there was data the
    heuristic skipped, rather than data the user genuinely omitted.
    """
    import warnings

    lines = text.splitlines()
    if not lines or lines[0].strip() != "---":
        return None, []
    hostname: str | None = None
    gpus: list[GPUInfo] = []
    section: str | None = None
    current_gpu: dict | None = None
    for line in lines[1:]:
        if line.strip() == "---":
            break
        if not line[:1].isspace():
            # Leaving the current section. If we accumulated a GPU but the
            # ``gpu:`` block ended with no trailing ``- name:`` to flush it,
            # append before resetting — otherwise the last GPU silently drops.
            if current_gpu:
                gpus.append(GPUInfo(**current_gpu))
            section = None
            current_gpu = None
            stripped = line.rstrip()
            if stripped.startswith("host:") and stripped.strip() != "host: null":
                # Support TWO shapes:
                #   1. flat string — ``host: <hostname>``  (hand-written
                #      version files use this)
                #   2. nested mapping — ``host:`` then indented
                #      ``  hostname: <name>``  (register_version writer)
                inline = stripped[len("host:"):].strip().strip('"').strip("'")
                if inline:
                    hostname = inline
                else:
                    section = "host"
            elif stripped == "gpu:":
                section = "gpu"
            continue
        content = line.strip()
        if section == "host" and content.startswith("hostname:"):
            val = content.split(":", 1)[1].strip().strip('"').strip("'")
            if val and val != "null":
                hostname = val
        elif section == "gpu":
            if content.startswith("- name:"):
                if current_gpu:
                    gpus.append(GPUInfo(**current_gpu))
                name_val = content.split(":", 1)[1].strip().strip('"').strip("'")
                current_gpu = {"name": name_val, "count": 1}
            elif current_gpu is not None:
                if content.startswith("count:"):
                    try:
                        current_gpu["count"] = int(content.split(":", 1)[1].strip())
                    except ValueError:
                        pass
                elif content.startswith("driver:"):
                    val = content.split(":", 1)[1].strip().strip('"').strip("'")
                    if val and val != "null":
                        current_gpu["driver"] = val
    if current_gpu:
        gpus.append(GPUInfo(**current_gpu))
    if hostname is None and not gpus and any(
        line.lstrip().startswith(("host:", "gpu:")) for line in lines[1:]
    ):
        warnings.warn(
            "fleet frontmatter had host:/gpu: keys but the heuristic extracted "
            "nothing — check indentation; "
            "/experiment feasibility will fall back to interactive capture.",
            UserWarning,
            stacklevel=2,
        )
    return hostname, gpus


def refresh_experiments_index() -> int:
    """Rewrite ``outputs/experiments/_index.md`` from each experiment's
    ``manifest.md``. Returns the number of experiments listed.

    The table columns match the empty header on disk:
    ``| Slug | Status | Created | Clone | Papers |``. Experiments with
    malformed manifests are skipped (the parser already swallows them).

    The SKILL's "Refresh ``_index.md``" instruction in Stages 1 / 3.5 / 5
    delegates to this helper so every experiment-mutating verb leaves the
    index in sync. Previously the instruction had no Python implementation;
    the file lived as an empty header.
    """
    from .parsers import parse_experiment

    if not _exp.EXPERIMENTS_DIR.is_dir():
        return 0
    rows: list[tuple[str, str, str, str, str]] = []
    for manifest in sorted(_exp.list_experiments()):
        try:
            exp = parse_experiment(manifest)
        except Exception:  # noqa: BLE001 — match list_experiments' lax contract
            continue
        clone = exp.repo.clone_status if exp.repo else "—"
        papers = ", ".join(exp.papers) if exp.papers else "—"
        rows.append((exp.slug, exp.status, exp.created_at.isoformat(), clone, papers))

    lines = [
        "# Experiments vault",
        "",
        "| Slug | Status | Created | Clone | Papers |",
        "|---|---|---|---|---|",
    ]
    for slug, status, created, clone, papers in rows:
        lines.append(f"| {slug} | {status} | {created} | {clone} | {papers} |")
    lines.append("")  # trailing newline

    index_path = _exp.EXPERIMENTS_DIR / "_index.md"
    index_path.parent.mkdir(parents=True, exist_ok=True)
    index_path.write_text("\n".join(lines), encoding="utf-8")
    return len(rows)


def infer_fleet_from_versions() -> list[Machine]:
    """Walk every experiment's ``versions/*.md`` files, extract host + GPU info,
    dedupe by hostname. Returned machines are sorted by hostname.

    Used by ``/experiment feasibility`` to bootstrap the fleet view from past
    runs. The interactive fallback in the skill body handles machines the user
    has but hasn't run anything on yet, persisting to ``inputs/fleet.md``.
    """
    if not _exp.EXPERIMENTS_DIR.is_dir():
        return []
    by_host: dict[str, Machine] = {}
    for version_file in _exp.EXPERIMENTS_DIR.glob("*/versions/*.md"):
        try:
            text = version_file.read_text(errors="replace")
        except OSError:
            continue
        hostname, gpus = _heuristic_extract_host_and_gpus(text)
        if not hostname:
            continue
        if hostname in by_host:
            existing = by_host[hostname]
            existing_names = {g.name for g in existing.gpus}
            for g in gpus:
                if g.name not in existing_names:
                    existing.gpus.append(g)
                    existing_names.add(g.name)
        else:
            by_host[hostname] = Machine(hostname=hostname, gpus=gpus)
    return sorted(by_host.values(), key=lambda m: m.hostname)


# ---------- figure link-back ----------

def append_figures_to_version(
    *, slug: str, version: str, figure_stems: list[str]
) -> Path:
    """Append `figures:` list to versions/<version>.md frontmatter. Idempotent.

    figure_stems are repo-relative path stems WITHOUT extension (consumers
    append `.pdf` / `.svg` / `.png` as needed). Mirrors the spec's 8.2
    "experiment version add link-back".
    """
    import yaml
    # Go through the canonical version_path resolver — it validates the
    # semver and enforces the `_guard_under` traversal guard every other
    # path helper uses (previously this function rebuilt the path inline
    # and skipped both checks).
    from .paths import version_path
    version_path_ = version_path(slug, version)
    if not version_path_.exists():
        raise FileNotFoundError(version_path_)
    text = version_path_.read_text(encoding="utf-8")
    fm_match = re.match(r"^---\r?\n(.*?)\r?\n---\r?\n?(.*)$", text, re.DOTALL)
    if not fm_match:
        raise ValueError(f"{version_path_} has no YAML frontmatter")
    fm = yaml.safe_load(fm_match.group(1)) or {}
    body = fm_match.group(2)
    existing = fm.get("figures") or []
    merged = list(dict.fromkeys([*existing, *figure_stems]))   # dedupe, preserve order
    fm["figures"] = merged
    new_yaml = yaml.safe_dump(fm, sort_keys=False, allow_unicode=True).rstrip("\n")
    version_path_.write_text(f"---\n{new_yaml}\n---\n{body}", encoding="utf-8")
    return version_path_
