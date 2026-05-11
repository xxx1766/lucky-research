"""Discovery helpers for venue-aware + arXiv-fallback paper sourcing.

Real implementations land later; signatures are locked here so the
paper-architect skill can call them as soon as bodies exist.
"""
from __future__ import annotations

from pydantic import BaseModel


class PaperRef(BaseModel):
    id: str
    title: str
    authors: list[str]
    abstract: str
    year: int
    venue: str | None = None
    url: str | None = None
    pdf_url: str | None = None


def search_openreview(venue: str, query: str, max_results: int = 25) -> list[PaperRef]:
    """Search OpenReview for papers at `venue` matching `query`.

    Supports ICLR / NeurIPS / COLM / TMLR. Returns up to `max_results`
    PaperRef rows. Implementation will use the openreview-py client.
    """
    raise NotImplementedError("OpenReview search lands with the real /paper scout body")


def search_arxiv(
    query: str,
    year_range: tuple[int, int] | None = None,
    max_results: int = 25,
) -> list[PaperRef]:
    """Search arXiv via the `arxiv` package."""
    raise NotImplementedError("arXiv search lands with the real /paper scout body")


def search_for_direction(
    venue: str,
    direction_keywords: list[str],
    max_results: int = 25,
) -> list[PaperRef]:
    """Unified entry: try OpenReview if venue is supported, fall back to arXiv."""
    raise NotImplementedError("Unified search lands with the real /paper scout body")
