"""Idea evaluation rubric for `/idea-check evaluate`.

Two axis families (value, feasibility), each scored 1-5; final verdict and
top-3 risks captured alongside. The dataclass is the source of truth; the
markdown is rendered from it so users can revise scores in plain text and the
file regenerates deterministically.

Stage 3 also captures a **pre-registration** block (proxy metric + baseline +
target delta) adapted from Orchestra-Research/AI-Research-SKILLs (MIT)
`0-autoresearch-skill` Bootstrap step 4 — "lock evaluation criteria upfront to
prevent unconscious metric gaming". When the user later runs `/experiment
design`, that command reads ``ideas/<current>/evaluation`` from AgentDB and
pre-fills the design's Metrics table from the pre-registration block, so the
metric the experiment optimizes is the same metric the idea was scored on.
"""
from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field, field_validator

VALUE_AXES: tuple[str, ...] = (
    "novelty",
    "technical_depth",
    "empirical_impact",
    "theoretical_contribution",
    "audience_scope",
)
FEASIBILITY_AXES: tuple[str, ...] = (
    "data_availability",
    "compute_cost",
    "baseline_reproducibility",
    "expected_timeline_months",
    "risk_level",
)

Verdict = Literal["go", "pivot", "drop"]


class IdeaRisk(BaseModel):
    """One named risk + a one-line mitigation."""

    name: str
    mitigation: str


class PreRegistration(BaseModel):
    """Locked evaluation criteria for the idea before experiments run.

    Adapted from Orchestra-Research/AI-Research-SKILLs (MIT)
    ``0-autoresearch-skill`` Bootstrap step 4 ("set the proxy metric and
    baseline before running experiments"). Persisted at Stage 3 and read
    by ``/experiment design`` Stage 3 step 2 when the experiment is bound
    to this idea (via ``project/paper-context.current`` → idea slug).

    ``target_delta`` is intentionally a free-form string ("+10%", "+0.5 BLEU",
    "≥ 0.80") rather than a number — the success bar is qualitative until
    the experiment design pins it down.
    """

    proxy_metric: str = ""
    """What we'll measure. Computable in minutes, not hours."""

    baseline_value: float | None = None
    """The baseline number this idea aims to beat (if quantitative)."""

    baseline_source: str = ""
    """Where the baseline number comes from — paper, prior run, or convention."""

    target_delta: str = ""
    """What size of improvement would convince a reviewer. Free-form."""

    notes: str = ""
    """One-line caveat (e.g. "metric only meaningful on long-context inputs")."""


class IdeaEvaluation(BaseModel):
    """Scores + verdict for one idea."""

    value_scores: dict[str, int] = Field(default_factory=dict)
    feasibility_scores: dict[str, int] = Field(default_factory=dict)
    rationale: dict[str, str] = Field(default_factory=dict)
    verdict: Verdict = "pivot"
    top_risks: list[IdeaRisk] = Field(default_factory=list)
    pre_registration: PreRegistration | None = None

    @field_validator("value_scores", "feasibility_scores")
    @classmethod
    def _validate_scores(cls, v: dict[str, int]) -> dict[str, int]:
        for axis, score in v.items():
            if not isinstance(score, int) or not (1 <= score <= 5):
                raise ValueError(f"score for {axis!r} out of [1,5]: {score!r}")
        return v


def _score_table(label: str, axes: tuple[str, ...], scores: dict[str, int],
                 rationale: dict[str, str]) -> list[str]:
    lines = [f"### {label}", "", "| Axis | Score | Why |", "|---|---|---|"]
    for axis in axes:
        score = scores.get(axis, "—")
        why = rationale.get(axis, "").replace("\n", " ").strip() or "_(pending)_"
        lines.append(f"| {axis.replace('_', ' ')} | {score} | {why} |")
    lines.append("")
    return lines


def render_evaluate_md(ev: IdeaEvaluation) -> str:
    """Render the evaluation to ``outputs/idea-checks/<slug>/evaluate.md``."""
    lines: list[str] = ["# Evaluation", "", "## Value (1–5 each axis)", ""]
    lines.extend(_score_table("Value axes", VALUE_AXES, ev.value_scores, ev.rationale))
    lines.append("## Feasibility (1–5 each axis)")
    lines.append("")
    lines.extend(_score_table("Feasibility axes", FEASIBILITY_AXES,
                              ev.feasibility_scores, ev.rationale))
    lines.append("## Verdict")
    lines.append("")
    lines.append(f"**{ev.verdict.upper()}**")
    lines.append("")
    lines.append("## Top risks")
    lines.append("")
    if not ev.top_risks:
        lines.append("_(no risks captured yet)_")
    else:
        for i, risk in enumerate(ev.top_risks, start=1):
            lines.append(f"{i}. **{risk.name}** — {risk.mitigation}")
    lines.append("")
    lines.append("## Pre-registration")
    lines.append("")
    if ev.pre_registration is None:
        lines.append(
            "_Not yet locked. `/experiment design` will not be able to "
            "pre-fill the Metrics table from this idea until the proxy metric "
            "and baseline are set here._"
        )
    else:
        pr = ev.pre_registration
        lines.append("| Field | Value |")
        lines.append("|---|---|")
        lines.append(f"| Proxy metric | {pr.proxy_metric or '_(unset)_'} |")
        baseline_disp = (
            f"{pr.baseline_value}" if pr.baseline_value is not None else "_(unset)_"
        )
        lines.append(f"| Baseline value | {baseline_disp} |")
        lines.append(f"| Baseline source | {pr.baseline_source or '_(unset)_'} |")
        lines.append(f"| Target delta | {pr.target_delta or '_(unset)_'} |")
        if pr.notes:
            lines.append(f"| Notes | {pr.notes} |")
    lines.append("")
    return "\n".join(lines).rstrip() + "\n"


def to_experiment_metrics_seed(ev: IdeaEvaluation) -> dict | None:
    """Compact seed for ``/experiment design`` to pre-fill its Metrics table.

    Returns ``None`` when no pre-registration has been locked, so the
    experiment design stage can fall back to asking the user from scratch.
    """
    if ev.pre_registration is None:
        return None
    pr = ev.pre_registration
    if not (pr.proxy_metric or pr.baseline_value is not None or pr.target_delta):
        return None
    return {
        "metric": pr.proxy_metric,
        "baseline_value": pr.baseline_value,
        "baseline_source": pr.baseline_source,
        "target_delta": pr.target_delta,
        "notes": pr.notes,
    }
