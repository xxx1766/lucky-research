"""Path + slug + scope resolution for pseudocode-tool.

Delegates scope decision to `figures.paths.resolve_scope` so /pseudocode and
/figure share one source of truth on (NoScope, AmbiguousScope, paper, experiment).
"""
from __future__ import annotations

import re
from pathlib import Path
from typing import Literal

from research_assistant.common.io import EXPERIMENTS_DIR, PAPERS_DIR
from research_assistant.figures.paths import (
    AmbiguousScopeError,
    NoScopeError,
    resolve_scope as _resolve_scope_figures,
    safe_join,
)

__all__ = [
    "AmbiguousScopeError",
    "NoScopeError",
    "experiment_algorithms_dir",
    "paper_algorithms_dir",
    "resolve_scope",
    "safe_join",
    "slugify",
]

_SLUG_CLEAN = re.compile(r"[^a-z0-9]+")


def slugify(title: str) -> str:
    cleaned = _SLUG_CLEAN.sub("-", title.lower()).strip("-")
    if not cleaned:
        raise ValueError(f"empty algorithm slug for title={title!r}")
    return cleaned


def paper_algorithms_dir(venue: str, direction: str) -> Path:
    return PAPERS_DIR / venue / direction / "algorithms"


def experiment_algorithms_dir(slug: str, *, version: str | None) -> Path:
    """Return the algorithms directory inside an experiment.

    With ``version`` (e.g. ``"v1.0"``) → ``repo/algorithms/<version>/``.
    Without it → ``repo/algorithms/_unversioned/`` — the fallback for
    algorithms drafted *before* the first `/experiment version add`. Once
    the experiment has versioned runs, callers should always pass an
    explicit ``version``; ``_unversioned`` files stay where they were and
    can be moved manually if the user decides to retroactively pin them.
    """
    base = EXPERIMENTS_DIR / slug / "repo" / "algorithms"
    return base / version if version else base / "_unversioned"


def resolve_scope(
    *,
    paper_ctx: tuple[str, str] | None,
    experiment_ctx: str | None,
    cli_scope: Literal["paper", "experiment"] | None,
) -> Literal["paper", "experiment"]:
    """Decide which scope a /pseudocode new is targeting (shares logic with /figure)."""
    return _resolve_scope_figures(
        paper_ctx=paper_ctx,
        experiment_ctx=experiment_ctx,
        cli_scope=cli_scope,
    )
