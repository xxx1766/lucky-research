"""Past-work corpus helpers — schema + I/O + indexing contract.

Past work lives at ``inputs/past-work/<slug>.md`` as the source of truth: each
file has YAML frontmatter matching :class:`PastWorkEntry` plus a free markdown
body. The ``past-work-historian`` agent mirrors them into AgentDB namespace
``project/past-work/<slug>`` so it can semantically recall relevant prior work
during /paper direction discussions.

Slug convention matches ``research_assistant.papers.slugify_direction`` —
kebab-case English, non-alphanumerics collapsed to hyphens.
"""
from __future__ import annotations

import re
from pathlib import Path

from pydantic import BaseModel, Field

from research_assistant.common.io import PAST_WORK_DIR

_SLUG_CLEAN = re.compile(r"[^a-z0-9]+")


class PastWorkEntry(BaseModel):
    slug: str
    title: str
    year: int | None = None
    venue: str | None = None
    status: str | None = None  # published | unpublished | abandoned | in-progress
    tags: list[str] = Field(default_factory=list)
    links: list[str] = Field(default_factory=list)
    abstract: str | None = None
    what_i_learned: list[str] = Field(default_factory=list)
    body: str = ""


def slugify(title: str) -> str:
    """Build a kebab-case slug from a free-form title."""
    cleaned = _SLUG_CLEAN.sub("-", title.lower()).strip("-")
    if not cleaned:
        raise ValueError(f"empty past-work slug for title={title!r}")
    return cleaned


def list_entries() -> list[Path]:
    """Return all past-work markdown files (excluding underscore-prefixed scratches)."""
    if not PAST_WORK_DIR.is_dir():
        return []
    return sorted(
        p for p in PAST_WORK_DIR.glob("*.md") if not p.name.startswith("_")
    )


def parse_entry(path: Path) -> PastWorkEntry:
    """Parse a past-work markdown file (YAML frontmatter + body) into a PastWorkEntry.

    Not implemented yet — real body lands with the first real /past-work add or sync.
    """
    raise NotImplementedError("YAML frontmatter parsing pending real /past-work bodies")


def to_agentdb_payload(entry: PastWorkEntry) -> dict:
    """Format a PastWorkEntry for ``mcp__claude-flow__memory_store``."""
    raise NotImplementedError("AgentDB indexing payload pending real /past-work sync")
