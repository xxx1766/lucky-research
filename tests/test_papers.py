"""Smoke tests for the paper-output helper package."""

from research_assistant.common.io import PAPERS_DIR
from research_assistant.papers import (
    direction_path,
    slugify_direction,
    slugify_venue,
    venue_path,
)


def test_slugify_venue_shape():
    assert slugify_venue("NeurIPS", 2026) == "NeurIPS-2026"
    assert slugify_venue("ICLR 2026", 2026) == "ICLR2026-2026"
    assert slugify_venue("CoLM", 2025) == "CoLM-2025"


def test_slugify_direction_shape():
    assert slugify_direction("Diffusion fine-tuning") == "diffusion-fine-tuning"
    assert slugify_direction("Retrieval Rerank") == "retrieval-rerank"
    assert slugify_direction("  spaced  ") == "spaced"


def test_venue_path_under_papers_dir():
    p = venue_path("NeurIPS-2026")
    assert p.parent == PAPERS_DIR
    assert p.name == "NeurIPS-2026"


def test_direction_path_nested():
    p = direction_path("NeurIPS-2026", "diffusion-finetune")
    assert p.parent.name == "NeurIPS-2026"
    assert p.name == "diffusion-finetune"
