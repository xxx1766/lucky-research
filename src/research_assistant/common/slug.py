"""Kebab-case slug builder shared across mentor / figures / pseudocode / ideas.

The same 4-line `_SLUG_CLEAN.sub(...).strip("-")` body had been re-implemented in
five modules with identical semantics; centralising here removes the drift risk.
Module-specific augmentations (e.g. :mod:`research_assistant.ideas.slug` strips
diacritics and length-caps) wrap this helper rather than copy its body.
"""
from __future__ import annotations

import re

_SLUG_CLEAN = re.compile(r"[^a-z0-9]+")


def slugify(title: str, *, kind: str = "slug") -> str:
    """Build a kebab-case slug from free-form text.

    Lowercases, collapses runs of non-alphanumerics into a single ``-``, and
    trims hyphens from both ends. Raises ``ValueError`` (with ``kind`` in the
    message) when the input has no alphanumeric content.
    """
    cleaned = _SLUG_CLEAN.sub("-", title.lower()).strip("-")
    if not cleaned:
        raise ValueError(f"empty {kind} for title={title!r}")
    return cleaned
