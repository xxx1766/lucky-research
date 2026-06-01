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
from datetime import date

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
