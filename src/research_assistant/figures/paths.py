"""Path + slug + scope-cursor resolution for figure-tool.

The "scope" decision (paper vs experiment) is made by the skill MD by reading
AgentDB cursors (project/paper-context.current, project/experiment-context.current)
and calling :func:`resolve_scope` with the read values.
"""
from __future__ import annotations

import re
from pathlib import Path
from typing import Literal

from research_assistant.common.io import EXPERIMENTS_DIR, PAPERS_DIR

_SLUG_CLEAN = re.compile(r"[^a-z0-9]+")


class NoScopeError(RuntimeError):
    """Neither paper nor experiment cursor is set — user must run /paper venue or /experiment init."""


class AmbiguousScopeError(RuntimeError):
    """Both cursors set; caller must supply cli_scope to disambiguate."""


def slugify(title: str) -> str:
    cleaned = _SLUG_CLEAN.sub("-", title.lower()).strip("-")
    if not cleaned:
        raise ValueError(f"empty figure slug for title={title!r}")
    return cleaned


def paper_figures_dir(venue: str, direction: str) -> Path:
    return PAPERS_DIR / venue / direction / "figures"


def experiment_figures_dir(slug: str, *, version: str | None) -> Path:
    """Return the figures dir inside an experiment.

    With ``version`` (e.g. ``"v1.0"``) → ``repo/figures/<version>/``.
    Without it → ``repo/figures/_arch/`` — the fallback bucket for figures
    drafted *before* the first ``/experiment version add``. (The pseudocode
    twin, :func:`research_assistant.pseudocode.paths.experiment_algorithms_dir`,
    uses ``_unversioned/`` for the same semantic — the bucket names differ
    for historical reasons; both stay as-is to avoid silently relocating
    user data.)
    """
    base = EXPERIMENTS_DIR / slug / "repo" / "figures"
    return base / version if version else base / "_arch"


def resolve_scope(
    *,
    paper_ctx: tuple[str, str] | None,
    experiment_ctx: str | None,
    cli_scope: Literal["paper", "experiment"] | None,
) -> Literal["paper", "experiment"]:
    """Decide which scope a /figure new is targeting.

    paper_ctx     — (venue, direction) tuple if /paper cursor is set
    experiment_ctx — exp slug if /experiment cursor is set
    cli_scope     — explicit override from --scope (or step-0 answer)
    """
    if cli_scope is not None:
        if cli_scope not in ("paper", "experiment"):
            raise ValueError(f"cli_scope must be 'paper' or 'experiment', got {cli_scope!r}")
        return cli_scope
    if paper_ctx and experiment_ctx:
        raise AmbiguousScopeError(
            "Both /paper and /experiment cursors are set; ask the user which scope this figure belongs to."
        )
    if paper_ctx:
        return "paper"
    if experiment_ctx:
        return "experiment"
    raise NoScopeError(
        "No paper or experiment cursor is set. Run /paper venue or /experiment init first."
    )


def safe_join(base: Path, user_relative: str) -> Path:
    """Reject path traversal and absolute paths. Mirrors the experiments.py guard."""
    if user_relative.startswith("/") or user_relative.startswith("\\"):
        raise ValueError(f"absolute paths are not allowed: {user_relative!r}")
    resolved = (base / user_relative).resolve()
    base_resolved = base.resolve()
    try:
        resolved.relative_to(base_resolved)
    except ValueError as e:
        raise ValueError(f"path escapes base: {user_relative!r}") from e
    return resolved
