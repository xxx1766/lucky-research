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
    """Search arXiv via the `arxiv` package, optionally filtering by year window.

    The arxiv server returns results sorted by relevance; we over-fetch by 3x to
    leave headroom for the year filter, then truncate to ``max_results``.
    Returns an empty list rather than raising when the network probe yields
    nothing — callers in /idea-check scout treat that as "fall back to WebSearch".
    """
    import arxiv

    client = arxiv.Client()
    search = arxiv.Search(
        query=query,
        max_results=max_results * 3,
        sort_by=arxiv.SortCriterion.Relevance,
    )
    refs: list[PaperRef] = []
    for r in client.results(search):
        year = r.published.year
        if year_range is not None and not (year_range[0] <= year <= year_range[1]):
            continue
        entry_id = r.entry_id
        bare_id = entry_id.rsplit("/", 1)[-1].split("v", 1)[0]
        refs.append(
            PaperRef(
                id=bare_id,
                title=(r.title or "").strip(),
                authors=[a.name for a in (r.authors or [])],
                abstract=(r.summary or "").strip(),
                year=year,
                venue="arXiv",
                url=entry_id,
                pdf_url=r.pdf_url,
            )
        )
        if len(refs) >= max_results:
            break
    return refs


def search_for_direction(
    venue: str,
    direction_keywords: list[str],
    max_results: int = 25,
) -> list[PaperRef]:
    """Unified entry: try OpenReview if venue is supported, fall back to arXiv."""
    raise NotImplementedError("Unified search lands with the real /paper scout body")
