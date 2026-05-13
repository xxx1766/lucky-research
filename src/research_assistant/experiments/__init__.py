"""Experiment-runner helpers — schema + I/O + repo-state + env capture.

Each experiment lives at ``outputs/experiments/<slug>/`` (gitignored). The bound
GitHub repo is the cross-machine truth for code/data; this module is the control
center that tracks repo state, records versioned execution attempts (semver),
and mirrors structured result files so downstream features (e.g. ``/paper``)
can consume them offline.

Mirrors three patterns already in the codebase:

* ``research_assistant.papers`` for stage status + progress rendering.
* ``research_assistant.mentor.boss_profile`` for collision-suffix paths and
  path-traversal guards.
* ``research_assistant.mentor.past_work`` for Pydantic models + the
  frontmatter-parser defer pattern.

Slug convention matches :func:`research_assistant.mentor.past_work.slugify` —
kebab-case English, non-alphanumerics collapsed to hyphens.
"""
from __future__ import annotations

import platform
import re
import shutil
import socket
import subprocess
import sys
from dataclasses import dataclass
from datetime import date, datetime
from pathlib import Path
from typing import Literal

from pydantic import BaseModel, Field

from research_assistant.common.io import EXPERIMENTS_DIR, FLEET_INPUT_PATH

_SLUG_CLEAN = re.compile(r"[^a-z0-9]+")
_SEMVER_RE = re.compile(r"^v(\d+)\.(\d+)$")
_DESIGN_SEMVER_RE = re.compile(r"^d(\d+)\.(\d+)$")
_FEASIBILITY_RE = re.compile(r"^feasibility-(\d{4}-\d{2}-\d{2})(?:-(\d+))?\.md$")

_BAR_WIDTH = 5
_STAGES: tuple[str, ...] = ("init", "scout", "design", "version", "analyze")

_GIT_TIMEOUT_S = 15
_CLONE_TIMEOUT_S = 120
_ENV_PROBE_TIMEOUT_S = 5
_LARGE_RESULT_BYTES = 100 * 1024 * 1024  # 100 MB

_TRACKED_LIBS: tuple[str, ...] = (
    "torch", "transformers", "peft", "datasets", "accelerate",
    "deepspeed", "numpy", "scipy", "scikit-learn", "pandas",
)


# ---------- slug + path helpers ----------

def slugify_experiment(title: str) -> str:
    """Build a kebab-case slug from a free-form title. Raise on empty."""
    cleaned = _SLUG_CLEAN.sub("-", title.lower()).strip("-")
    if not cleaned:
        raise ValueError(f"empty experiment slug for title={title!r}")
    return cleaned


def next_available_slug(base: str) -> str:
    """Collision-safe variant. ``base`` -> ``base``, ``base-2``, ``base-3`` ...

    Mirrors :func:`research_assistant.mentor.boss_profile.rehearsal_path`.
    """
    if not base:
        raise ValueError("empty base slug")
    if not (EXPERIMENTS_DIR / base).exists():
        return base
    n = 2
    while (EXPERIMENTS_DIR / f"{base}-{n}").exists():
        n += 1
    return f"{base}-{n}"


def _guard_under(root: Path, candidate: Path, what: str) -> Path:
    """Raise ``ValueError`` if ``candidate`` resolves outside ``root``."""
    rr = root.resolve()
    cc = candidate.resolve()
    if rr != cc and rr not in cc.parents:
        raise ValueError(f"{what} escapes {root.name}: {candidate}")
    return cc


def experiment_path(slug: str) -> Path:
    """Resolve ``outputs/experiments/<slug>/``. Path-traversal guarded."""
    if not slug:
        raise ValueError("empty experiment slug")
    return _guard_under(EXPERIMENTS_DIR, EXPERIMENTS_DIR / slug, "experiment slug")


def manifest_path(slug: str) -> Path:
    return experiment_path(slug) / "manifest.md"


def legacy_design_path(slug: str) -> Path:
    """Pre-refactor singleton ``design.md`` location.

    Kept as a defensive fallback for :func:`stage_status` — the canonical
    path now lives at :func:`latest_design_path` (under ``designs/d<N.M>.md``).
    """
    return experiment_path(slug) / "design.md"


def references_path(slug: str) -> Path:
    return experiment_path(slug) / "references.md"


def status_path(slug: str) -> Path:
    return experiment_path(slug) / "status.md"


def data_index_path(slug: str) -> Path:
    return experiment_path(slug) / "data" / "index.md"


def repo_clone_path(slug: str) -> Path:
    return experiment_path(slug) / "repo"


def version_path(slug: str, version: str) -> Path:
    """Resolve ``versions/<vN.M>.md`` under an experiment. Both args validated."""
    parse_semver(version)  # rejects malformed / traversal-tainted args
    exp = experiment_path(slug)
    return _guard_under(exp, exp / "versions" / f"{version}.md", "version slug")


def result_path(slug: str, version: str) -> Path:
    """Resolve ``results/<vN.M>/`` under an experiment. Both args validated."""
    parse_semver(version)
    exp = experiment_path(slug)
    return _guard_under(exp, exp / "results" / version, "version slug")


def resolve_result_in_repo(slug: str, repo_rel_path: str) -> Path:
    """Resolve a repo-relative result path to an absolute Path under the clone.

    Raises ``ValueError`` on empty/traversal. Used by ``register_version`` to
    locate the source file before mirroring.
    """
    if not repo_rel_path:
        raise ValueError("empty result path")
    repo = repo_clone_path(slug)
    return _guard_under(repo, repo / repo_rel_path, "result path")


def design_version_path(slug: str, version: str) -> Path:
    """Resolve ``designs/<dN.M>.md`` under an experiment. Both args validated.

    The design plan is versioned in parallel with run versions (``versions/v<N.M>``);
    ``/experiment feasibility apply`` writes a new design version after the user
    adopts suggestions from a feasibility report.
    """
    parse_semver(version, prefix="d")
    exp = experiment_path(slug)
    return _guard_under(exp, exp / "designs" / f"{version}.md", "design version")


def latest_design_path(slug: str) -> Path | None:
    """Return the path of the highest-semver design file, or ``None`` if absent."""
    v = latest_design(slug)
    return design_version_path(slug, v) if v else None


def fleet_input_path() -> Path:
    """``inputs/fleet.md`` — user-maintained machine-inventory manifest.

    Read by ``/experiment feasibility`` and merged with hosts auto-derived from
    ``versions/*.md`` frontmatter. When the user volunteers fleet info during a
    feasibility check, the skill body writes it here immediately so the next
    check doesn't re-ask.
    """
    return FLEET_INPUT_PATH


def feasibility_path(slug: str, d: date | None = None) -> Path:
    """Collision-safe path to a feasibility report.

    Mirrors :func:`research_assistant.mentor.boss_profile.rehearsal_path`: same
    date produces ``feasibility-<date>.md``, ``feasibility-<date>-2.md``,
    ``feasibility-<date>-3.md``, ...
    """
    if d is None:
        d = date.today()
    exp_dir = experiment_path(slug)
    base = f"feasibility-{d.isoformat()}"
    candidate = exp_dir / f"{base}.md"
    if not candidate.exists():
        return candidate
    n = 2
    while True:
        nth = exp_dir / f"{base}-{n}.md"
        if not nth.exists():
            return nth
        n += 1


def _parse_feasibility_filename(name: str) -> tuple[date, int] | None:
    """Parse ``feasibility-<YYYY-MM-DD>[-<n>].md`` into ``(date, suffix)``.

    Returns ``None`` if the name doesn't match. Lexical sort on
    ``feasibility-<date>.md`` filenames is unreliable (``"."`` > ``"-"`` in
    ASCII puts the unsuffixed file AFTER the ``-2`` suffix in lex order),
    so :func:`latest_feasibility` sorts on this tuple instead.
    """
    m = _FEASIBILITY_RE.match(name)
    if not m:
        return None
    try:
        d = date.fromisoformat(m.group(1))
    except ValueError:
        return None
    suffix = int(m.group(2)) if m.group(2) else 1
    return (d, suffix)


def latest_feasibility(slug: str) -> Path | None:
    """Return the newest feasibility report for ``slug`` (date + suffix order)."""
    exp_dir = experiment_path(slug)
    if not exp_dir.is_dir():
        return None
    parsed: list[tuple[tuple[date, int], Path]] = []
    for p in exp_dir.glob("feasibility-*.md"):
        info = _parse_feasibility_filename(p.name)
        if info:
            parsed.append((info, p))
    if not parsed:
        return None
    parsed.sort()
    return parsed[-1][1]


# ---------- semver ----------

def _semver_regex(prefix: str) -> re.Pattern[str]:
    if prefix == "v":
        return _SEMVER_RE
    if prefix == "d":
        return _DESIGN_SEMVER_RE
    raise ValueError(f"unsupported semver prefix: {prefix!r}")


def parse_semver(s: str, prefix: str = "v") -> tuple[int, int]:
    """``'v1.2'`` -> ``(1, 2)``. Raise on malformed.

    ``prefix`` controls the expected version prefix; pass ``"d"`` for the
    parallel design-plan semver (``d1.0``, ``d1.1`` ...).
    """
    m = _semver_regex(prefix).match(s) if isinstance(s, str) else None
    if not m:
        raise ValueError(f"malformed semver: {s!r}")
    return int(m.group(1)), int(m.group(2))


def format_semver(major: int, minor: int, prefix: str = "v") -> str:
    return f"{prefix}{major}.{minor}"


def bump_major(v: str, prefix: str = "v") -> str:
    major, _ = parse_semver(v, prefix=prefix)
    return format_semver(major + 1, 0, prefix=prefix)


def bump_minor(v: str, prefix: str = "v") -> str:
    major, minor = parse_semver(v, prefix=prefix)
    return format_semver(major, minor + 1, prefix=prefix)


def _list_semver_files(dir_path: Path, prefix: str) -> list[str]:
    """Read ``*.md`` files under ``dir_path``, filter to well-formed semver
    stems for ``prefix``, return sorted numerically by (major, minor).
    """
    if not dir_path.is_dir():
        return []
    out: list[str] = []
    for p in dir_path.glob("*.md"):
        try:
            parse_semver(p.stem, prefix=prefix)
        except ValueError:
            continue
        out.append(p.stem)
    out.sort(key=lambda s: parse_semver(s, prefix=prefix))
    return out


def list_versions(slug: str) -> list[str]:
    """Read ``versions/*.md``, return semver-sorted slugs (numeric, not lexical)."""
    return _list_semver_files(experiment_path(slug) / "versions", "v")


def list_designs(slug: str) -> list[str]:
    """Read ``designs/*.md``, return semver-sorted slugs (numeric).

    Mirror of :func:`list_versions` for design-plan semver (``d1.0`` ...).
    """
    return _list_semver_files(experiment_path(slug) / "designs", "d")


def latest_version(slug: str) -> str | None:
    vs = list_versions(slug)
    return vs[-1] if vs else None


def latest_design(slug: str) -> str | None:
    ds = list_designs(slug)
    return ds[-1] if ds else None


def _next_in_series(vs: list[str], kind: str, prefix: str) -> str:
    """Suggest the next semver from a sorted list. Empty -> ``<prefix>1.0``."""
    if kind not in ("major", "minor"):
        raise ValueError(f"unknown bump kind: {kind!r}")
    if not vs:
        return format_semver(1, 0, prefix=prefix)
    if kind == "major":
        return bump_major(vs[-1], prefix=prefix)
    highest_major = parse_semver(vs[-1], prefix=prefix)[0]
    candidates = [v for v in vs if parse_semver(v, prefix=prefix)[0] == highest_major]
    return bump_minor(candidates[-1], prefix=prefix)


def next_version(slug: str, kind: Literal["major", "minor"]) -> str:
    """Suggest the next run-semver. ``'major'`` bumps the highest major; ``'minor'``
    bumps the highest minor under the current highest major. Empty -> ``v1.0``.

    Suggestion only — callers are free to register a non-monotonic explicit
    version (e.g. skip from ``v1.3`` to ``v3.0``).
    """
    return _next_in_series(list_versions(slug), kind, "v")


def next_design_version(slug: str, kind: Literal["major", "minor"]) -> str:
    """Suggest the next design-plan semver. Mirror of :func:`next_version`."""
    return _next_in_series(list_designs(slug), kind, "d")


# ---------- models ----------

class ExperimentRepo(BaseModel):
    url: str
    branch: str = "main"
    last_known_sha: str | None = None
    clone_status: Literal["tracked", "cloned", "missing"] = "tracked"


class Experiment(BaseModel):
    slug: str
    title: str
    created_at: date
    repo: ExperimentRepo
    papers: list[str] = Field(default_factory=list)
    status: Literal["active", "paused", "archived", "abandoned"] = "active"
    tags: list[str] = Field(default_factory=list)
    body: str = ""


class HostInfo(BaseModel):
    hostname: str
    os: str
    arch: str


class GPUInfo(BaseModel):
    name: str
    count: int = 1
    driver: str | None = None


class Version(BaseModel):
    version: str
    description: str
    kind: Literal["major", "minor"] = "minor"
    status: Literal["planned", "running", "completed", "failed", "abandoned"] = "completed"
    commit_sha: str | None = None
    config_snapshot: str | None = None
    result_file: str | None = None
    mirrored_to: str | None = None
    started_at: datetime | None = None
    finished_at: datetime | None = None
    host: HostInfo | None = None
    gpu: list[GPUInfo] = Field(default_factory=list)
    cuda: str | None = None
    python: str | None = None
    libraries: dict[str, str] = Field(default_factory=dict)
    libraries_lockfile: str | None = None
    seeds: list[int] = Field(default_factory=list)
    metrics: dict[str, float] = Field(default_factory=dict)
    artifacts: list[str] = Field(default_factory=list)
    notes: str = ""
    body: str = ""


class DataArtifact(BaseModel):
    slug: str
    category: Literal["trace", "dataset", "checkpoint", "log", "plot", "other"]
    size: str | None = None
    sha256: str | None = None
    produced_by: str | None = None
    produced_on: str | None = None
    path: str
    description: str = ""


class Machine(BaseModel):
    """One host in the user's fleet. Used by ``/experiment feasibility``."""
    hostname: str
    gpus: list[GPUInfo] = Field(default_factory=list)
    cpu_cores: int | None = None
    ram_gb: float | None = None
    disk_gb: float | None = None
    network: str | None = None
    available: bool = True
    notes: str = ""


class FleetSnapshot(BaseModel):
    """Snapshot of the user's available machines at a point in time."""
    as_of: date
    machines: list[Machine] = Field(default_factory=list)
    body: str = ""


class FeasibilitySuggestion(BaseModel):
    """One purpose-preserving modification to fit the experiment to the fleet."""
    id: int
    axis: Literal[
        "model-size", "baseline-pruning", "batching", "sharding",
        "dataset-subset", "sequential", "lighter-eval", "mixed-precision",
        "gradient-checkpointing", "other",
    ]
    change: str
    rationale: str
    cost: str = ""


class FeasibilityReport(BaseModel):
    """The structured output of ``/experiment feasibility``.

    Frontmatter of ``feasibility-<date>.md`` files round-trips through this model.
    ``/experiment feasibility apply`` reads ``suggestions`` to drive design
    revisions.
    """
    slug: str
    date: date
    design_version: str                       # 'd1.0'
    verdict: Literal["feasible", "tight", "infeasible"]
    fleet_used: list[str] = Field(default_factory=list)
    blockers: list[str] = Field(default_factory=list)
    suggestions: list[FeasibilitySuggestion] = Field(default_factory=list)
    body: str = ""


# ---------- stage status + progress rendering ----------

@dataclass(frozen=True)
class ExperimentStatus:
    has_manifest: bool
    has_repo: bool
    has_papers_bound: bool
    has_references: bool
    has_design: bool
    has_clone: bool
    version_count: int
    last_version: str | None
    last_sync: datetime | None
    last_feasibility_check: datetime | None


def stage_status(slug: str) -> ExperimentStatus:
    """Inspect ``<slug>/`` on disk; tolerate every file/dir missing.

    Uses cheap text heuristics (``"url:"``, ``"papers:"``) rather than YAML
    parsing, matching the deferred-frontmatter-parser policy elsewhere.
    """
    exp_dir = experiment_path(slug)
    manifest = manifest_path(slug)
    has_manifest = manifest.is_file()
    has_repo = False
    has_papers_bound = False
    last_sync: datetime | None = None
    if has_manifest:
        text = manifest.read_text(errors="replace")
        has_repo = "url:" in text
        # papers: followed by at least one "  - " bullet inside a YAML block
        if "papers:" in text:
            tail = text.split("papers:", 1)[1].splitlines()[1:6]
            has_papers_bound = any(line.strip().startswith("- ") for line in tail)
        last_sync = datetime.fromtimestamp(manifest.stat().st_mtime)
    references = references_path(slug)
    has_references = references.is_file() and references.stat().st_size > 0
    # has_design: any file in designs/<dN.M>.md, or the legacy singleton.
    has_design = bool(list_designs(slug)) or legacy_design_path(slug).is_file()
    has_clone = repo_clone_path(slug).is_dir()
    versions = list_versions(slug) if exp_dir.is_dir() else []
    last_feasibility_check: datetime | None = None
    if exp_dir.is_dir():
        lf = latest_feasibility(slug)
        if lf and lf.is_file():
            last_feasibility_check = datetime.fromtimestamp(lf.stat().st_mtime)
    return ExperimentStatus(
        has_manifest=has_manifest,
        has_repo=has_repo,
        has_papers_bound=has_papers_bound,
        has_references=has_references,
        has_design=has_design,
        has_clone=has_clone,
        version_count=len(versions),
        last_version=versions[-1] if versions else None,
        last_sync=last_sync,
        last_feasibility_check=last_feasibility_check,
    )


def _stage_done(stage: str, s: ExperimentStatus) -> bool:
    if stage == "init":
        return s.has_manifest and s.has_repo
    if stage == "scout":
        # Scout is conditional: if no papers bound, it auto-completes (no work
        # to do). Stay "not done" before the manifest exists — we can't know
        # yet whether papers will be bound.
        if not s.has_manifest:
            return False
        return (not s.has_papers_bound) or s.has_references
    if stage == "design":
        return s.has_design
    if stage == "version":
        return s.version_count > 0
    if stage == "analyze":
        return s.version_count >= 2
    raise ValueError(f"unknown stage: {stage}")


def _stage_partial(stage: str, s: ExperimentStatus) -> bool:
    if _stage_done(stage, s):
        return False
    if stage == "init":
        return s.has_manifest
    return False


def next_suggested(s: ExperimentStatus) -> str:
    if not s.has_manifest:
        return "/experiment init <title>"
    if not s.has_repo:
        return "/experiment init  (re-run; provide --repo)"
    if s.has_papers_bound and not s.has_references:
        return "/experiment scout"
    if not s.has_design:
        return "/experiment design"
    # Once design exists, pre-flight the fleet before the first run.
    if s.last_feasibility_check is None and s.version_count == 0:
        return "/experiment feasibility"
    if s.version_count == 0:
        return '/experiment version add v1.0 --description "..."'
    if s.version_count < 2:
        return "/experiment version add  (or /experiment analyze)"
    return "/experiment analyze"


def _progress_bar(s: ExperimentStatus) -> tuple[str, int]:
    done = sum(1 for st in _STAGES if _stage_done(st, s))
    return "#" * done + "-" * (_BAR_WIDTH - done), done


def render_progress_footer(slug: str | None, status: ExperimentStatus | None) -> str:
    """One-line footer printed at the end of every ``/experiment`` subcommand."""
    if not slug:
        return "── no current experiment · next: /experiment init <title> ──"
    if status is None:
        return f"── {slug} · next: /experiment init  (re-run) ──"
    bar, done = _progress_bar(status)
    return (
        f"── {slug}   [{bar}] {done}/{_BAR_WIDTH}   "
        f"next: {next_suggested(status)} ──"
    )


def _state_marker(stage: str, s: ExperimentStatus) -> str:
    if _stage_done(stage, s):
        return "[x]"
    if _stage_partial(stage, s):
        return "[.]"
    return "[ ]"


def _board_detail(stage: str, s: ExperimentStatus) -> str:
    if stage == "init":
        bits = ["manifest.md ok" if s.has_manifest else "manifest.md missing"]
        bits.append("repo set" if s.has_repo else "repo missing")
        if s.has_clone:
            bits.append("cloned")
        return " · ".join(bits)
    if stage == "scout":
        if s.has_references:
            return "references.md filled"
        if s.has_papers_bound:
            return "papers bound · run /experiment scout"
        return "no papers bound (optional)"
    if stage == "design":
        return "designs/ populated" if s.has_design else "designs/ empty"
    if stage == "version":
        if s.version_count == 0:
            return "no versions yet"
        return f"{s.version_count} version(s) · latest {s.last_version}"
    if stage == "analyze":
        return "ready to compare" if s.version_count >= 2 else "need ≥2 versions"
    raise ValueError(f"unknown stage: {stage}")


def render_progress_board(slug: str, status: ExperimentStatus) -> str:
    """Multi-line full board for ``/experiment status``."""
    bar, done = _progress_bar(status)
    lines = [slug, f"[{bar}] {done}/{_BAR_WIDTH} stages", ""]
    for i, stage in enumerate(_STAGES, start=1):
        lines.append(
            f"  {_state_marker(stage, status)} {i}. {stage:<10} "
            f"{_board_detail(stage, status)}"
        )
    if status.last_sync or status.last_feasibility_check:
        lines.append("")
        if status.last_sync:
            lines.append(f"Last sync:        {status.last_sync.isoformat(timespec='seconds')}")
        if status.last_feasibility_check:
            lines.append(
                f"Last feasibility: {status.last_feasibility_check.isoformat(timespec='seconds')}"
            )
    lines.append("")
    lines.append(f"Suggested next: {next_suggested(status)}")
    return "\n".join(lines)


# ---------- repo + filesystem ops ----------

def check_repo_updates(
    url: str, branch: str = "main", local_sha: str | None = None
) -> dict:
    """Run ``git ls-remote <url> <branch>`` and compare to ``local_sha``.

    Returns a dict with keys ``remote_sha``, ``local_sha``, ``drift``, ``ahead``,
    ``error``. **Never raises** — git / network failures surface as
    ``error`` populated and the other fields nulled, so ``/experiment status``
    can survive a flaky network.
    """
    base = {
        "remote_sha": None,
        "local_sha": local_sha,
        "drift": None,
        "ahead": None,
        "error": None,
    }
    try:
        out = subprocess.run(  # noqa: S603 — no shell, fixed argv
            ["git", "ls-remote", url, branch],
            capture_output=True, text=True,
            timeout=_GIT_TIMEOUT_S, check=False,
        )
    except (subprocess.TimeoutExpired, FileNotFoundError, OSError) as e:
        return {**base, "error": f"{type(e).__name__}: {e}"}
    if out.returncode != 0:
        return {**base, "error": out.stderr.strip() or f"git exited {out.returncode}"}
    stdout = out.stdout.strip()
    if not stdout:
        return {**base, "error": f"no ref matching branch={branch!r}"}
    remote_sha = stdout.splitlines()[0].split()[0]
    drift = (remote_sha != local_sha) if local_sha else None
    return {**base, "remote_sha": remote_sha, "drift": drift}


def current_commit_sha(slug: str) -> str | None:
    """Return ``git rev-parse HEAD`` for the local clone, or ``None``."""
    repo = repo_clone_path(slug)
    if not repo.is_dir():
        return None
    try:
        out = subprocess.run(  # noqa: S603 — no shell, fixed argv
            ["git", "-C", str(repo), "rev-parse", "HEAD"],
            capture_output=True, text=True,
            timeout=_GIT_TIMEOUT_S, check=False,
        )
    except (subprocess.TimeoutExpired, FileNotFoundError, OSError):
        return None
    if out.returncode != 0:
        return None
    return out.stdout.strip() or None


def clone_repo(slug: str, url: str, branch: str = "main") -> Path:
    """``git clone --branch <branch> --depth 1 <url>`` into the experiment dir.

    Raises ``FileExistsError`` if the destination already exists, ``RuntimeError``
    on a non-zero ``git clone`` exit.
    """
    dest = repo_clone_path(slug)
    if dest.exists():
        raise FileExistsError(f"clone destination already exists: {dest}")
    dest.parent.mkdir(parents=True, exist_ok=True)
    out = subprocess.run(  # noqa: S603 — no shell, fixed argv
        ["git", "clone", "--branch", branch, "--depth", "1", url, str(dest)],
        capture_output=True, text=True,
        timeout=_CLONE_TIMEOUT_S, check=False,
    )
    if out.returncode != 0:
        raise RuntimeError(
            f"git clone failed (exit {out.returncode}): {out.stderr.strip()}"
        )
    return dest


def mirror_results(
    slug: str,
    version: str,
    src: Path,
    *,
    boundary_root: Path | None = None,
    force: bool = False,
) -> Path:
    """Copy a result file or directory from the bound repo into local storage.

    Refuses to overwrite a non-empty destination unless ``force=True``. Warns
    on files over 100 MB (raises ``ValueError`` unless ``force=True``). If
    ``boundary_root`` is given, ``src`` must resolve inside it.
    """
    src = Path(src)
    if boundary_root is not None:
        _guard_under(boundary_root, src, "mirror source")
    if not src.exists():
        raise FileNotFoundError(f"mirror source does not exist: {src}")
    dest_dir = result_path(slug, version)
    dest_dir.parent.mkdir(parents=True, exist_ok=True)
    if src.is_file():
        size = src.stat().st_size
        if size > _LARGE_RESULT_BYTES and not force:
            raise ValueError(
                f"result file is {size / 1024 / 1024:.1f} MB (> 100 MB); "
                "pass force=True to mirror anyway"
            )
        dest_dir.mkdir(parents=True, exist_ok=True)
        dest_file = dest_dir / src.name
        if dest_file.exists() and not force:
            raise FileExistsError(f"mirror destination exists: {dest_file}")
        shutil.copy2(src, dest_file)
        return dest_file
    if src.is_dir():
        if dest_dir.exists() and any(dest_dir.iterdir()) and not force:
            raise FileExistsError(f"mirror destination is non-empty: {dest_dir}")
        if dest_dir.exists():
            shutil.rmtree(dest_dir)
        shutil.copytree(src, dest_dir)
        return dest_dir
    raise ValueError(f"mirror source is neither file nor directory: {src}")


# ---------- environment capture ----------

def _safe_subprocess(cmd: list[str], timeout: int = _ENV_PROBE_TIMEOUT_S) -> str | None:
    try:
        out = subprocess.run(  # noqa: S603 — no shell, caller-supplied argv
            cmd, capture_output=True, text=True, timeout=timeout, check=False,
        )
    except (subprocess.TimeoutExpired, FileNotFoundError, OSError):
        return None
    if out.returncode != 0:
        return None
    return out.stdout


def _probe_cuda() -> str | None:
    out = _safe_subprocess(["nvcc", "--version"])
    if not out:
        return None
    m = re.search(r"release\s+(\d+\.\d+)", out)
    return m.group(1) if m else None


def _probe_gpu() -> list[dict]:
    out = _safe_subprocess([
        "nvidia-smi",
        "--query-gpu=name,driver_version",
        "--format=csv,noheader",
    ])
    if not out:
        return []
    by_name: dict[str, dict] = {}
    for line in out.strip().splitlines():
        parts = [s.strip() for s in line.split(",")]
        if len(parts) < 2:
            continue
        name, driver = parts[0], parts[1]
        if name in by_name:
            by_name[name]["count"] += 1
        else:
            by_name[name] = {"name": name, "count": 1, "driver": driver}
    return list(by_name.values())


def _probe_libraries() -> dict[str, str]:
    out = _safe_subprocess([sys.executable, "-m", "pip", "freeze"], timeout=15)
    if not out:
        return {}
    libs: dict[str, str] = {}
    for line in out.splitlines():
        if "==" in line:
            name, _, version = line.partition("==")
        elif " @ " in line:
            name, _, _ = line.partition(" @ ")
            version = "unknown"
        else:
            continue
        key = name.strip().lower()
        if key in _TRACKED_LIBS:
            libs[key] = version.strip()
    return libs


def _probe_full_pip_freeze() -> str | None:
    return _safe_subprocess([sys.executable, "-m", "pip", "freeze"], timeout=15)


def capture_env() -> dict:
    """Cross-platform env snapshot for reproducibility / rebuttal.

    Always populates ``hostname``, ``os``, ``arch``, ``python`` (no subprocess
    needed). Adds ``cuda``, ``gpu``, ``libraries`` if probes succeed; missing
    keys are simply omitted rather than crashing the capture.
    """
    env: dict = {
        "hostname": socket.gethostname(),
        "os": platform.platform(),
        "arch": platform.machine(),
        "python": platform.python_version(),
    }
    cuda = _probe_cuda()
    if cuda:
        env["cuda"] = cuda
    gpu = _probe_gpu()
    if gpu:
        env["gpu"] = gpu
    libs = _probe_libraries()
    if libs:
        env["libraries"] = libs
    return env


# ---------- version registration ----------

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
        any(c in text for c in ':#"\'\n[]{}|>&*!?%`,')
        or text.strip() != text
        or text in ("null", "true", "false", "yes", "no")
        or text[:1] in "@-"
    )
    if needs_quote:
        return '"' + text.replace("\\", "\\\\").replace('"', '\\"') + '"'
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


def register_version(
    slug: str,
    version: str,
    description: str,
    *,
    kind: Literal["major", "minor"] = "minor",
    config: str | None = None,
    result_in_repo: str | None = None,
    seeds: list[int] | None = None,
    metrics: dict[str, float] | None = None,
    notes: str = "",
    force: bool = False,
) -> Path:
    """Compose and write ``versions/<vN.M>.md`` for ``slug``.

    Refuses to overwrite an existing file unless ``force=True`` — surfaces the
    suggested next version in the exception message. ``next_version`` is the
    canonical suggestion source; this function accepts any well-formed
    ``vN.M`` so callers can deliberately skip numbers (e.g. ``v1.3`` -> ``v3.0``).
    """
    parse_semver(version)
    if kind not in ("major", "minor"):
        raise ValueError(f"unknown version kind: {kind!r}")
    out_path = version_path(slug, version)
    if out_path.exists() and not force:
        suggestion = next_version(slug, "minor")
        raise FileExistsError(
            f"version {version} already exists for {slug}; "
            f"suggested next: {suggestion} (or pass force=True)"
        )
    out_path.parent.mkdir(parents=True, exist_ok=True)

    env = capture_env()
    commit_sha = current_commit_sha(slug)
    mirrored: Path | None = None
    if result_in_repo:
        src = resolve_result_in_repo(slug, result_in_repo)
        mirrored = mirror_results(
            slug, version, src,
            boundary_root=repo_clone_path(slug),
            force=force,
        )

    freeze = _probe_full_pip_freeze()
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
        "status": "completed",
        "commit_sha": commit_sha,
        "config_snapshot": config,
        "result_file": result_in_repo,
        "mirrored_to": (
            str(mirrored.relative_to(experiment_path(slug))) if mirrored else None
        ),
        "started_at": None,
        "finished_at": None,
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
    writes today, may miss hand-edited files with unusual indentation. The
    interactive fallback in ``/experiment feasibility`` covers gaps.
    """
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
            section = None
            current_gpu = None
            stripped = line.rstrip()
            if stripped.startswith("host:") and stripped.strip() != "host: null":
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
    return hostname, gpus


def infer_fleet_from_versions() -> list[Machine]:
    """Walk every experiment's ``versions/*.md`` files, extract host + GPU info,
    dedupe by hostname. Returned machines are sorted by hostname.

    Used by ``/experiment feasibility`` to bootstrap the fleet view from past
    runs. The interactive fallback in the skill body handles machines the user
    has but hasn't run anything on yet, persisting to ``inputs/fleet.md``.
    """
    if not EXPERIMENTS_DIR.is_dir():
        return []
    by_host: dict[str, Machine] = {}
    for version_file in EXPERIMENTS_DIR.glob("*/versions/*.md"):
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


# ---------- listing + parsing stubs ----------

def list_experiments() -> list[Path]:
    """Return all per-experiment manifest paths (excluding ``_*`` scratches)."""
    if not EXPERIMENTS_DIR.is_dir():
        return []
    out: list[Path] = []
    for child in sorted(EXPERIMENTS_DIR.iterdir()):
        if not child.is_dir() or child.name.startswith("_") or child.name.startswith("."):
            continue
        m = child / "manifest.md"
        if m.is_file():
            out.append(m)
    return out


def parse_experiment(path: Path) -> Experiment:
    """Parse ``manifest.md`` into an :class:`Experiment`.

    Not implemented yet — lands with the plugin-wide YAML-frontmatter parser
    decision (see :func:`research_assistant.mentor.boss_profile.parse_profile`).
    """
    raise NotImplementedError(
        "YAML frontmatter parsing pending real /experiment sync"
    )


def parse_version(path: Path) -> Version:
    """Parse a ``versions/<vN.M>.md`` file. Not implemented yet."""
    raise NotImplementedError(
        "YAML frontmatter parsing pending real /experiment sync"
    )


def parse_data_index(path: Path) -> list[DataArtifact]:
    """Parse ``data/index.md`` sections. Not implemented yet."""
    raise NotImplementedError(
        "YAML frontmatter parsing pending real /experiment sync"
    )


def parse_fleet(path: Path) -> FleetSnapshot:
    """Parse ``inputs/fleet.md`` into a :class:`FleetSnapshot`.

    Not implemented yet — lands with the plugin-wide YAML-frontmatter parser
    decision. ``/experiment feasibility`` reads the YAML inline (via Claude's
    parsing in the skill body) until this stub lands a real implementation.
    """
    raise NotImplementedError(
        "YAML frontmatter parsing pending real /experiment feasibility"
    )


def parse_feasibility(path: Path) -> FeasibilityReport:
    """Parse a ``feasibility-<date>.md`` file. Not implemented yet."""
    raise NotImplementedError(
        "YAML frontmatter parsing pending real /experiment feasibility"
    )


def parse_design(path: Path) -> dict:
    """Parse a ``designs/<dN.M>.md`` file. Not implemented yet."""
    raise NotImplementedError(
        "YAML frontmatter parsing pending real /experiment design"
    )


def to_agentdb_payload(entry: Experiment | Version | DataArtifact) -> dict:
    """Format an entry for ``mcp__claude-flow__memory_store``. Not implemented yet."""
    raise NotImplementedError("AgentDB indexing payload pending real /experiment sync")
