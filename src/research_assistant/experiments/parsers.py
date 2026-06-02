"""Frontmatter parsers + AgentDB payload formatter for the experiments package.

Each parser is a thin three-step:
``read file → split YAML frontmatter → ``<Model>.model_validate(...)``.
Per-block ``parse_data_index`` tolerates malformed entries (skip rather than
raise) since the data index is user-edited.
"""
from __future__ import annotations

from datetime import date
from pathlib import Path

import research_assistant.experiments as _exp  # late attribute access for EXPERIMENTS_DIR

from .models import (
    DataArtifact,
    Experiment,
    FeasibilityReport,
    FleetSnapshot,
    Version,
)


def list_experiments() -> list[Path]:
    """Return all per-experiment manifest paths (excluding ``_*`` scratches)."""
    if not _exp.EXPERIMENTS_DIR.is_dir():
        return []
    out: list[Path] = []
    for child in sorted(_exp.EXPERIMENTS_DIR.iterdir()):
        if not child.is_dir() or child.name.startswith("_") or child.name.startswith("."):
            continue
        m = child / "manifest.md"
        if m.is_file():
            out.append(m)
    return out


def parse_experiment(path: Path) -> Experiment:
    """Parse ``manifest.md`` into an :class:`Experiment`.

    Falls back to the parent directory name for ``slug`` when frontmatter omits
    it (matches the convention ``outputs/experiments/<slug>/manifest.md``).
    """
    from research_assistant.common.frontmatter import parse as parse_fm

    data, body = parse_fm(path)
    data.setdefault("slug", Path(path).parent.name)
    data.setdefault("body", body)
    return Experiment.model_validate(data)


def parse_version(path: Path) -> Version:
    """Parse a ``versions/<vN.M>.md`` file into a :class:`Version`.

    Falls back to the filename stem for ``version`` when frontmatter omits it.
    """
    from research_assistant.common.frontmatter import parse as parse_fm

    data, body = parse_fm(path)
    data.setdefault("version", Path(path).stem)
    data.setdefault("body", body)
    return Version.model_validate(data)


def parse_data_index(path: Path) -> list[DataArtifact]:
    """Parse ``data/index.md`` into a list of :class:`DataArtifact`.

    Each artifact is one ``---\\n<yaml>\\n---\\n`` block in the file. Blocks that
    fail validation are skipped (the registry is user-edited and may contain
    partial entries); the function never raises on individual block errors.
    Missing file → ``[]``.
    """
    from research_assistant.common.frontmatter import split_blocks

    file_path = Path(path)
    if not file_path.is_file():
        return []
    text = file_path.read_text(encoding="utf-8")
    from pydantic import ValidationError

    out: list[DataArtifact] = []
    for fm, body in split_blocks(text):
        fm.setdefault("description", body.strip())
        try:
            out.append(DataArtifact.model_validate(fm))
        except ValidationError:
            continue
    return out


def parse_fleet(path: Path) -> FleetSnapshot:
    """Parse ``inputs/fleet.md`` into a :class:`FleetSnapshot`."""
    from research_assistant.common.frontmatter import parse as parse_fm

    data, body = parse_fm(path)
    data.setdefault("body", body)
    return FleetSnapshot.model_validate(data)


def parse_feasibility(path: Path) -> FeasibilityReport:
    """Parse a ``feasibility-<date>.md`` file into a :class:`FeasibilityReport`.

    Falls back to the filename's date portion (``feasibility-YYYY-MM-DD``,
    optionally suffixed ``-2``/``-3``/... when :func:`feasibility_path`
    collided) when the frontmatter omits ``date``.
    """
    from research_assistant.common.frontmatter import parse as parse_fm

    from .paths import _parse_feasibility_filename

    data, body = parse_fm(path)
    if "date" not in data:
        parsed = _parse_feasibility_filename(Path(path).name)
        if parsed is not None:
            data["date"] = parsed[0]
    data.setdefault("body", body)
    return FeasibilityReport.model_validate(data)


def parse_design(path: Path) -> dict:
    """Parse a ``designs/<dN.M>.md`` file. Returns the raw frontmatter dict.

    The design body is intentionally free-form prose (Research Question /
    Hypothesis / etc.); we return only the typed frontmatter for callers that
    need to read ``design_version`` / ``derived_from`` / ``adopted_suggestions``.
    """
    from research_assistant.common.frontmatter import parse as parse_fm

    data, _body = parse_fm(path)
    return data


def to_agentdb_payload(entry: Experiment | Version | DataArtifact) -> dict:
    """Format an entry for ``mcp__claude-flow__memory_store``.

    Returns a flat metadata dict (long prose excluded) plus a ``kind``
    discriminator so the indexer can route into the right ``project/experiments/...``
    sub-namespace.
    """
    if isinstance(entry, Experiment):
        return {
            "kind": "experiment",
            "slug": entry.slug,
            "title": entry.title,
            "created_at": entry.created_at.isoformat(),
            "status": entry.status,
            "tags": list(entry.tags),
            "papers": list(entry.papers),
            "repo_url": entry.repo.url,
        }
    if isinstance(entry, Version):
        return {
            "kind": "experiment_version",
            "version": entry.version,
            "description": entry.description,
            "status": entry.status,
            "commit_sha": entry.commit_sha,
            "metrics": dict(entry.metrics),
            "python": entry.python,
            "cuda": entry.cuda,
            "result_file": entry.result_file,
            "mirrored_to": entry.mirrored_to,
        }
    if isinstance(entry, DataArtifact):
        return {
            "kind": "experiment_data",
            "slug": entry.slug,
            "category": entry.category,
            "path": entry.path,
            "sha256": entry.sha256,
            "size": entry.size,
            "produced_by": entry.produced_by,
        }
    raise TypeError(f"unsupported entry type: {type(entry).__name__}")


# ---------- per-version indexing ----------

def _version_search_text(v: Version, slug: str) -> str:
    """Compose the embeddable text for one experiment version.

    The text is what gets ONNX-embedded so semantic search can hit on things
    like "rouge-L > 0.4" or "ablation where seed jitter mattered". Keep it
    short, descriptive, and metric-bearing — not a YAML dump.
    """
    parts: list[str] = [f"Experiment {slug} version {v.version}: {v.description}"]
    parts.append(f"Status: {v.status}")
    if v.commit_sha:
        parts.append(f"Commit: {v.commit_sha[:12]}")
    if v.metrics:
        metric_str = ", ".join(f"{k}={val}" for k, val in v.metrics.items())
        parts.append(f"Metrics: {metric_str}")
    if v.seeds:
        parts.append(f"Seeds: {', '.join(str(s) for s in v.seeds)}")
    if v.notes:
        excerpt = v.notes.strip().splitlines()[0][:200]
        parts.append(f"Notes: {excerpt}")
    return "\n".join(parts)


def version_indexing_payload(slug: str, version: str) -> dict:
    """Return ``{namespace, key, value, metadata}`` for ``memory_store``.

    The skill prompt calls ``mcp__claude-flow__memory_store(**payload)`` after
    ``register_version`` writes ``versions/<vN.M>.md``. Splitting the I/O from
    the call lets tests check the payload shape without mocking MCP.

    Raises :class:`FileNotFoundError` when ``versions/<version>.md`` is missing.
    """
    from .paths import version_path

    path = version_path(slug, version)
    v = parse_version(path)
    metadata = to_agentdb_payload(v)
    metadata["slug"] = slug
    return {
        "namespace": f"project/experiments/{slug}/versions",
        "key": v.version,
        "value": _version_search_text(v, slug),
        "metadata": metadata,
    }


def iter_version_indexing_payloads(slug: str | None = None) -> list[dict]:
    """Walk every ``versions/<vN.M>.md`` and emit one indexing payload each.

    Used by ``/experiment index`` for backfill after ``ruvector.db`` is
    rebuilt (the on-disk markdown survives even when AgentDB is wiped).
    When ``slug`` is ``None`` sweeps every experiment; otherwise scopes to one.
    Malformed version files are skipped, matching :func:`parse_data_index`'s
    tolerance for user-edited registries.
    """
    if not _exp.EXPERIMENTS_DIR.is_dir():
        return []
    if slug is not None:
        slugs = [slug]
    else:
        slugs = sorted(
            p.name for p in _exp.EXPERIMENTS_DIR.iterdir()
            if p.is_dir() and not p.name.startswith(("_", "."))
        )
    from pydantic import ValidationError

    out: list[dict] = []
    for s in slugs:
        versions_dir = _exp.EXPERIMENTS_DIR / s / "versions"
        if not versions_dir.is_dir():
            continue
        for vfile in sorted(versions_dir.glob("v*.md")):
            try:
                out.append(version_indexing_payload(s, vfile.stem))
            except (ValidationError, ValueError, OSError):
                continue
    return out
