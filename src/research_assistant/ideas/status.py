"""Stage tracker for one idea — reads the manifest + artifact directory,
renders a checkbox board.

Stage progression is driven by the manifest's ``status`` field (advanced by
``registry.update_idea``); the per-stage artifact files (``socratic.md``,
``scout.md``, ...) are secondary signals so a partially-rendered stage still
shows up as in-progress.
"""
from __future__ import annotations

from dataclasses import dataclass

from research_assistant.ideas.registry import (
    STATUS_ORDER,
    idea_dir,
    load_idea,
)

# (label, subcommand-to-resume, file artifact that signals "done")
_STAGES: tuple[tuple[str, str, str], ...] = (
    ("captured", "socratic", "socratic.md"),
    ("scouted", "scout", "scout.md"),
    ("evaluated", "evaluate", "evaluate.md"),
    ("venued", "venues", "venues.md"),
    ("knowledge-indexed", "knowledge", "knowledge.md"),
    ("handed-off", "handoff", ""),  # marked solely by manifest status
)


@dataclass(frozen=True)
class StageStatus:
    """Per-stage flags."""

    has_socratic: bool
    has_scout: bool
    has_evaluate: bool
    has_venues: bool
    has_knowledge: bool
    handed_off: bool


def stage_status(slug: str) -> StageStatus:
    d = idea_dir(slug)
    manifest_status: str | None = None
    try:
        manifest_status = load_idea(slug).status
    except (FileNotFoundError, ValueError, KeyError):
        # Treat malformed or missing manifest the same as "no manifest yet":
        # the on-disk artifacts still drive the checkbox board. Without this
        # widen, a single hand-edit that corrupts idea.md frontmatter would
        # crash `/idea-check status` instead of letting the user see and fix.
        pass

    def _at_or_past(stage_label: str) -> bool:
        if manifest_status is None:
            return False
        try:
            return STATUS_ORDER.index(manifest_status) >= STATUS_ORDER.index(stage_label)  # type: ignore[arg-type]
        except ValueError:
            return False

    return StageStatus(
        has_socratic=(d / "socratic.md").is_file() or _at_or_past("captured"),
        has_scout=(d / "scout.md").is_file() or _at_or_past("scouted"),
        has_evaluate=(d / "evaluate.md").is_file() or _at_or_past("evaluated"),
        has_venues=(d / "venues.md").is_file() or _at_or_past("venued"),
        has_knowledge=(d / "knowledge.md").is_file() or _at_or_past("knowledge-indexed"),
        handed_off=manifest_status == "handed-off",
    )


def render_status_md(slug: str) -> str:
    """Render the 6-stage checkbox board for ``outputs/idea-checks/<slug>/status.md``."""
    s = stage_status(slug)
    flags = (
        s.has_socratic, s.has_scout, s.has_evaluate,
        s.has_venues, s.has_knowledge, s.handed_off,
    )
    lines = [f"# Status — `{slug}`", ""]
    for (label, _sub, _file), done in zip(_STAGES, flags):
        mark = "x" if done else " "
        lines.append(f"- [{mark}] {label}")
    lines.append("")
    next_subcommand = next(
        (sub for (_label, sub, _f), done in zip(_STAGES, flags) if not done),
        None,
    )
    if next_subcommand:
        lines.append(f"_Next: `/idea-check {next_subcommand}`_")
    else:
        lines.append("_All stages complete — handed off to `/paper`._")
    return "\n".join(lines) + "\n"
