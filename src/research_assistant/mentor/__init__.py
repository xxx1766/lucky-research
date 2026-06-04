"""Research mentor: track research trajectory and surface path corrections.

Used by the `research-mentor` skill. Reads/writes the `project/` namespace in
AgentDB (via the claude-flow MCP `memory_store` / `memory_search` tools), keeping
goals, weekly check-ins, blockers, and decisions.

This module holds local helpers (diffing stated goals vs. recent activity, etc.).
The skill prompt itself talks to AgentDB; the helpers here are pure-Python so they
are easy to test offline.
"""

from __future__ import annotations

import re
from datetime import date, datetime, timezone
from pathlib import Path

# Minimal English stopword list — enough to keep token-overlap meaningful for
# the kinds of phrases that appear in goal statements and activity log entries.
# Deliberately small; we want to keep domain vocabulary (e.g. "lora", "kv-cache").
_STOPWORDS: frozenset[str] = frozenset(
    {
        "a", "an", "and", "are", "as", "at", "be", "by", "do", "for", "from",
        "in", "is", "it", "of", "on", "or", "that", "the", "this", "to", "via",
        "with", "we", "i", "my", "our", "your", "their", "his", "her", "its",
        "but", "if", "so", "than", "then", "into", "over", "under", "about",
        "use", "using", "make", "made", "get", "got", "do", "doing", "done",
        "work", "working", "task", "todo", "tbd",
    }
)

_TOKEN = re.compile(r"[A-Za-z0-9][A-Za-z0-9_\-]+")


def _tokens(text: str) -> set[str]:
    """Lowercase content tokens, with stopwords + ≤2-char fluff dropped.

    Hyphens and underscores are kept inside a token (so ``kv-cache`` stays one
    token, ``LoRA`` becomes ``lora``). Stopwords are dropped after lowercasing.
    """
    if not text:
        return set()
    out: set[str] = set()
    for m in _TOKEN.findall(text):
        tok = m.lower()
        if len(tok) <= 2 or tok in _STOPWORDS:
            continue
        out.add(tok)
    return out


def diff_goals(
    stated_goals: list[str], recent_activity: list[str]
) -> dict[str, list[str]]:
    """Bucket each stated goal by how recent activity supports it.

    Returns a dict with three keys:

    - ``on_track`` — ≥2 distinct recent-activity entries share at least one
      meaningful (non-stopword, >2-char) token with the goal.
    - ``drifting`` — exactly 1 activity entry overlaps.
    - ``missing`` — no overlap; the goal looks neglected this period.

    Goals are returned in their original input order, with surrounding
    whitespace trimmed. Empty / whitespace-only goals are ignored entirely.

    The matcher is intentionally simple (token overlap, not embedding distance)
    so the helper is offline-testable. Callers wanting semantic recall layer
    that on top via AgentDB.
    """
    on_track: list[str] = []
    drifting: list[str] = []
    missing: list[str] = []

    activity_tokens = [_tokens(entry) for entry in recent_activity]

    for raw in stated_goals:
        goal = (raw or "").strip()
        if not goal:
            continue
        gtok = _tokens(goal)
        if not gtok:
            # Goal has no content tokens — treat as missing rather than crash.
            missing.append(goal)
            continue
        hits = sum(1 for atok in activity_tokens if atok & gtok)
        if hits >= 2:
            on_track.append(goal)
        elif hits == 1:
            drifting.append(goal)
        else:
            missing.append(goal)

    return {"on_track": on_track, "drifting": drifting, "missing": missing}


_STALE_INCLUDED_STATUSES: frozenset[str] = frozenset({"active"})


def stale_experiments(
    min_age_days: int = 14,
    *,
    today: date | None = None,
) -> list[dict]:
    """Return active experiments with no new version in ``min_age_days`` days.

    Used by the weekly check-in to surface trajectory drift — a goal can look
    on-track in the activity log while the corresponding experiment hasn't had
    a version added in weeks. The "freshness" signal is the most recent
    ``versions/<vN.M>.md`` mtime; if no versions exist, ``manifest.md`` mtime
    is the fallback (a long-uninitialized experiment is just as much a drift
    signal as a stalled one).

    Experiments with status ``paused`` / ``archived`` / ``abandoned`` are
    excluded — they're intentionally idle, not drifting. ``planned``
    experiments are also excluded (they haven't started; surfacing them as
    stale would be noise).

    Each returned dict carries ``slug``, ``title``, ``status``,
    ``latest_version`` (or ``None``), and ``days_since_update``. Sorted by
    ``days_since_update`` descending (oldest first) so the most-stale
    experiment leads the check-in.

    ``today`` is injectable for deterministic tests; defaults to
    ``date.today()`` in UTC.
    """
    # Lazy imports: avoid a circular dependency at module import time —
    # ``research_assistant.experiments`` doesn't import mentor, but we want
    # mentor's other helpers (diff_goals, template) to be importable without
    # paying the experiments-package import cost.
    from pydantic import ValidationError
    from research_assistant.experiments import (
        EXPERIMENTS_DIR,
        list_experiments,
        list_versions,
        parse_experiment,
        version_path,
    )

    if not EXPERIMENTS_DIR.is_dir():
        return []
    reference = today or datetime.now(timezone.utc).date()
    out: list[dict] = []
    for manifest in list_experiments():
        try:
            exp = parse_experiment(manifest)
        except (ValidationError, ValueError, OSError):
            continue
        if exp.status not in _STALE_INCLUDED_STATUSES:
            continue
        versions = list_versions(exp.slug)
        if versions:
            latest = versions[-1]
            signal_path: Path = version_path(exp.slug, latest)
        else:
            latest = None
            signal_path = manifest
        try:
            mtime = signal_path.stat().st_mtime
        except OSError:
            continue
        last_update = datetime.fromtimestamp(mtime, tz=timezone.utc).date()
        age = (reference - last_update).days
        if age < min_age_days:
            continue
        out.append({
            "slug": exp.slug,
            "title": exp.title,
            "status": exp.status,
            "latest_version": latest,
            "days_since_update": age,
        })
    return sorted(out, key=lambda h: (-h["days_since_update"], h["slug"]))


def weekly_checkin_template(today: date) -> str:
    """Return a markdown skeleton for a weekly mentor check-in.

    Sections mirror the `research-mentor` skill's check-in flow: goal-vs-activity
    diff, decisions logged, blockers, mood, and the next-week plan. The
    front-matter carries the date so downstream tools (``mentor diff_goals``
    re-runs, retros) can locate the entry without parsing the filename.
    """
    iso = today.isoformat()
    return (
        f"---\n"
        f"date: {iso}\n"
        f"kind: weekly-checkin\n"
        f"---\n"
        f"\n"
        f"# Weekly check-in — {iso}\n"
        f"\n"
        f"## Goals vs. activity\n"
        f"\n"
        f"_Run `mentor.diff_goals(goals, recent_activity)` and paste the bucketed result._\n"
        f"\n"
        f"- ✅ On track:\n"
        f"- ⚠️ Drifting:\n"
        f"- ❌ Missing:\n"
        f"\n"
        f"## Stale experiments\n"
        f"\n"
        f"_Run `mentor.stale_experiments(min_age_days=14)` and paste anything returned._\n"
        f"\n"
        f"- ⏳ \n"
        f"\n"
        f"## Done this week\n"
        f"\n"
        f"- \n"
        f"\n"
        f"## Blockers\n"
        f"\n"
        f"- \n"
        f"\n"
        f"## Decisions logged\n"
        f"\n"
        f"_Reference `project/decisions/<slug>` entries created this week._\n"
        f"\n"
        f"- \n"
        f"\n"
        f"## Mood / energy\n"
        f"\n"
        f"_1 (drained) – 5 (charged). One sentence on why._\n"
        f"\n"
        f"- Score: \n"
        f"- Why: \n"
        f"\n"
        f"## Next week\n"
        f"\n"
        f"_Top 1–3 things. Each tied to a stated goal._\n"
        f"\n"
        f"- [ ] \n"
        f"- [ ] \n"
        f"- [ ] \n"
    )


# Re-export submodules so the attribute form documented across the skills /
# agents (``mentor.past_work.X``, ``mentor.research_notes.X``,
# ``mentor.boss_profile.X``) resolves in a fresh process without the caller
# first importing the submodule. Placed at the bottom so the helpers above are
# already defined when the submodules load.
from research_assistant.mentor import (  # noqa: E402,F401
    boss_profile,
    past_work,
    past_work_capture,
    research_notes,
)
