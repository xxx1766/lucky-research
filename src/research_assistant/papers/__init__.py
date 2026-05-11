"""Helpers for the venue-rooted, multi-stage paper-output flow.

Owns path resolution, slug normalization, and stage-status reporting for
outputs/papers/<venue>/<direction>/. AgentDB context (project/paper-context)
is touched via the skill prompts directly — the two stubs below pin the
contract.
"""
from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path

from research_assistant.common.io import PAPERS_DIR

_VENUE_CLEAN = re.compile(r"[^A-Za-z0-9]+")
_DIRECTION_CLEAN = re.compile(r"[^a-z0-9]+")


def slugify_venue(name: str, year: int) -> str:
    """Build a `<Conf>-<YYYY>` slug. Strips non-alphanumerics from conf name."""
    cleaned = _VENUE_CLEAN.sub("", name)
    if not cleaned:
        raise ValueError(f"empty venue slug for name={name!r}")
    return f"{cleaned}-{year}"


def slugify_direction(name: str) -> str:
    """Build a kebab-case direction slug."""
    cleaned = _DIRECTION_CLEAN.sub("-", name.lower()).strip("-")
    if not cleaned:
        raise ValueError(f"empty direction slug for name={name!r}")
    return cleaned


def venue_path(venue_slug: str) -> Path:
    return PAPERS_DIR / venue_slug


def direction_path(venue_slug: str, direction_slug: str) -> Path:
    return venue_path(venue_slug) / direction_slug


@dataclass(frozen=True)
class StageStatus:
    has_expert: bool
    has_scout: bool
    has_focus: bool
    has_motivate: bool
    sections_written: int


def stage_status(direction_dir: Path) -> StageStatus:
    """Inspect a direction folder and report which stages are filled in."""
    scout_dir = direction_dir / "related-papers"
    sections_dir = direction_dir / "sections"
    return StageStatus(
        has_expert=(direction_dir / "expert.md").exists(),
        has_scout=scout_dir.is_dir() and any(scout_dir.glob("*.md")),
        has_focus=(direction_dir / "focused-problem.md").exists(),
        has_motivate=(direction_dir / "experiments" / "motivation.md").exists(),
        sections_written=(
            sum(1 for _ in sections_dir.glob("*.md")) if sections_dir.is_dir() else 0
        ),
    )


def current_context() -> tuple[str | None, str | None]:
    """Read project/paper-context from AgentDB.

    Returns (venue_slug, direction_slug). Not implemented in Python — the skill
    reads AgentDB via MCP and passes values explicitly to other helpers.
    """
    raise NotImplementedError("AgentDB context read pending real skill body")


def set_context(venue: str, direction: str | None) -> None:
    """Write project/paper-context to AgentDB. See `current_context`."""
    raise NotImplementedError("AgentDB context write pending real skill body")
