"""Parse the per-section page budget out of a direction's ``outline.md``.

``/paper`` directions plan a hard page budget *before* drafting — a Markdown
table under a ``## Page budget`` heading, one row per section::

    | § | Section | File | Pages | Cuts to |
    | 1 | Introduction | `sections/intro.md` | 1.5 | — |
    | 2 | Motivation   | `sections/motivation.md` | 2.0 | — |

This module extracts ``{section_stem: planned_pages}`` from that table so the
dashboard can weight progress by how much of each section's *page allotment* is
drafted, rather than treating every section equally. Parsing is lenient: rows
without a parseable page number (``(not counted)`` abstract, the body-total
line, references) are simply skipped, and a direction with no budget table
yields ``{}`` (the caller falls back to the 7-stage pipeline metric).

The ``File`` cell points at ``sections/<stem>.md`` while drafts land as
``sections/<stem>.tex`` — we key on the stem so the two reconcile.
"""
from __future__ import annotations

import re
from pathlib import Path

# `sections/<stem>.md` or `.tex`, optionally in backticks.
_FILE_RE = re.compile(r"sections/([A-Za-z0-9][\w-]*)\.(?:md|tex)")


def _first_float_after(cells: list[str], start: int) -> float | None:
    """First strictly-positive float in ``cells[start+1:]`` (else ``None``).

    Searching *after* the file cell is deliberate: the leading ``§`` column is
    also numeric, so a naive "first number on the row" would grab the section
    index instead of the page count.
    """
    for c in cells[start + 1:]:
        token = c.strip().strip("*").strip()
        try:
            v = float(token)
        except ValueError:
            continue
        if v > 0:
            return v
    return None


def parse_page_budget(direction_dir: Path) -> dict[str, float]:
    """Return ``{section_stem: planned_pages}`` from ``<direction>/outline.md``.

    Insertion order follows the table (so callers can render sections in the
    planned order). Empty dict when there is no outline or no budget rows.
    """
    outline = Path(direction_dir) / "outline.md"
    if not outline.is_file():
        return {}
    try:
        text = outline.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return {}

    budget: dict[str, float] = {}
    for line in text.splitlines():
        if "|" not in line or "sections/" not in line:
            continue
        m = _FILE_RE.search(line)
        if not m:
            continue
        cells = line.split("|")
        file_idx = next((i for i, c in enumerate(cells) if "sections/" in c), None)
        if file_idx is None:
            continue
        pages = _first_float_after(cells, file_idx)
        if pages is not None:
            budget[m.group(1)] = pages
    return budget
