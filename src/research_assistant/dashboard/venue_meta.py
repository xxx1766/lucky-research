"""Best-effort metadata extraction from a venue's ``_venue.md``.

The dashboard needs two facts per venue that live only in the freeform venue
brief: the **conference name** and the **full-paper submission deadline**. Both
are parsed leniently — venue briefs are hand-edited Markdown scaffolds that are
often ``TBD``-heavy, so every field degrades to a safe default rather than
raising.

Deadline parsing returns *two* values: the raw window string for display
(``"mid Dec 2026 (~Dec 10 ±1 wk, hard)"``) and a single approximate ``date``
for sorting. The approximate date is intentionally coarse — it exists only so
``/dashboard`` can order papers by how soon they are due, not to be quoted as
authoritative. Lock real deadlines against the official CFP.
"""
from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import date
from pathlib import Path

_MONTHS: dict[str, int] = {
    "jan": 1, "feb": 2, "mar": 3, "apr": 4, "may": 5, "jun": 6,
    "jul": 7, "aug": 8, "sep": 9, "oct": 10, "nov": 11, "dec": 12,
}
# qualifier word -> representative day-of-month
_QUALIFIER_DAY: dict[str, int] = {"early": 5, "mid": 15, "late": 25}

# `| Conference | <full name> |` inside the Quick-facts table.
_CONF_ROW_RE = re.compile(r"^\|\s*Conference\s*\|\s*(.+?)\s*\|", re.IGNORECASE | re.MULTILINE)
# A markdown table row whose first cell mentions "full paper".
_FULL_PAPER_ROW_RE = re.compile(
    r"^\|\s*Full\s+paper\b[^|]*\|\s*(.+?)\s*\|", re.IGNORECASE | re.MULTILINE
)
# An explicit `~Mon DD` anchor (e.g. "~Dec 10").
_TILDE_DAY_RE = re.compile(r"~\s*([A-Za-z]{3,9})\.?\s+(\d{1,2})")
# A `<qualifier> Mon YYYY` form (e.g. "mid Dec 2026").
_QUAL_MONTH_YEAR_RE = re.compile(
    r"\b(early|mid|late)\s+([A-Za-z]{3,9})\.?\s+(20\d{2})", re.IGNORECASE
)
# A bare `Mon YYYY` form.
_MONTH_YEAR_RE = re.compile(r"\b([A-Za-z]{3,9})\.?\s+(20\d{2})")
_YEAR_RE = re.compile(r"(20\d{2})")
# Venue slug trailing year, e.g. "OSDI-2027" -> 2027.
_SLUG_YEAR_RE = re.compile(r"(20\d{2})\s*$")
# Title line: "# OSDI '27 — ..." -> "OSDI '27".
_TITLE_RE = re.compile(r"^#\s+(.+?)(?:\s+[—\-–:]\s+.*)?$", re.MULTILINE)


@dataclass(frozen=True)
class VenueMeta:
    """Parsed venue facts. Every field is best-effort; ``""``/``None`` on miss."""

    conference: str = ""          # full conference name (or short title)
    deadline_text: str = "TBD"    # human-readable window for display
    deadline_date: date | None = None  # coarse approximate date, for sorting


def _month_num(word: str) -> int | None:
    return _MONTHS.get(word[:3].lower())


def _parse_deadline_date(cell: str) -> date | None:
    """Derive one coarse ``date`` from a deadline-cell string. ``None`` on miss."""
    year_anywhere = _YEAR_RE.search(cell)

    # 1. Explicit `~Mon DD` anchor — most precise.
    m = _TILDE_DAY_RE.search(cell)
    if m and year_anywhere:
        mon = _month_num(m.group(1))
        if mon is not None:
            day = max(1, min(28, int(m.group(2))))
            try:
                return date(int(year_anywhere.group(1)), mon, day)
            except ValueError:
                pass

    # 2. `<qualifier> Mon YYYY` — map the qualifier to a representative day.
    m = _QUAL_MONTH_YEAR_RE.search(cell)
    if m:
        mon = _month_num(m.group(2))
        if mon is not None:
            try:
                return date(int(m.group(3)), mon, _QUALIFIER_DAY[m.group(1).lower()])
            except ValueError:
                pass

    # 3. Bare `Mon YYYY` — assume mid-month.
    m = _MONTH_YEAR_RE.search(cell)
    if m:
        mon = _month_num(m.group(1))
        if mon is not None:
            try:
                return date(int(m.group(2)), mon, 15)
            except ValueError:
                pass
    return None


def parse_venue_meta(venue_dir: Path, *, venue_slug: str | None = None) -> VenueMeta:
    """Read ``<venue_dir>/_venue.md`` and extract conference name + deadline.

    Missing file, missing rows, or unparseable dates all degrade gracefully:
    ``conference`` falls back to the title line then to ``venue_slug``;
    ``deadline_text`` falls back to ``"TBD"``; ``deadline_date`` falls back to
    Dec 1 of the year embedded in ``venue_slug`` (so a CFP-less venue still
    sorts roughly by its target year) then to ``None``.
    """
    venue_path = Path(venue_dir)
    slug = venue_slug or venue_path.name
    brief = venue_path / "_venue.md"

    conference = ""
    deadline_text = "TBD"
    deadline_date: date | None = None

    if brief.is_file():
        try:
            text = brief.read_text(encoding="utf-8", errors="replace")
        except OSError:
            text = ""
        if text:
            cm = _CONF_ROW_RE.search(text)
            if cm:
                conference = cm.group(1).strip()
            if not conference:
                tm = _TITLE_RE.search(text)
                if tm:
                    conference = tm.group(1).strip()
            fm = _FULL_PAPER_ROW_RE.search(text)
            if fm:
                deadline_text = fm.group(1).strip()
                deadline_date = _parse_deadline_date(deadline_text)

    if not conference:
        conference = slug

    if deadline_date is None:
        ym = _SLUG_YEAR_RE.search(slug)
        if ym:
            try:
                deadline_date = date(int(ym.group(1)), 12, 1)
            except ValueError:
                deadline_date = None

    return VenueMeta(
        conference=conference,
        deadline_text=deadline_text,
        deadline_date=deadline_date,
    )
