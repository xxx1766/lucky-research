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
    out: list[DataArtifact] = []
    for fm, body in split_blocks(text):
        fm.setdefault("description", body.strip())
        try:
            out.append(DataArtifact.model_validate(fm))
        except Exception:
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

    Falls back to the filename's date portion (``feasibility-YYYY-MM-DD``) when
    the frontmatter omits ``date``.
    """
    from research_assistant.common.frontmatter import parse as parse_fm

    data, body = parse_fm(path)
    if "date" not in data:
        stem = Path(path).stem
        if stem.startswith("feasibility-"):
            try:
                data["date"] = date.fromisoformat(stem[len("feasibility-"):])
            except ValueError:
                pass
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
