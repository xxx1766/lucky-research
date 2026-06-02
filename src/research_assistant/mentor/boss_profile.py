"""Boss-profile corpus helpers — schema + I/O + indexing contract.

The user's "big boss" (大老板, group PI) is tracked across two artifacts on disk:

* ``inputs/boss-profile/profile.md`` — singleton profile (YAML frontmatter +
  free body). Captures research interests, hot buttons, sore spots, preferred
  communication style.
* ``inputs/boss-profile/meetings/YYYY-MM-DD.md`` — one file per report meeting
  (YAML frontmatter + body). Sediments feedback / action items over time.

The ``boss-historian`` agent mirrors both into AgentDB namespace ``project/boss/``
(``project/boss/profile`` + ``project/boss/meetings/<date>``) so it can semantically
recall relevant prior context before the next report.

Parsers (``parse_profile``, ``parse_meeting``) consume the YAML frontmatter via
:func:`research_assistant.common.frontmatter.parse`; ``to_agentdb_payload`` produces
the flat dict the historian agent stores in AgentDB.
"""
from __future__ import annotations

from datetime import date
from pathlib import Path

from pydantic import BaseModel, Field

from research_assistant.common.io import (
    BOSS_MEETINGS_DIR,
    BOSS_REHEARSALS_DIR,
    BOSS_REPORTS_DIR,
)


class BossProfile(BaseModel):
    name: str
    role: str | None = None
    research_interests: list[str] = Field(default_factory=list)
    recent_papers: list[str] = Field(default_factory=list)
    collaborators: list[str] = Field(default_factory=list)
    communication_style: str | None = None
    hot_buttons: list[str] = Field(default_factory=list)
    sore_spots: list[str] = Field(default_factory=list)
    preferred_format: str | None = None
    body: str = ""


class BossMeeting(BaseModel):
    date: date
    topic: str
    mode: str | None = None  # 1:1 | group | email | slack
    duration_min: int | None = None
    mood: str | None = None  # positive | neutral | concerned
    feedback: str | None = None
    action_items: list[str] = Field(default_factory=list)
    body: str = ""


def meeting_slug(d: date) -> str:
    """ISO-date slug for a meeting log file. Matches ``YYYY-MM-DD.md``."""
    return d.isoformat()


def list_meetings() -> list[Path]:
    """Return all meeting markdown files (excluding underscore-prefixed scratches).

    Mirrors :func:`research_assistant.mentor.past_work.list_entries` — sorted lexically,
    which for ``YYYY-MM-DD.md`` filenames is also chronological ascending.
    """
    if not BOSS_MEETINGS_DIR.is_dir():
        return []
    return sorted(
        p for p in BOSS_MEETINGS_DIR.glob("*.md") if not p.name.startswith("_")
    )


def recent_meetings(n: int = 3) -> list[Path]:
    """Return the ``n`` most recent meeting files, newest first.

    Sort key is the filename (``YYYY-MM-DD``), not mtime, so manually back-dated
    entries land in chronological order rather than insertion order.
    """
    return list(reversed(list_meetings()))[:n]


def list_reports() -> list[Path]:
    """Return all report-material markdown files under ``BOSS_REPORTS_DIR``.

    Sorted lexically; skips underscore-prefixed scratches (matches
    :func:`list_meetings` and :func:`research_assistant.mentor.past_work.list_entries`).
    """
    if not BOSS_REPORTS_DIR.is_dir():
        return []
    return sorted(
        p for p in BOSS_REPORTS_DIR.glob("*.md") if not p.name.startswith("_")
    )


def latest_report() -> Path | None:
    """Return the most-recently-modified report, or ``None`` if absent/empty.

    Uses mtime rather than filename sort: users may name reports topic-first
    (``q2-progress.md``) or date-first (``2026-05-13-q2.md``) and the freshest
    drop should win regardless.
    """
    reports = list_reports()
    if not reports:
        return None
    return max(reports, key=lambda p: p.stat().st_mtime)


def report_path(slug: str) -> Path:
    """Resolve a report slug to a path under ``BOSS_REPORTS_DIR``.

    Appends ``.md`` if missing. Raises ``ValueError`` on anything that resolves
    outside ``BOSS_REPORTS_DIR`` (path-traversal guard for the user-supplied
    arg in ``/boss rehearse <slug>``).
    """
    if not slug:
        raise ValueError("empty report slug")
    name = slug if slug.endswith(".md") else f"{slug}.md"
    candidate = (BOSS_REPORTS_DIR / name).resolve()
    root = BOSS_REPORTS_DIR.resolve()
    if root != candidate and root not in candidate.parents:
        raise ValueError(f"report slug escapes BOSS_REPORTS_DIR: {slug!r}")
    return candidate


def rehearsal_slug(d: date, report_slug: str) -> str:
    """Build ``<YYYY-MM-DD>-<report-slug>`` (no ``.md``).

    Strips a trailing ``.md`` from ``report_slug`` if the caller passed a
    filename instead of a bare slug.
    """
    if not report_slug:
        raise ValueError("empty report slug")
    stem = report_slug[:-3] if report_slug.endswith(".md") else report_slug
    return f"{d.isoformat()}-{stem}"


def rehearsal_path(d: date, report_slug: str) -> Path:
    """Return a collision-safe path under ``BOSS_REHEARSALS_DIR``.

    First conflict on the same day gets ``-2``, then ``-3``, ... — matches the
    meeting-log convention documented in ``boss-historian.md``.
    """
    base = rehearsal_slug(d, report_slug)
    candidate = BOSS_REHEARSALS_DIR / f"{base}.md"
    if not candidate.exists():
        return candidate
    n = 2
    while True:
        nth = BOSS_REHEARSALS_DIR / f"{base}-{n}.md"
        if not nth.exists():
            return nth
        n += 1


def parse_profile(path: Path) -> BossProfile:
    """Parse ``inputs/boss-profile/profile.md`` into a :class:`BossProfile`.

    YAML frontmatter holds the typed fields; the body below the closing fence
    is stored verbatim in :attr:`BossProfile.body`.
    """
    from research_assistant.common.frontmatter import parse as parse_fm

    data, body = parse_fm(path)
    data.setdefault("body", body)
    return BossProfile.model_validate(data)


def parse_meeting(path: Path) -> BossMeeting:
    """Parse one ``inputs/boss-profile/meetings/<date>.md`` into a :class:`BossMeeting`.

    Falls back to the filename stem (``YYYY-MM-DD``) when the frontmatter
    omits ``date`` — useful when the user creates the file but forgets to set
    the field. Body is kept verbatim.
    """
    from research_assistant.common.frontmatter import parse as parse_fm

    data, body = parse_fm(path)
    if "date" not in data:
        try:
            data["date"] = date.fromisoformat(Path(path).stem)
        except ValueError:
            pass
    data.setdefault("body", body)
    return BossMeeting.model_validate(data)


def to_agentdb_payload(entry: BossProfile | BossMeeting) -> dict:
    """Format a :class:`BossProfile` or :class:`BossMeeting` for ``memory_store``.

    Returns a flat metadata dict (long prose excluded) plus a ``kind``
    discriminator the indexer can use to route into ``project/boss/profile``
    vs. ``project/boss/meetings/<date>``.
    """
    if isinstance(entry, BossProfile):
        return {
            "kind": "boss_profile",
            "name": entry.name,
            "role": entry.role,
            "research_interests": list(entry.research_interests),
            "hot_buttons": list(entry.hot_buttons),
            "sore_spots": list(entry.sore_spots),
            "communication_style": entry.communication_style,
        }
    if isinstance(entry, BossMeeting):
        return {
            "kind": "boss_meeting",
            "date": entry.date.isoformat(),
            "topic": entry.topic,
            "mode": entry.mode,
            "mood": entry.mood,
            "action_items": list(entry.action_items),
        }
    raise TypeError(f"unsupported entry type: {type(entry).__name__}")
