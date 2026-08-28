"""Idea-graph + gate-pipeline helpers — used by the `idea-validate` skill.

The progress axis is the **five-gate validation pipeline** (:mod:`gates`):
failure-case → problem-standalone → mechanism → predictions →
minimal-experiment. A gate that has not cleared blocks every later gate; the
override is recorded, never silent.

Everything else is a *service* the gates call for evidence, and none of them
advance status on their own:
- Socratic capture → distilled idea statement + persisted manifest.
- Brainstorm / contrarian → fresh angles, inverted framings, sibling ideas.
- Scout (last 3 years, arXiv + WebSearch fallback) → grouped paper survey.
- Assumption mining → the unstated premises a paper leans on.
- Evaluate (value + feasibility rubric) → scores, risks, pre-registration.
- Venues / knowledge → ranked target list, study plan.
- Handoff → set ``project/paper-context.current`` so /paper can take over.

Two legacy comparison modes are retained: ``horizontal`` (compare N papers on
fixed axes) and ``vertical`` (trace one idea's lineage).

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
    gates,
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
    "gates",
    "knowledge",
    "registry",
    "scout",
    "slugify",
    "socratic",
    "status",
    "venues",
]
