"""Write-stage preflight gates for ``/paper write``.

Adapted from the *hard gate* discipline in
`joshua-zyy/academic-paper-writer`: a section may not be drafted until its
prerequisites exist on disk. We keep the gates deliberately small and split
them into two strengths:

* **blocking** — drafting is refused (the user runs the named fix command, or
  passes ``--force`` to override). Examples: no ``_venue.md``; no
  ``focused-problem.md``; an ``intro`` / ``related-work`` section with no
  scouted literature.
* **warning** — drafting proceeds, but the user is reminded to keep the
  evidence-first contract. Example: a ``results`` section with no experiment
  result yet — allowed, but every reported number must use a ``[DATA_NEEDED]``
  placeholder until ``/experiment version add`` lands a real value.

The function is pure and path-based so it can be unit-tested against a mock
filesystem; the skill resolves ``(venue, direction)`` to the two directories
and (optionally) computes ``evidence_present`` from the bound experiments.
"""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from research_assistant.common import frontmatter

# Resolved section kinds (post synonym-map) that depend on scouted literature.
LITERATURE_KINDS: frozenset[str] = frozenset(
    {"intro", "introduction", "related", "related-work", "relatedwork", "background"}
)
# Resolved section kinds that report empirical results.
RESULTS_KINDS: frozenset[str] = frozenset(
    {"results", "result", "evaluation", "eval", "experiments"}
)


@dataclass(frozen=True)
class GateCheck:
    """One preflight gate result."""

    name: str
    passed: bool
    blocking: bool
    reason: str = ""      # why it failed ("" when passed)
    fix_hint: str = ""    # the command / action that clears it


@dataclass(frozen=True)
class PreflightResult:
    section_kind: str | None
    checks: tuple[GateCheck, ...]

    @property
    def blocked(self) -> bool:
        return any(not c.passed and c.blocking for c in self.checks)

    @property
    def failures(self) -> list[GateCheck]:
        return [c for c in self.checks if not c.passed and c.blocking]

    @property
    def warnings(self) -> list[GateCheck]:
        return [c for c in self.checks if not c.passed and not c.blocking]

    def render(self) -> str:
        """Human-readable gate report for the skill to print verbatim."""
        if not self.failures and not self.warnings:
            return "preflight ok — all gates pass."
        lines: list[str] = []
        if self.failures:
            lines.append("⛔ blocked — fix before drafting (or re-run with --force):")
            for c in self.failures:
                lines.append(f"  • {c.name}: {c.reason}")
                if c.fix_hint:
                    lines.append(f"      → {c.fix_hint}")
        if self.warnings:
            lines.append("⚠ warnings (drafting allowed):")
            for c in self.warnings:
                lines.append(f"  • {c.name}: {c.reason}")
                if c.fix_hint:
                    lines.append(f"      → {c.fix_hint}")
        return "\n".join(lines)


def _has_scouted_literature(direction_dir: Path) -> bool:
    scout_dir = direction_dir / "related-papers"
    return scout_dir.is_dir() and any(scout_dir.glob("*.md"))


def _literature_exempt(direction_dir: Path) -> bool:
    expert = direction_dir / "expert.md"
    if not expert.is_file():
        return False
    try:
        data, _ = frontmatter.parse_optional(expert)
    except (ValueError, OSError):
        return False
    return bool(data and data.get("literature_exempt"))


def _has_results_on_disk(direction_dir: Path) -> bool:
    results_dir = direction_dir / "experiments" / "results"
    return results_dir.is_dir() and any(results_dir.iterdir())


def write_preflight(
    direction_dir: Path,
    venue_dir: Path,
    section_kind: str | None,
    *,
    evidence_present: bool | None = None,
) -> PreflightResult:
    """Evaluate the write gates for one section (or the outline scaffold).

    Parameters
    ----------
    direction_dir
        ``outputs/papers/<venue>/<direction>/``.
    venue_dir
        ``outputs/papers/<venue>/`` — holds ``_venue.md``.
    section_kind
        The resolved section kind (``intro`` / ``method`` / ``results`` / …),
        or ``None`` for the first ``/paper write`` call that scaffolds the
        outline.
    evidence_present
        Optional override for the evidence gate. When the skill has already
        called ``collect_experiment_results_for_paper`` it passes the boolean
        directly; when ``None`` the gate falls back to an on-disk check of
        ``experiments/results/``.
    """
    direction_path = Path(direction_dir)
    venue_path = Path(venue_dir)
    kind = section_kind.lower() if section_kind else None
    checks: list[GateCheck] = []

    # G1 — venue brief must exist (always blocking).
    has_venue = (venue_path / "_venue.md").is_file()
    checks.append(
        GateCheck(
            name="venue",
            passed=has_venue,
            blocking=True,
            reason="" if has_venue else "_venue.md is missing for this venue",
            fix_hint="" if has_venue else "/paper venue <slug>",
        )
    )

    # G2 — focused problem must exist (always blocking).
    has_focus = (direction_path / "focused-problem.md").is_file()
    checks.append(
        GateCheck(
            name="focus",
            passed=has_focus,
            blocking=True,
            reason="" if has_focus else "focused-problem.md is missing",
            fix_hint="" if has_focus else "/paper focus",
        )
    )

    # G3 — literature sections need scouted refs (blocking, with exempt escape).
    if kind in LITERATURE_KINDS:
        ok = _has_scouted_literature(direction_path) or _literature_exempt(direction_path)
        checks.append(
            GateCheck(
                name="literature",
                passed=ok,
                blocking=True,
                reason=(
                    ""
                    if ok
                    else "no scouted papers in related-papers/ and expert.md "
                    "has no `literature_exempt: true`"
                ),
                fix_hint=(
                    ""
                    if ok
                    else "/paper scout  (or set `literature_exempt: true` in expert.md)"
                ),
            )
        )

    # G4 — results sections want evidence (warning only; falls back to disk).
    if kind in RESULTS_KINDS:
        present = (
            evidence_present
            if evidence_present is not None
            else _has_results_on_disk(direction_path)
        )
        checks.append(
            GateCheck(
                name="evidence",
                passed=present,
                blocking=False,
                reason=(
                    ""
                    if present
                    else "no experiment result bound yet — report numbers as "
                    "[DATA_NEEDED: …] until a version lands"
                ),
                fix_hint="" if present else "/experiment version add",
            )
        )

    return PreflightResult(section_kind=section_kind, checks=tuple(checks))
