"""Idea evaluation rubric for `/idea-check evaluate`.

Two axis families (value, feasibility), each scored 1-5; final verdict and
top-3 risks captured alongside. The dataclass is the source of truth; the
markdown is rendered from it so users can revise scores in plain text and the
file regenerates deterministically.
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


class IdeaEvaluation(BaseModel):
    """Scores + verdict for one idea."""

    value_scores: dict[str, int] = Field(default_factory=dict)
    feasibility_scores: dict[str, int] = Field(default_factory=dict)
    rationale: dict[str, str] = Field(default_factory=dict)
    verdict: Verdict = "pivot"
    top_risks: list[IdeaRisk] = Field(default_factory=list)

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
    return "\n".join(lines).rstrip() + "\n"
