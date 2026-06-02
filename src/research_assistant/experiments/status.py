"""Stage status + progress rendering for the experiments package.

Reads file existence on disk to derive a 5-stage progress board
(``init -> scout -> design -> version -> analyze``). Uses cheap text
heuristics rather than YAML parsing — same policy as the legacy frontmatter
parser stubs so this can survive partial/malformed files.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

from .paths import (
    experiment_path,
    latest_feasibility,
    legacy_design_path,
    list_designs,
    list_versions,
    manifest_path,
    references_path,
    repo_clone_path,
)

_BAR_WIDTH = 5
_STAGES: tuple[str, ...] = ("init", "scout", "design", "version", "analyze")


@dataclass(frozen=True)
class ExperimentStatus:
    has_manifest: bool
    has_repo: bool
    has_papers_bound: bool
    has_references: bool
    has_design: bool
    has_clone: bool
    version_count: int
    last_version: str | None
    last_sync: datetime | None
    last_feasibility_check: datetime | None
    has_analysis: bool = False


def stage_status(slug: str) -> ExperimentStatus:
    """Inspect ``<slug>/`` on disk; tolerate every file/dir missing.

    Uses cheap text heuristics (``"url:"``, ``"papers:"``) rather than YAML
    parsing, matching the deferred-frontmatter-parser policy elsewhere.
    """
    exp_dir = experiment_path(slug)
    manifest = manifest_path(slug)
    has_manifest = manifest.is_file()
    has_repo = False
    has_papers_bound = False
    last_sync: datetime | None = None
    if has_manifest:
        text = manifest.read_text(errors="replace")
        has_repo = "url:" in text
        # papers: followed by at least one "  - " bullet inside a YAML block
        if "papers:" in text:
            tail = text.split("papers:", 1)[1].splitlines()[1:6]
            has_papers_bound = any(line.strip().startswith("- ") for line in tail)
        last_sync = datetime.fromtimestamp(manifest.stat().st_mtime)
    references = references_path(slug)
    has_references = references.is_file() and references.stat().st_size > 0
    # has_design: any file in designs/<dN.M>.md, or the legacy singleton.
    has_design = bool(list_designs(slug)) or legacy_design_path(slug).is_file()
    has_clone = repo_clone_path(slug).is_dir()
    versions = list_versions(slug) if exp_dir.is_dir() else []
    last_feasibility_check: datetime | None = None
    if exp_dir.is_dir():
        lf = latest_feasibility(slug)
        if lf and lf.is_file():
            last_feasibility_check = datetime.fromtimestamp(lf.stat().st_mtime)
    # has_analysis: did `/experiment analyze` produce analysis.{tex,md} for
    # the latest version? Bare `version_count >= 2` is a false positive — the
    # user can register two runs without ever invoking analyze.
    has_analysis = False
    if versions:
        from .paths import result_path  # local: avoid circular import at module load
        try:
            latest_results = result_path(slug, versions[-1])
        except Exception:  # noqa: BLE001 - tolerate semver/path edge cases
            latest_results = None
        if latest_results is not None and latest_results.is_dir():
            has_analysis = (
                (latest_results / "analysis.tex").is_file()
                or (latest_results / "analysis.md").is_file()
            )
    return ExperimentStatus(
        has_manifest=has_manifest,
        has_repo=has_repo,
        has_papers_bound=has_papers_bound,
        has_references=has_references,
        has_design=has_design,
        has_clone=has_clone,
        version_count=len(versions),
        last_version=versions[-1] if versions else None,
        last_sync=last_sync,
        last_feasibility_check=last_feasibility_check,
        has_analysis=has_analysis,
    )


def _stage_done(stage: str, s: ExperimentStatus) -> bool:
    if stage == "init":
        return s.has_manifest and s.has_repo
    if stage == "scout":
        # Scout is conditional: if no papers bound, it auto-completes (no work
        # to do). Stay "not done" before the manifest exists — we can't know
        # yet whether papers will be bound.
        if not s.has_manifest:
            return False
        return (not s.has_papers_bound) or s.has_references
    if stage == "design":
        return s.has_design
    if stage == "version":
        return s.version_count > 0
    if stage == "analyze":
        # Real check: did `/experiment analyze` actually produce analysis.tex
        # or analysis.md for the latest version? (Previously this was a bare
        # `version_count >= 2` heuristic — registering two runs without ever
        # running analyze would falsely mark the stage done.)
        return s.has_analysis
    raise ValueError(f"unknown stage: {stage}")


def _stage_partial(stage: str, s: ExperimentStatus) -> bool:
    if _stage_done(stage, s):
        return False
    if stage == "init":
        return s.has_manifest
    return False


def next_suggested(s: ExperimentStatus) -> str:
    if not s.has_manifest:
        return "/experiment init <title>"
    if not s.has_repo:
        return "/experiment init  (re-run; provide --repo)"
    if s.has_papers_bound and not s.has_references:
        return "/experiment scout"
    if not s.has_design:
        return "/experiment design"
    # Once design exists, pre-flight the fleet before the first run.
    if s.last_feasibility_check is None and s.version_count == 0:
        return "/experiment feasibility"
    if s.version_count == 0:
        return '/experiment version add v1.0 --description "..."'
    if s.version_count < 2:
        return "/experiment version add  (or /experiment analyze)"
    return "/experiment analyze"


def _progress_bar(s: ExperimentStatus) -> tuple[str, int]:
    done = sum(1 for st in _STAGES if _stage_done(st, s))
    return "#" * done + "-" * (_BAR_WIDTH - done), done


def render_progress_footer(slug: str | None, status: ExperimentStatus | None) -> str:
    """One-line footer printed at the end of every ``/experiment`` subcommand."""
    if not slug:
        return "── no current experiment · next: /experiment init <title> ──"
    if status is None:
        return f"── {slug} · next: /experiment init  (re-run) ──"
    bar, done = _progress_bar(status)
    return (
        f"── {slug}   [{bar}] {done}/{_BAR_WIDTH}   "
        f"next: {next_suggested(status)} ──"
    )


def _state_marker(stage: str, s: ExperimentStatus) -> str:
    if _stage_done(stage, s):
        return "[x]"
    if _stage_partial(stage, s):
        return "[.]"
    return "[ ]"


def _board_detail(stage: str, s: ExperimentStatus) -> str:
    if stage == "init":
        bits = ["manifest.md ok" if s.has_manifest else "manifest.md missing"]
        bits.append("repo set" if s.has_repo else "repo missing")
        if s.has_clone:
            bits.append("cloned")
        return " · ".join(bits)
    if stage == "scout":
        if s.has_references:
            return "references.md filled"
        if s.has_papers_bound:
            return "papers bound · run /experiment scout"
        return "no papers bound (optional)"
    if stage == "design":
        return "designs/ populated" if s.has_design else "designs/ empty"
    if stage == "version":
        if s.version_count == 0:
            return "no versions yet"
        return f"{s.version_count} version(s) · latest {s.last_version}"
    if stage == "analyze":
        return "ready to compare" if s.version_count >= 2 else "need ≥2 versions"
    raise ValueError(f"unknown stage: {stage}")


def render_progress_board(slug: str, status: ExperimentStatus) -> str:
    """Multi-line full board for ``/experiment status``."""
    bar, done = _progress_bar(status)
    lines = [slug, f"[{bar}] {done}/{_BAR_WIDTH} stages", ""]
    for i, stage in enumerate(_STAGES, start=1):
        lines.append(
            f"  {_state_marker(stage, status)} {i}. {stage:<10} "
            f"{_board_detail(stage, status)}"
        )
    if status.last_sync or status.last_feasibility_check:
        lines.append("")
        if status.last_sync:
            lines.append(f"Last sync:        {status.last_sync.isoformat(timespec='seconds')}")
        if status.last_feasibility_check:
            lines.append(
                f"Last feasibility: {status.last_feasibility_check.isoformat(timespec='seconds')}"
            )
    lines.append("")
    lines.append(f"Suggested next: {next_suggested(status)}")
    return "\n".join(lines)
