"""Idea-graph + Socratic-direction helpers — used by the `idea-validate` skill.

Two legacy modes (retained):
- horizontal: compare N papers on fixed axes (problem, method, dataset, metric, gap).
- vertical:   trace one idea's lineage across time.

New flow on top (used by ``/idea-check <free-text>`` and per-stage subcommands):
- Socratic discussion → distilled idea statement + persisted manifest.
- Scout (last 3 years, arXiv + WebSearch fallback) → grouped paper survey.
- Evaluate (value + feasibility rubric) → verdict + top-3 risks.
- Venues (curated registry × user-curated _venue.md) → ranked target list.
- Knowledge (brain-library index) → study plan, mirrored to AgentDB for /paper.
- Handoff → set ``project/paper-context.current`` so /paper can take over.

The submodules export the dataclasses + renderers; the skill prompt drives the
conversation and calls the AgentDB MCP tools.
"""
from __future__ import annotations

from collections import OrderedDict
from pathlib import Path

from research_assistant.ideas import (
    brainstorm,
    contrarian,
    evaluate,
    knowledge,
    registry,
    scout,
    socratic,
    status,
    venues,
)
from research_assistant.ideas.slug import slugify

_DEFAULT_AXES: tuple[str, ...] = ("problem", "method", "dataset", "metric", "gap")


def build_horizontal_matrix(summary_paths: list[Path], axes: list[str] | None = None) -> dict:
    """Return ``{paper_id: {axis: ""}}`` — a skeleton matrix the skill body fills in.

    Each ``paper_id`` is the summary file stem (Claude maps that back to title
    when it fills the cells). Returning the skeleton (rather than parsing each
    summary's prose) keeps this module deterministic and easy to test; the
    skill prompt drives the actual cell-filling step.
    """
    use_axes = list(axes) if axes else list(_DEFAULT_AXES)
    matrix: "OrderedDict[str, dict[str, str]]" = OrderedDict()
    for p in summary_paths:
        if not isinstance(p, Path):
            p = Path(p)
        matrix[p.stem] = {axis: "" for axis in use_axes}
    return dict(matrix)


def build_vertical_lineage(seed_paper_id: str, summary_paths: list[Path]) -> list[dict]:
    """Return a chronologically-sorted skeleton ``[{paper_id, year, relationship}]``.

    Like :func:`build_horizontal_matrix`, this is a structural scaffold — the
    skill prompt fills in ``relationship`` ("what new claim does this add")
    from the paper summaries.
    """
    if not seed_paper_id:
        raise ValueError("empty seed_paper_id")
    rows: list[dict] = []
    seen: set[str] = set()
    for p in summary_paths:
        if not isinstance(p, Path):
            p = Path(p)
        pid = p.stem
        if pid in seen:
            continue
        seen.add(pid)
        rows.append({"paper_id": pid, "year": None, "relationship": ""})
    rows.sort(key=lambda r: (r["paper_id"] != seed_paper_id, r["paper_id"]))
    return rows


__all__ = [
    "brainstorm",
    "build_horizontal_matrix",
    "build_vertical_lineage",
    "contrarian",
    "evaluate",
    "knowledge",
    "registry",
    "scout",
    "slugify",
    "socratic",
    "status",
    "venues",
]
