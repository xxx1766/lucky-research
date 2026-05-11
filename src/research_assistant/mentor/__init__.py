"""Research mentor: track research trajectory and surface path corrections.

Used by the `research-mentor` skill. Reads/writes the `project/` namespace in
AgentDB (via the claude-flow MCP `memory_store` / `memory_search` tools), keeping
goals, weekly check-ins, blockers, and decisions.

This module holds local helpers (diffing stated goals vs. recent activity, etc.).
The skill prompt itself talks to AgentDB; the helpers here are pure-Python so they
are easy to test offline.
"""

from datetime import date


def diff_goals(stated_goals: list[str], recent_activity: list[str]) -> dict:
    """Return {on_track: [...], drifting: [...], missing: [...]}. STUB."""
    raise NotImplementedError("mentor.diff_goals")


def weekly_checkin_template(today: date) -> str:
    """Return a markdown template for a weekly mentor check-in. STUB."""
    raise NotImplementedError("mentor.weekly_checkin_template")
