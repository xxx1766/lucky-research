"""VerificationReport — the source-level evidence-closure check for `/paper verify`.

Adapted from the *academic-reviser* discipline in
`github.com/joshua-zyy/academic-paper-writer`. ``/paper verify`` is distinct
from ``/paper review`` (which simulates a reviewer reading the rendered PDF):
verify runs a **three-pass, order-enforced** audit of the ``.tex`` source and
its evidence —

    Pass 1  Evidence   — every claim has support; numbers match experiment files.
    Pass 2  Argument   — peer-review risk questions; intro promises vs. results.
    Pass 3  Style      — only after Passes 1 & 2; structure + prose.

The order may not be skipped (no polishing prose before facts are checked). The
pass narrative is the model's job; this module owns the **typed ledger** the
passes fill in, the deterministic verdict, and persistence.

Debt classes (shared vocabulary with `placeholders.py`):

* hard (block a ``passed`` verdict): ``citation`` · ``evidence`` · ``prose`` ·
  ``consistency``
* soft (a pre-publication debt, does not block): ``figure``

The verdict is computed in code from the debt ledger + round number, so it is
not the model's whim:

* ``passed``  — no open hard debt (soft debts may remain).
* ``failed``  — open hard debt, round < ``MAX_VERIFY_ROUNDS``.
* ``blocked`` — open hard debt at the round cap → ``unresolvable``.
"""
from __future__ import annotations

from pathlib import Path
from typing import Literal

import yaml
from pydantic import BaseModel, ConfigDict, Field

DEBT_CLASSES: tuple[str, ...] = ("citation", "evidence", "figure", "consistency", "prose")
HARD_DEBTS: frozenset[str] = frozenset({"citation", "evidence", "prose", "consistency"})
SOFT_DEBTS: frozenset[str] = frozenset({"figure"})
PASS_ORDER: tuple[str, ...] = ("evidence", "argument", "style")
MAX_VERIFY_ROUNDS = 3

Verdict = Literal["passed", "failed", "blocked"]
Status = Literal["open", "closed"]


class DebtEntry(BaseModel):
    model_config = ConfigDict(extra="ignore")
    status: Status = "closed"
    note: str = ""


class ClaimEvidence(BaseModel):
    """One row of the Citation-to-Claim map (Pass 1)."""

    model_config = ConfigDict(extra="ignore")
    claim: str
    # e.g. "exp:weightlet-1@v1.2" | "cite:vaswani2017" | "REF_NEEDED" | "" (naked)
    evidence: str = ""
    verified: bool = False

    @property
    def is_naked(self) -> bool:
        """A claim with no evidence and not verified — the thing Pass 1 forbids."""
        return not self.verified and not self.evidence.strip()


class VerificationReport(BaseModel):
    model_config = ConfigDict(extra="ignore")

    section: str
    date: str                       # YYYY-MM-DD (passed in by the skill)
    round: int = Field(default=1, ge=1)
    verdict: Verdict = "failed"
    score: int = Field(ge=1, le=10)
    debts: dict[str, DebtEntry] = Field(default_factory=dict)
    claims: list[ClaimEvidence] = Field(default_factory=list)
    unresolvable: bool = False
    notes: str = ""                 # free-form three-pass narrative summary

    def open_debts(self) -> list[str]:
        return [c for c, e in self.debts.items() if e.status == "open"]

    def open_hard_debts(self) -> list[str]:
        return [c for c in self.open_debts() if c in HARD_DEBTS]

    def naked_claims(self) -> list[ClaimEvidence]:
        return [c for c in self.claims if c.is_naked]


def compute_verdict(debts: dict[str, str | DebtEntry], round_no: int) -> tuple[Verdict, bool]:
    """Deterministic verdict from the debt ledger + round number.

    Accepts either ``{class: "open"/"closed"}`` or ``{class: DebtEntry}``.
    Returns ``(verdict, unresolvable)``.
    """
    def _status(v: str | DebtEntry) -> str:
        return v.status if isinstance(v, DebtEntry) else v

    open_hard = [c for c, v in debts.items() if c in HARD_DEBTS and _status(v) == "open"]
    if not open_hard:
        return "passed", False
    if round_no >= MAX_VERIFY_ROUNDS:
        return "blocked", True
    return "failed", False


def finalize_verdict(report: VerificationReport) -> VerificationReport:
    """Return a copy of ``report`` with verdict + unresolvable set from its debts.

    The skill fills ``debts`` / ``score`` / ``claims`` / ``notes`` from the
    three passes; this stamps the verdict so it can't drift from the ledger.
    """
    verdict, unresolvable = compute_verdict(report.debts, report.round)
    return report.model_copy(update={"verdict": verdict, "unresolvable": unresolvable})


# ---------- serialization ----------


def report_to_markdown(report: VerificationReport, body: str | None = None) -> str:
    """YAML frontmatter (round-trip source) + a human-readable body."""
    data = report.model_dump(mode="json")
    frontmatter = yaml.safe_dump(data, sort_keys=False, allow_unicode=True).rstrip()
    rendered_body = body if body is not None else _render_body(report)
    return f"---\n{frontmatter}\n---\n\n{rendered_body}\n"


def report_from_markdown(text: str) -> VerificationReport:
    """Inverse of :func:`report_to_markdown` — parses frontmatter (body is informational)."""
    from research_assistant.common.frontmatter import _split

    split = _split(text)
    if split is None:
        raise ValueError("missing YAML frontmatter in verification-report markdown")
    data = yaml.safe_load(split[0]) or {}
    if not isinstance(data, dict):
        raise ValueError("verification-report frontmatter must be a YAML mapping")
    return VerificationReport.model_validate(data)


def _render_body(r: VerificationReport) -> str:
    lines: list[str] = [
        f"# Verification — {r.section} (round {r.round})",
        "",
        f"**Verdict:** {r.verdict}  ·  **Score:** {r.score}/10"
        + ("  ·  **UNRESOLVABLE**" if r.unresolvable else ""),
        "",
        "## Debt ledger",
        "",
    ]
    if r.debts:
        for cls in DEBT_CLASSES:
            entry = r.debts.get(cls)
            if entry is None:
                continue
            mark = "🔴 open" if entry.status == "open" else "🟢 closed"
            hard = " (hard)" if cls in HARD_DEBTS else " (soft)"
            line = f"- **{cls}**{hard}: {mark}"
            if entry.note:
                line += f" — {entry.note}"
            lines.append(line)
    else:
        lines.append("- _no debts recorded_")
    lines.append("")

    if r.claims:
        lines.append("## Claim → evidence map")
        lines.append("")
        for c in r.claims:
            tick = "✓" if c.verified else ("✗ NAKED" if c.is_naked else "…")
            ev = c.evidence or "_none_"
            lines.append(f"- [{tick}] {c.claim} → `{ev}`")
        lines.append("")

    if r.notes:
        lines.append("## Pass narrative")
        lines.append("")
        lines.append(r.notes)

    return "\n".join(lines).rstrip()


# ---------- persistence ----------


def reviews_dir(direction_dir: Path) -> Path:
    return Path(direction_dir) / "reviews"


def verify_report_path(direction_dir: Path, section: str, date: str) -> Path:
    """Collision-safe ``reviews/verify-<section>-<date>[-N].md`` path."""
    base = reviews_dir(direction_dir)
    stem = f"verify-{section}-{date}"
    candidate = base / f"{stem}.md"
    n = 2
    while candidate.exists():
        candidate = base / f"{stem}-{n}.md"
        n += 1
    return candidate


def write_verification_report(
    direction_dir: Path, report: VerificationReport, body: str | None = None
) -> Path:
    """Persist a report (verdict finalized) to a collision-safe path. Returns the path."""
    final = finalize_verdict(report)
    out = verify_report_path(direction_dir, final.section, final.date)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(report_to_markdown(final, body), encoding="utf-8")
    return out


def _iter_reports(direction_dir: Path):
    base = reviews_dir(direction_dir)
    if not base.is_dir():
        return
    for path in sorted(base.glob("verify-*.md")):
        try:
            report = report_from_markdown(path.read_text(encoding="utf-8"))
        except (ValueError, OSError):
            continue
        yield path, report


def read_latest_reports(direction_dir: Path) -> dict[str, VerificationReport]:
    """Latest verification report per section, keyed by section name.

    "Latest" = highest ``(date, round, filename)`` — deterministic and free of
    filesystem mtime, so tests are stable.
    """
    latest: dict[str, tuple[tuple[str, int, str], VerificationReport]] = {}
    for path, report in _iter_reports(direction_dir):
        key = (report.date, report.round, path.name)
        prev = latest.get(report.section)
        if prev is None or key > prev[0]:
            latest[report.section] = (key, report)
    return {section: rep for section, (_, rep) in latest.items()}


def verify_debt_counts(direction_dir: Path) -> tuple[int, int]:
    """``(prose, consistency)`` open-debt counts from the latest reports.

    Only the two *judgment* debt classes that no file scan can derive. The
    objective classes (citation / figure / evidence) are computed live by
    :func:`research_assistant.papers.debt_summary` from placeholders + cites.
    """
    prose = consistency = 0
    for report in read_latest_reports(direction_dir).values():
        open_set = set(report.open_debts())
        if "prose" in open_set:
            prose += 1
        if "consistency" in open_set:
            consistency += 1
    return prose, consistency


def collect_claims(direction_dir: Path) -> list[ClaimEvidence]:
    """All claim→evidence rows from the latest reports, in section order."""
    reports = read_latest_reports(direction_dir)
    rows: list[ClaimEvidence] = []
    for section in sorted(reports):
        rows.extend(reports[section].claims)
    return rows


def naked_claims(direction_dir: Path) -> list[ClaimEvidence]:
    """Claims with no evidence and not verified — the Pass-1 red flags."""
    return [c for c in collect_claims(direction_dir) if c.is_naked]
