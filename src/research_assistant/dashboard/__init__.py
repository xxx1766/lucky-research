"""``/dashboard`` — a single self-contained HTML overview of the research state.

Two panels, both read from on-disk truth (no AgentDB dependency):

* **Ideas** — every captured idea (``outputs/idea-checks/<slug>/idea.md``) via
  :func:`research_assistant.ideas.registry.list_ideas`.
* **Papers** — every ``(venue, direction)`` under ``outputs/papers/`` with its
  7-stage pipeline completion (``venue → render``), per-section word count and
  unresolved-placeholder count, plus the venue's conference name + full-paper
  deadline parsed best-effort from ``_venue.md``.

The renderer ( :mod:`research_assistant.dashboard.render` ) emits one static
HTML file with inline CSS/JS — open it in a browser, click any column header to
re-sort. Papers default-sort by deadline (soonest first).

This module is pure aggregation: it walks the filesystem and returns typed rows.
Nothing here writes; :func:`build_dashboard` is the only side-effecting entry.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from datetime import date
from pathlib import Path

from research_assistant.common.io import PAPERS_DIR
from research_assistant.dashboard.outline_budget import parse_page_budget
from research_assistant.dashboard.venue_meta import VenueMeta, parse_venue_meta
from research_assistant.papers import (
    STAGE_COUNT,
    stage_status,
    stages_completed,
    tex_files,
)
from research_assistant.papers.placeholders import scan_placeholders

#: Rough words-per-body-page for converting a section's drafted word count into
#: an approximate page fill. Two-column 9–10pt camera-ready (OSDI/EuroSys) runs
#: ~800–1000 words/page; 900 is a deliberately coarse midpoint. Only used for
#: the *fill* estimate against an explicit page budget — never quoted as truth.
WORDS_PER_PAGE = 900

__all__ = [
    "IdeaRow",
    "PaperRow",
    "SectionRow",
    "DashboardData",
    "collect_ideas",
    "collect_papers",
    "collect",
    "build_dashboard",
]

# Strip a single-line `%` comment so the Chinese-translation comment above a
# paragraph is not counted as draft prose (mirrors placeholders._strip_tex_comment).
_COMMENT_RE = re.compile(r"(?<!\\)%.*$")


@dataclass(frozen=True)
class SectionRow:
    """One paper section — either a drafted ``sections/*.tex`` file, or a
    planned-but-not-yet-started section pulled from the outline page budget."""

    name: str                       # section stem, e.g. "intro"
    words: int                      # approximate word count (comments stripped)
    placeholders: int               # unresolved [..._NEEDED] / [CLAIM_UNVERIFIED]
    planned_pages: float | None = None  # page budget from outline.md (None = unplanned)
    drafted: bool = True            # a .tex file exists for it
    fill: float = 1.0               # 0..1 — drafted length vs page budget


@dataclass(frozen=True)
class PaperRow:
    """One ``(venue, direction)`` paper — or a venue with no direction yet."""

    venue: str                 # venue slug, e.g. "OSDI-2027"
    direction: str | None      # direction slug, or None when none exists
    conference: str            # full conference name (from _venue.md)
    deadline_text: str         # human-readable deadline window or "TBD"
    deadline_date: date | None # coarse approximate date, for sorting
    stages_done: int
    sections: tuple[SectionRow, ...] = ()
    # Page-budget progress (set only when outline.md has a budget table).
    pages_written: float | None = None  # Σ(planned_pages × fill)
    pages_total: float | None = None    # Σ(planned_pages)

    @property
    def stages_total(self) -> int:
        return STAGE_COUNT

    @property
    def uses_pages(self) -> bool:
        return self.pages_total is not None and self.pages_total > 0

    @property
    def percent(self) -> int:
        """Page-share progress when a budget exists, else 7-stage pipeline %."""
        if self.uses_pages:
            return round(100 * (self.pages_written or 0.0) / self.pages_total)
        if STAGE_COUNT == 0:
            return 0
        return round(100 * self.stages_done / STAGE_COUNT)

    @property
    def progress_detail(self) -> str:
        if self.uses_pages:
            return f"{self.pages_written:.1f}/{self.pages_total:.2f} pp"
        return f"{self.stages_done}/{STAGE_COUNT} stages"

    @property
    def open_placeholders(self) -> int:
        return sum(s.placeholders for s in self.sections)

    def days_left(self, today: date) -> int | None:
        if self.deadline_date is None:
            return None
        return (self.deadline_date - today).days


@dataclass(frozen=True)
class IdeaRow:
    """One captured idea (flattened from its manifest)."""

    slug: str
    status: str
    updated: date | None
    venue: str | None
    verdict: str | None
    statement: str


@dataclass
class DashboardData:
    """Everything the renderer needs."""

    ideas: list[IdeaRow] = field(default_factory=list)
    papers: list[PaperRow] = field(default_factory=list)
    generated_on: date | None = None


def _is_venue_or_direction(p: Path) -> bool:
    """A real venue/direction dir — skip dotfiles and ``_``-prefixed scaffolds
    (``_template``, ``_venue-refs``, ``_smoketest-*``...)."""
    return p.is_dir() and not p.name.startswith((".", "_"))


def _word_count(tex: Path) -> int:
    try:
        text = tex.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return 0
    total = 0
    for line in text.splitlines():
        total += len(_COMMENT_RE.sub("", line).split())
    return total


def collect_ideas() -> list[IdeaRow]:
    """Flatten every captured idea into a row. Empty when no ideas exist."""
    from research_assistant.ideas.registry import list_ideas

    rows: list[IdeaRow] = []
    for m in list_ideas():
        rows.append(
            IdeaRow(
                slug=m.slug,
                status=m.status,
                updated=m.updated,
                venue=m.venue,
                verdict=m.verdict,
                statement=m.statement,
            )
        )
    return rows


def _drafted_sections(direction_dir: Path) -> dict[str, tuple[int, int]]:
    """``{stem: (words, placeholders)}`` for every drafted ``sections/*.tex``."""
    counts: dict[str, int] = {}
    for ph in scan_placeholders(direction_dir):
        stem = ph.file.split("/")[-1].rsplit(".", 1)[0]
        counts[stem] = counts.get(stem, 0) + 1
    drafted: dict[str, tuple[int, int]] = {}
    for tex in tex_files(direction_dir):
        stem = tex.stem
        drafted[stem] = (_word_count(tex), counts.get(stem, 0))
    return drafted


def _section_rows(
    direction_dir: Path, budget: dict[str, float]
) -> tuple[tuple[SectionRow, ...], float | None, float | None]:
    """Build section rows + (pages_written, pages_total).

    With a ``budget`` the rows cover every *planned* section (so not-yet-started
    ones show as 0% and still count toward the denominator); ``fill`` is the
    drafted length (words ÷ WORDS_PER_PAGE) capped at the section's page budget.
    Without a budget the rows are just the drafted ``.tex`` files and the two
    page totals are ``None`` (caller falls back to the stage metric).
    """
    drafted = _drafted_sections(direction_dir)

    if not budget:
        rows = tuple(
            SectionRow(name=stem, words=w, placeholders=ph)
            for stem, (w, ph) in drafted.items()
        )
        return rows, None, None

    rows_list: list[SectionRow] = []
    pages_written = 0.0
    pages_total = 0.0
    for stem, planned in budget.items():
        words, ph = drafted.get(stem, (0, 0))
        is_drafted = stem in drafted
        written_pages = words / WORDS_PER_PAGE
        fill = min(1.0, written_pages / planned) if planned > 0 else 0.0
        if not is_drafted:
            fill = 0.0
        pages_total += planned
        pages_written += planned * fill
        rows_list.append(
            SectionRow(
                name=stem,
                words=words,
                placeholders=ph,
                planned_pages=planned,
                drafted=is_drafted,
                fill=fill,
            )
        )
    # Drafted sections that aren't in the budget (renamed / extra) — show them
    # but don't let them skew the planned-page denominator.
    for stem, (w, ph) in drafted.items():
        if stem not in budget:
            rows_list.append(SectionRow(name=stem, words=w, placeholders=ph, drafted=True))
    return tuple(rows_list), round(pages_written, 2), round(pages_total, 2)


def collect_papers(papers_dir: Path | None = None) -> list[PaperRow]:
    """Walk ``outputs/papers/`` into one row per (venue, direction).

    A venue with no real direction yields a single direction-less row so the
    venue (and its deadline) still appears on the board.
    """
    root = Path(papers_dir) if papers_dir is not None else PAPERS_DIR
    rows: list[PaperRow] = []
    if not root.is_dir():
        return rows

    for venue_dir in sorted(root.iterdir()):
        if not _is_venue_or_direction(venue_dir):
            continue
        meta: VenueMeta = parse_venue_meta(venue_dir, venue_slug=venue_dir.name)
        directions = [d for d in sorted(venue_dir.iterdir()) if _is_venue_or_direction(d)]

        if not directions:
            rows.append(
                PaperRow(
                    venue=venue_dir.name,
                    direction=None,
                    conference=meta.conference,
                    deadline_text=meta.deadline_text,
                    deadline_date=meta.deadline_date,
                    stages_done=1,  # venue set, no direction yet
                )
            )
            continue

        for d in directions:
            status = stage_status(d)
            budget = parse_page_budget(d)
            sections, pages_written, pages_total = _section_rows(d, budget)
            rows.append(
                PaperRow(
                    venue=venue_dir.name,
                    direction=d.name,
                    conference=meta.conference,
                    deadline_text=meta.deadline_text,
                    deadline_date=meta.deadline_date,
                    stages_done=stages_completed(status),
                    sections=sections,
                    pages_written=pages_written,
                    pages_total=pages_total,
                )
            )
    return rows


def _sort_papers(papers: list[PaperRow]) -> list[PaperRow]:
    """Soonest deadline first; undated papers last; then venue/direction."""
    far = date.max

    def key(p: PaperRow):
        return (p.deadline_date or far, p.venue, p.direction or "")

    return sorted(papers, key=key)


def collect(papers_dir: Path | None = None, *, today: date | None = None) -> DashboardData:
    """Gather ideas + papers into the renderer's input bundle."""
    ideas = sorted(
        collect_ideas(),
        key=lambda i: (i.updated or date.min, i.slug),
        reverse=True,
    )
    papers = _sort_papers(collect_papers(papers_dir))
    return DashboardData(ideas=ideas, papers=papers, generated_on=today or date.today())


def build_dashboard(out_path: Path, *, today: date | None = None) -> Path:
    """Render the dashboard HTML to ``out_path`` and return the written path."""
    from research_assistant.dashboard.render import render_html

    data = collect(today=today)
    out = Path(out_path)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(render_html(data), encoding="utf-8")
    return out
