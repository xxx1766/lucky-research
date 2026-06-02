"""Slug helper for `/idea-check`.

Mirrors :func:`research_assistant.mentor.past_work.slugify` and
:func:`research_assistant.papers.slugify_direction` so an idea slug can later be
reused as a /paper direction slug without renaming. Adds two idea-specific
guarantees on top of :func:`research_assistant.common.slug.slugify`:

* strips diacritics (``"Café-aware"`` → ``"cafe-aware"``) so non-ASCII titles
  produce valid slugs,
* caps length at 64 chars on a hyphen boundary so a verbose Socratic capture
  doesn't yield a 200-char path component.
"""
from __future__ import annotations

import unicodedata

from research_assistant.common.slug import slugify as _slugify_base

_MAX_LEN = 64


def slugify(text: str) -> str:
    if not text or not text.strip():
        raise ValueError("empty idea slug")
    # Strip diacritics so e.g. "Café-aware" → "cafe-aware"
    normalized = unicodedata.normalize("NFKD", text)
    ascii_only = "".join(c for c in normalized if not unicodedata.combining(c))
    cleaned = _slugify_base(ascii_only, kind="idea slug")
    if len(cleaned) <= _MAX_LEN:
        return cleaned
    # Cut at the nearest hyphen boundary <= _MAX_LEN, fall back to hard cut.
    truncated = cleaned[:_MAX_LEN]
    last_hyphen = truncated.rfind("-")
    if last_hyphen > _MAX_LEN // 2:
        truncated = truncated[:last_hyphen]
    return truncated.rstrip("-")
