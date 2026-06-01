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


# OpenReview venue → search group mapping. The group is the conference series;
# year filtering is done post-hoc via the per-paper invitation string.
_OPENREVIEW_GROUPS: dict[str, str] = {
    "iclr": "ICLR",
    "neurips": "NeurIPS",
    "colm": "COLM",
    "tmlr": "TMLR",
}


def _openreview_group_for(venue: str) -> str | None:
    """Normalize ``venue`` to an OpenReview group id, or ``None`` if unsupported.

    Accepts forms like ``ICLR``, ``iclr-2024``, ``NeurIPS_2023``. Year suffixes
    are stripped — year filtering happens after the search.
    """
    if not venue:
        return None
    head = venue.strip().lower().replace("_", "-").split("-", 1)[0]
    return _OPENREVIEW_GROUPS.get(head)


def _unwrap_v2(value):
    """OpenReview v2 wraps content values as ``{"value": <x>}``. Unwrap safely."""
    if isinstance(value, dict) and "value" in value:
        return value["value"]
    return value


def _year_from_invitations(invitations: list[str] | None) -> int | None:
    """Extract a 4-digit year from any invitation string like ``ICLR.cc/2024/...``."""
    if not invitations:
        return None
    for inv in invitations:
        for tok in inv.split("/"):
            if tok.isdigit() and len(tok) == 4:
                year = int(tok)
                if 2000 <= year <= 2100:
                    return year
    return None


def search_openreview(
    venue: str,
    query: str,
    max_results: int = 25,
    *,
    year_range: tuple[int, int] | None = None,
) -> list[PaperRef]:
    """Search OpenReview for papers at ``venue`` matching ``query``.

    Supports ICLR / NeurIPS / COLM / TMLR. Returns up to ``max_results``
    PaperRef rows. Unsupported venues, network failure, or empty results all
    yield ``[]`` — callers fall back to :func:`search_arxiv`.
    """
    group = _openreview_group_for(venue)
    if group is None:
        return []
    try:
        from openreview.api import OpenReviewClient
        client = OpenReviewClient(baseurl="https://api2.openreview.net")
        notes = client.search_notes(
            term=query,
            content="all",
            group=group,
            limit=max_results * 3,
        )
    except Exception:
        return []

    refs: list[PaperRef] = []
    for n in notes or []:
        content = getattr(n, "content", None) or {}
        title = _unwrap_v2(content.get("title"))
        abstract = _unwrap_v2(content.get("abstract"))
        authors = _unwrap_v2(content.get("authors")) or []
        if not (title and abstract):
            # filter out reviews / comments / decisions — only paper submissions
            continue
        year = _year_from_invitations(getattr(n, "invitations", None))
        if year is None:
            continue
        if year_range is not None and not (year_range[0] <= year <= year_range[1]):
            continue
        nid = getattr(n, "id", None)
        if not nid:
            continue
        refs.append(
            PaperRef(
                id=nid,
                title=str(title).strip(),
                authors=[str(a) for a in (authors if isinstance(authors, list) else [authors])],
                abstract=str(abstract).strip(),
                year=year,
                venue=venue,
                url=f"https://openreview.net/forum?id={nid}",
                pdf_url=f"https://openreview.net/pdf?id={nid}",
            )
        )
        if len(refs) >= max_results:
            break
    return refs


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
    *,
    year_range: tuple[int, int] | None = None,
) -> list[PaperRef]:
    """Unified entry: try OpenReview if venue is supported, fall back to arXiv.

    Joins ``direction_keywords`` with spaces to build the query. If the venue
    maps to an OpenReview group and the OpenReview search returns ≥1 result,
    those are returned. Otherwise (unsupported venue, network failure, or
    empty result), falls back to :func:`search_arxiv` with the same query
    and optional ``year_range``.
    """
    query = " ".join(k.strip() for k in direction_keywords if k and k.strip())
    if not query:
        return []
    if _openreview_group_for(venue) is not None:
        refs = search_openreview(
            venue, query, max_results=max_results, year_range=year_range
        )
        if refs:
            return refs
    return search_arxiv(query, year_range=year_range, max_results=max_results)
