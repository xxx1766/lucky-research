"""Paper-scout helper for `/idea-check scout`.

Wraps :func:`research_assistant.lit.sourcing.search_arxiv` and adds a renderer
that groups PaperRefs by year + writes one "relation note" stub per paper for
Claude to fill in during the scout stage.

The skill prompt is the part that asks Claude to fill the relation note from
each paper's abstract; this module only formats the structural skeleton.
"""
from __future__ import annotations

from collections import defaultdict
from datetime import date

from pydantic import BaseModel, Field

from research_assistant.lit.sourcing import PaperRef, search_arxiv


def default_year_range(today: date | None = None) -> tuple[int, int]:
    """Last 3 years inclusive, ending at the current year."""
    today = today or date.today()
    return (today.year - 3, today.year)


class ScoutedPaper(BaseModel):
    """A scouted PaperRef + the relation note Claude is expected to fill."""

    ref: PaperRef
    relation_note: str = ""


class ScoutGaps(BaseModel):
    """Consolidated gap analysis over the scouted papers.

    Adapted from Orchestra-Research/AI-Research-SKILLs (MIT)
    ``0-autoresearch-skill`` Bootstrap step 2 — the four-bucket structure
    ("what's been tried / what hasn't / where methods break / Discussion
    future-work pointers"). Claude fills these buckets after Stage 2 step 4
    cluster + relation notes are written — the buckets are extracted from
    the same papers, just consolidated up one level.

    Empty lists are fine; the renderer omits empty buckets so the section
    stays compact when only one bucket has signal.
    """

    tried: list[str] = Field(default_factory=list)
    """Approaches the last 3 years have explored (one bullet per cluster)."""

    untried: list[str] = Field(default_factory=list)
    """Combinations, regimes, or extensions nobody has published yet."""

    where_broken: list[str] = Field(default_factory=list)
    """Concrete failure modes documented in the scouted papers."""

    future_work: list[str] = Field(default_factory=list)
    """Discussion-section pointers from the scouted papers (cite by URL)."""


class ScoutResult(BaseModel):
    """Aggregate result for a single scout invocation."""

    query: str
    year_range: tuple[int, int]
    papers: list[ScoutedPaper] = Field(default_factory=list)
    gaps: ScoutGaps = Field(default_factory=ScoutGaps)


def scout_recent_papers(
    query: str,
    year_range: tuple[int, int] | None = None,
    max_results: int = 25,
) -> ScoutResult:
    """Call arXiv search, wrap each ``PaperRef`` into a ``ScoutedPaper``.

    Returns even when arXiv yields no rows — the empty list signals to the
    skill prompt that it should fall back to WebSearch for non-arXiv venues.
    """
    if not query.strip():
        raise ValueError("empty scout query")
    yr = year_range or default_year_range()
    refs = search_arxiv(query=query, year_range=yr, max_results=max_results)
    papers = [ScoutedPaper(ref=r) for r in refs]
    return ScoutResult(query=query, year_range=yr, papers=papers)


def _group_by_year(papers: list[ScoutedPaper]) -> dict[int, list[ScoutedPaper]]:
    out: dict[int, list[ScoutedPaper]] = defaultdict(list)
    for p in papers:
        out[p.ref.year].append(p)
    return dict(out)


def render_scout_md(result: ScoutResult) -> str:
    """Render the scout result to ``outputs/idea-checks/<slug>/scout.md``."""
    lo, hi = result.year_range
    lines: list[str] = [
        "# Scout — recent papers",
        "",
        f"**Query:** `{result.query}`",
        "",
        f"**Year range:** {lo}–{hi}",
        "",
    ]
    if not result.papers:
        lines.append(
            "_No arXiv hits. Try a broader query, or fall back to WebSearch for "
            "venues without an arXiv mirror (OSDI/SOSP/ATC/USENIX Security/etc.)._"
        )
        lines.append("")
        gap_block = _render_gaps_block(result.gaps)
        if gap_block:
            lines.append(gap_block)
        return "\n".join(lines).rstrip() + "\n"
    grouped = _group_by_year(result.papers)
    for year in sorted(grouped.keys(), reverse=True):
        lines.append(f"## {year}")
        lines.append("")
        for sp in grouped[year]:
            r = sp.ref
            title_link = f"[{r.title}]({r.url})" if r.url else r.title
            authors = ", ".join(r.authors[:3])
            if len(r.authors) > 3:
                authors += " et al."
            lines.append(f"### {title_link}")
            lines.append("")
            if authors:
                lines.append(f"_{authors} — {r.venue or 'arXiv'}, {r.year}_")
                lines.append("")
            if sp.relation_note:
                lines.append(sp.relation_note)
            else:
                lines.append(
                    "_Relation note pending: what they did · how it relates to your "
                    "idea · why it doesn't subsume yours._"
                )
            lines.append("")
    gap_block = _render_gaps_block(result.gaps)
    if gap_block:
        lines.append(gap_block)
    return "\n".join(lines).rstrip() + "\n"


def _render_gaps_block(gaps: ScoutGaps) -> str:
    """Render the four-bucket Gaps section. Returns ``""`` if all buckets empty."""
    buckets = [
        ("Tried in the last 3 years", gaps.tried),
        ("Not tried yet", gaps.untried),
        ("Where existing methods break", gaps.where_broken),
        ("Discussion-section future work", gaps.future_work),
    ]
    if not any(items for _, items in buckets):
        return ""
    lines = ["## Gaps from this scout", ""]
    for label, items in buckets:
        if not items:
            continue
        lines.append(f"### {label}")
        lines.append("")
        for it in items:
            lines.append(f"- {it}")
        lines.append("")
    return "\n".join(lines).rstrip() + "\n"


def to_agentdb_payload(result: ScoutResult) -> dict:
    """Compact payload for ``memory_store namespace=ideas, key=<slug>/scout``."""
    return {
        "query": result.query,
        "year_range": list(result.year_range),
        "papers": [
            {"ref": p.ref.model_dump(), "relation_note": p.relation_note}
            for p in result.papers
        ],
        "gaps": result.gaps.model_dump(),
    }
