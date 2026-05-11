"""Idea graph helpers: build comparison matrices and lineage trees.

Used by the `idea-validate` skill. Two modes:
- horizontal: compare N papers on a fixed axis set (problem, method, dataset, metric).
- vertical:   trace one idea's lineage across time (papers that cite or extend it).
"""

from pathlib import Path


def build_horizontal_matrix(summary_paths: list[Path], axes: list[str]) -> dict:
    """Return a dict-of-dicts {paper_id: {axis: value}}. STUB."""
    raise NotImplementedError("ideas.build_horizontal_matrix")


def build_vertical_lineage(seed_paper_id: str, summary_paths: list[Path]) -> list[dict]:
    """Return a chronologically-sorted list of {paper_id, year, relationship}. STUB."""
    raise NotImplementedError("ideas.build_vertical_lineage")
