"""Helpers for the venue-rooted, multi-stage paper-output flow.

Owns path resolution, slug normalization, stage-status reporting, and the
terminal progress visualizers (footer + full board) consumed by the
`paper-architect` skill. AgentDB context (project/paper-context) is touched
via the skill prompts directly — the two stubs at the bottom pin the contract.
"""
from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path

from research_assistant.common.io import PAPERS_DIR

_VENUE_CLEAN = re.compile(r"[^A-Za-z0-9]+")
_VENUE_TRAILING_YEAR = re.compile(r"[\s\-_/]*(?:19|20)\d{2}\s*$")
_DIRECTION_CLEAN = re.compile(r"[^a-z0-9]+")
_BIB_ENTRY = re.compile(r"^\s*@\w+\s*\{", re.MULTILINE)

_BAR_WIDTH = 7
_STAGES: tuple[str, ...] = (
    "venue",
    "direction",
    "scout",
    "focus",
    "motivate",
    "write",
    "render",
)


def slugify_venue(name: str, year: int) -> str:
    """Build a `<Conf>-<YYYY>` slug. Strips non-alphanumerics from conf name.

    A trailing year in ``name`` (e.g. ``"ICLR 2026"``) is removed before
    slugifying so the result stays single-year (``"ICLR-2026"`` rather than
    ``"ICLR2026-2026"``).
    """
    stripped = _VENUE_TRAILING_YEAR.sub("", name)
    cleaned = _VENUE_CLEAN.sub("", stripped)
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


def tex_files(direction_dir: Path) -> list[Path]:
    """List drafted LaTeX sections under `<direction>/sections/`. Empty if absent."""
    sections_dir = direction_dir / "sections"
    if not sections_dir.is_dir():
        return []
    return sorted(sections_dir.glob("*.tex"))


def _count_bib_entries(refs_bib: Path) -> int:
    if not refs_bib.is_file():
        return 0
    try:
        text = refs_bib.read_text(errors="replace")
    except OSError:
        return 0
    return len(_BIB_ENTRY.findall(text))


@dataclass(frozen=True)
class StageStatus:
    has_expert: bool
    has_scout: bool
    has_focus: bool
    has_motivate: bool
    has_benchmark: bool
    has_outline: bool
    has_main_tex: bool
    has_pdf: bool
    has_refs: bool
    sections_written: int
    refs_entries: int


def stage_status(direction_dir: Path) -> StageStatus:
    """Inspect a direction folder and report which stages are filled in."""
    scout_dir = direction_dir / "related-papers"
    refs_bib = direction_dir / "refs.bib"
    refs_nonempty = refs_bib.is_file() and refs_bib.stat().st_size > 0
    return StageStatus(
        has_expert=(direction_dir / "expert.md").exists(),
        has_scout=scout_dir.is_dir() and any(scout_dir.glob("*.md")),
        has_focus=(direction_dir / "focused-problem.md").exists(),
        has_motivate=(direction_dir / "experiments" / "motivation.md").exists(),
        has_benchmark=(direction_dir / "experiments" / "benchmark.md").exists(),
        has_outline=(direction_dir / "outline.md").exists(),
        has_main_tex=(direction_dir / "main.tex").exists(),
        has_pdf=(direction_dir / "main.pdf").exists(),
        has_refs=refs_nonempty,
        sections_written=len(tex_files(direction_dir)),
        refs_entries=_count_bib_entries(refs_bib),
    )


# ---------- progress rendering ----------

def _stage_done(stage: str, status: StageStatus) -> bool:
    """Return True if a stage's required artifacts are all present."""
    if stage == "venue":
        return True  # caller resolved a direction → venue must exist
    if stage == "direction":
        return status.has_expert
    if stage == "scout":
        return status.has_scout
    if stage == "focus":
        return status.has_focus
    if stage == "motivate":
        return status.has_motivate and status.has_benchmark
    if stage == "write":
        return status.has_main_tex and status.sections_written > 0
    if stage == "render":
        return status.has_pdf
    raise ValueError(f"unknown stage: {stage}")


def _stage_partial(stage: str, status: StageStatus) -> bool:
    """Return True if a stage has some but not all of its artifacts."""
    if _stage_done(stage, status):
        return False
    if stage == "motivate":
        return status.has_motivate or status.has_benchmark
    if stage == "write":
        return status.has_outline or status.has_main_tex or status.sections_written > 0
    return False


def next_suggested(status: StageStatus) -> str:
    """Return the recommended next slash-command for a direction."""
    if not status.has_expert:
        return "/paper direction <slug>"
    if not status.has_scout:
        return "/paper scout"
    if not status.has_focus:
        return "/paper focus"
    if not (status.has_motivate and status.has_benchmark):
        return "/paper motivate"
    if not status.has_outline or not status.has_main_tex:
        return "/paper write"
    if status.sections_written == 0:
        return "/paper write intro"
    if not status.has_pdf:
        return "/paper render"
    if status.refs_entries == 0:
        return "/cite"
    return "all stages complete — ready to submit"


def _progress_bar(status: StageStatus) -> tuple[str, int]:
    done = sum(1 for s in _STAGES if _stage_done(s, status))
    bar = "#" * done + "-" * (_BAR_WIDTH - done)
    return bar, done


def render_progress_footer(
    venue: str | None,
    direction: str | None,
    status: StageStatus | None,
    debts: DebtSummary | None = None,
) -> str:
    """One-line progress footer printed at the end of every /paper subcommand.

    ``debts`` is optional — stages that have already resolved the direction
    (``write`` / ``verify`` / ``status``) may pass
    ``papers.debt_summary(direction_dir)`` to surface open debts inline.
    """
    if not venue:
        return "── no current paper · next: /paper venue <slug> ──"
    if direction is None or status is None:
        return f"── {venue} · venue set{_venue_refs_suffix(venue)} · next: /paper direction <slug> ──"
    bar, done = _progress_bar(status)
    debt_seg = ""
    if debts is not None and debts.total:
        debt_seg = f"⚠ {debts.total} debt{'s' if debts.total != 1 else ''}   "
    return (
        f"── {venue} / {direction}   "
        f"[{bar}] {done}/{_BAR_WIDTH}   "
        f"{debt_seg}"
        f"next: {next_suggested(status)} ──"
    )


def _venue_refs_suffix(venue: str) -> str:
    """Lazy-import the venue-refs summary; return ' · N refs[ · conventions distilled]' or ''."""
    try:
        from research_assistant.papers.venue_refs import venue_refs_summary
        summary = venue_refs_summary(venue)
    except (ImportError, OSError):
        return ""
    if summary is None or summary.count == 0:
        return ""
    base = f" · {summary.count} ref{'s' if summary.count != 1 else ''}"
    return f"{base} · conventions distilled" if summary.distilled else base


def _state_marker(stage: str, status: StageStatus) -> str:
    if _stage_done(stage, status):
        return "[x]"
    if _stage_partial(stage, status):
        return "[.]"
    return "[ ]"


def _board_detail(stage: str, status: StageStatus) -> str:
    if stage == "venue":
        return "venue dir present"
    if stage == "direction":
        return "expert.md ok" if status.has_expert else "expert.md missing"
    if stage == "scout":
        return "related-papers/ present" if status.has_scout else "related-papers/ empty"
    if stage == "focus":
        return "focused-problem.md" if status.has_focus else "focused-problem.md missing"
    if stage == "motivate":
        return " · ".join([
            "motivation.md" if status.has_motivate else "motivation.md missing",
            "benchmark.md" if status.has_benchmark else "benchmark.md missing",
        ])
    if stage == "write":
        section_word = "section" if status.sections_written == 1 else "sections"
        return " · ".join([
            "outline.md" if status.has_outline else "outline.md missing",
            f"{status.sections_written} {section_word}",
            "main.tex" if status.has_main_tex else "main.tex missing",
        ])
    if stage == "render":
        return "main.pdf ok" if status.has_pdf else "main.pdf missing"
    raise ValueError(f"unknown stage: {stage}")


def render_progress_board(
    venue: str,
    direction: str,
    status: StageStatus,
    debts: DebtSummary | None = None,
) -> str:
    """Multi-line full board for /paper status.

    When ``debts`` is supplied (``papers.debt_summary(direction_dir)``) a debt
    sidebar line is shown alongside the ``cite`` line. The line never starts
    with a ``[x]``/``[.]``/``[ ]`` marker, so it does not count as a stage row.
    """
    bar, done = _progress_bar(status)
    lines = [
        f"{venue} / {direction}",
        f"[{bar}] {done}/{_BAR_WIDTH} stages",
        "",
    ]
    for i, stage in enumerate(_STAGES, start=1):
        marker = _state_marker(stage, status)
        lines.append(f"  {marker} {i}. {stage:<10} {_board_detail(stage, status)}")
    cite_indent = " " * len("  [x] 1. ")
    cite_detail = (
        f"refs.bib: {status.refs_entries} entries"
        if status.refs_entries
        else "refs.bib: 0 entries  ← /cite to populate"
    )
    lines.append(f"{cite_indent}{'cite':<10} {cite_detail}")
    if debts is not None:
        debt_detail = (
            debts.as_line()
            if debts.total
            else "none ✓"
        )
        lines.append(f"{cite_indent}{'debts':<10} {debt_detail}")
    lines.append("")
    lines.append(f"Suggested next: {next_suggested(status)}")
    return "\n".join(lines)


_CURSOR_NS = "project/paper-context"
_CURSOR_KEY = "current"


def current_context() -> tuple[str | None, str | None]:
    """Read project/paper-context from AgentDB.

    By-design Python stub: the cursor lives in AgentDB and the skill reads it
    via MCP (``mcp__claude-flow__memory_retrieve``) before calling other
    helpers. No Python caller should hit this; the function exists only to
    anchor the docstring contract for skill authors.

    The error message names the exact MCP call and the agentic-flow CLI
    equivalent so a stuck Python REPL / test session can still inspect what
    cursor is set without bouncing into a skill.
    """
    raise RuntimeError(
        "current_context is intentionally Python-stubbed — the cursor lives "
        "in AgentDB. Read it from:\n"
        f"  - inside a skill: mcp__claude-flow__memory_retrieve(namespace='{_CURSOR_NS}', key='{_CURSOR_KEY}')\n"
        f"  - from the shell: npx @claude-flow/cli@latest memory retrieve "
        f"--namespace {_CURSOR_NS} --key {_CURSOR_KEY}"
    )


def set_context(venue: str, direction: str | None) -> None:
    """Write project/paper-context to AgentDB. See :func:`current_context`."""
    raise RuntimeError(
        "set_context is intentionally Python-stubbed — the cursor lives in "
        "AgentDB. Write it from:\n"
        f"  - inside a skill: mcp__claude-flow__memory_store(namespace='{_CURSOR_NS}', "
        f"key='{_CURSOR_KEY}', value={{'venue': {venue!r}, 'direction': {direction!r}}})\n"
        f"  - from the shell: npx @claude-flow/cli@latest memory store "
        f"--namespace {_CURSOR_NS} --key {_CURSOR_KEY} "
        f"--value '{{\"venue\": {venue!r}, \"direction\": {direction!r}}}'"
    )


# ---------- binding re-exports ----------

# Lazy imports avoid a circular import: binding.py imports from
# `research_assistant.papers` (this module) for path helpers, so we re-export
# after this module finishes defining them.
from research_assistant.papers.archive import (  # noqa: E402
    ArchiveError,
    ArchivedPaper,
    ArchiveResult,
    archive_direction,
    list_archived,
    unarchive_direction,
)
from research_assistant.papers.binding import (  # noqa: E402
    AlreadyBoundError,
    BindError,
    BindingResult,
    ConflictError,
    DivergedError,
    NotBoundError,
    SyncResult,
    bind,
    is_bound,
    read_binding_from_expert_md,
    restore,
    sync,
    unbind,
)
from research_assistant.papers.related_experiments import (  # noqa: E402
    collect_experiment_results_for_paper,
    find_experiments_for_paper,
)
from research_assistant.papers.venue_family import (  # noqa: E402
    family_for_venue,
)
from research_assistant.papers.venue_conventions import (  # noqa: E402
    VenueRefAnalysis,
)
from research_assistant.papers.venue_refs import (  # noqa: E402
    VenueRefEntry,
    VenueRefsSummary,
    distill_venue_conventions,
    ingest_venue_ref,
    list_venue_refs,
    slugify_paper_ref,
    venue_ref_path,
    venue_refs_dir,
    venue_refs_summary,
)
from research_assistant.papers.placeholders import (  # noqa: E402
    DEBT_BY_TOKEN,
    DebtSummary,
    Placeholder,
    debt_summary,
    scan_placeholders,
)
from research_assistant.papers.claim_strength import (  # noqa: E402
    STRENGTH_RULES,
    StrengthHit,
    scan_strength_words,
)
from research_assistant.papers.preflight import (  # noqa: E402
    GateCheck,
    PreflightResult,
    write_preflight,
)
from research_assistant.papers.verification import (  # noqa: E402
    MAX_VERIFY_ROUNDS,
    PASS_ORDER,
    ClaimEvidence,
    DebtEntry,
    VerificationReport,
    collect_claims,
    compute_verdict,
    finalize_verdict,
    naked_claims,
    read_latest_reports,
    report_from_markdown,
    report_to_markdown,
    verify_debt_counts,
    write_verification_report,
)

__all__ = [
    "AlreadyBoundError",
    "ArchiveError",
    "ArchivedPaper",
    "ArchiveResult",
    "BindError",
    "BindingResult",
    "ConflictError",
    "DEBT_BY_TOKEN",
    "ClaimEvidence",
    "DebtEntry",
    "DebtSummary",
    "DivergedError",
    "GateCheck",
    "MAX_VERIFY_ROUNDS",
    "NotBoundError",
    "PASS_ORDER",
    "Placeholder",
    "PreflightResult",
    "STRENGTH_RULES",
    "StrengthHit",
    "SyncResult",
    "VerificationReport",
    "VenueRefAnalysis",
    "VenueRefEntry",
    "VenueRefsSummary",
    "archive_direction",
    "bind",
    "collect_claims",
    "collect_experiment_results_for_paper",
    "compute_verdict",
    "debt_summary",
    "distill_venue_conventions",
    "family_for_venue",
    "finalize_verdict",
    "find_experiments_for_paper",
    "ingest_venue_ref",
    "is_bound",
    "list_archived",
    "list_venue_refs",
    "naked_claims",
    "read_binding_from_expert_md",
    "read_latest_reports",
    "report_from_markdown",
    "report_to_markdown",
    "restore",
    "scan_placeholders",
    "scan_strength_words",
    "slugify_paper_ref",
    "sync",
    "unarchive_direction",
    "unbind",
    "venue_ref_path",
    "venue_refs_dir",
    "venue_refs_summary",
    "verify_debt_counts",
    "write_preflight",
    "write_verification_report",
]
