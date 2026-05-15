"""Slug helper for `/idea-check`.

Mirrors :func:`research_assistant.mentor.past_work.slugify` and
:func:`research_assistant.papers.slugify_direction` so an idea slug can later be
reused as a /paper direction slug without renaming.
"""
from __future__ import annotations

import re
import unicodedata

_SLUG_CLEAN = re.compile(r"[^a-z0-9]+")
_MAX_LEN = 64


def slugify(text: str) -> str:
    """Build a short kebab-case slug from free-form text.

    Strips diacritics, lowercases, collapses non-alphanumerics to ``-``, trims
    leading/trailing hyphens, and caps length at 64 chars on a word boundary.
    Raises ``ValueError`` when the input has no alphanumeric content.
    """
    if not text or not text.strip():
        raise ValueError("empty idea slug")
    # Strip diacritics so e.g. "Café-aware" → "cafe-aware"
    normalized = unicodedata.normalize("NFKD", text)
    ascii_only = "".join(c for c in normalized if not unicodedata.combining(c))
    cleaned = _SLUG_CLEAN.sub("-", ascii_only.lower()).strip("-")
    if not cleaned:
        raise ValueError(f"empty idea slug for text={text!r}")
    if len(cleaned) <= _MAX_LEN:
        return cleaned
    # Cut at the nearest hyphen boundary <= _MAX_LEN, fall back to hard cut.
    truncated = cleaned[:_MAX_LEN]
    last_hyphen = truncated.rfind("-")
    if last_hyphen > _MAX_LEN // 2:
        truncated = truncated[:last_hyphen]
    return truncated.rstrip("-")
