"""Socratic discussion trace for `/idea-check`.

Captures the multi-turn Q&A and the distilled idea statement so the markdown
file is auditable and re-renderable from the trace.

Stage 1 Round 3 ("gap + claim") collects a **hypothesis tree** (H1 root +
optional H1.1/H1.2 sub-hypotheses) — adapted from
Orchestra-Research/AI-Research-SKILLs (MIT) ``0-autoresearch-skill``
Bootstrap step 3 ("form testable hypotheses with clear predictions"). The
tree is persisted in :attr:`SocraticTrace.hypotheses` and surfaced verbatim
to ``/experiment design`` Stage 3 step 2 so the design's ``## Hypothesis``
section starts pre-filled when the experiment is bound to an idea.
"""
from __future__ import annotations

import re
from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field, field_validator


_HYP_ID_RE = re.compile(r"^H\d+(?:\.\d+)*$")


class Hypothesis(BaseModel):
    """One node in the Stage-1 hypothesis tree.

    The shape is a deliberate subset of the richer
    :class:`research_assistant.mentor.research_notes.Hypothesis` — at idea
    capture time we don't yet have ``supported``/``refuted`` status; that's a
    post-experiment annotation. Predictions are encouraged but optional, and
    ``parent`` is derived from the dotted ID convention rather than stored
    twice (``H1.1`` implies parent ``H1``).
    """

    id: str
    statement: str
    prediction: str = ""
    priority: Literal["high", "medium", "low"] = "medium"

    @field_validator("id")
    @classmethod
    def _validate_id(cls, v: str) -> str:
        if not _HYP_ID_RE.match(v):
            raise ValueError(
                f"hypothesis id {v!r} must match H<n> or H<n>.<m>... "
                "(e.g. H1, H1.1, H2.1.3)"
            )
        return v

    @property
    def parent(self) -> str | None:
        """Derived parent id. ``H1.2`` → ``H1``; ``H1`` → ``None``."""
        if "." not in self.id:
            return None
        return self.id.rsplit(".", 1)[0]

    @property
    def depth(self) -> int:
        """0 for root (``H1``), 1 for first sub-level (``H1.1``), etc."""
        return self.id.count(".")


class SocraticTurn(BaseModel):
    """One Q/A round inside a Socratic discussion."""

    question: str
    answer: str


class SocraticTrace(BaseModel):
    """Full discussion trace for one idea."""

    turns: list[SocraticTurn] = Field(default_factory=list)
    idea_statement: str | None = None
    past_work_refs: list[str] = Field(default_factory=list)
    hypotheses: list[Hypothesis] = Field(default_factory=list)
    created_at: str = Field(default_factory=lambda: datetime.now().isoformat(timespec="seconds"))


def record_turn(trace: SocraticTrace, question: str, answer: str) -> None:
    """Append a Q/A turn to the trace, in place."""
    if not question.strip():
        raise ValueError("empty question")
    trace.turns.append(SocraticTurn(question=question.strip(), answer=answer.strip()))


def to_experiment_hypothesis_seed(trace: SocraticTrace) -> str:
    """Render the hypothesis tree as Markdown for ``/experiment design`` to paste.

    Returns ``""`` when no hypotheses are captured, so the caller can fall
    through to the existing free-text prompt.

    The output matches the format the experiment-design template's
    ``## Hypothesis`` section accepts (bullet list with optional sub-bullets
    for predictions). Indentation follows the dotted-id depth, so ``H1.1``
    nests under ``H1``.
    """
    if not trace.hypotheses:
        return ""
    lines: list[str] = []
    for h in sorted(trace.hypotheses, key=lambda hyp: hyp.id):
        indent = "  " * h.depth
        lines.append(f"{indent}- **{h.id}**: {h.statement.strip()}")
        if h.prediction:
            lines.append(f"{indent}  - Prediction: {h.prediction.strip()}")
    return "\n".join(lines) + "\n"


def render_socratic_md(trace: SocraticTrace) -> str:
    """Render the trace to markdown for ``outputs/idea-checks/<slug>/socratic.md``."""
    lines: list[str] = ["# Socratic discussion", ""]
    lines.append(f"_Captured {trace.created_at}_")
    lines.append("")
    if trace.idea_statement:
        lines.extend([
            "## Distilled idea statement",
            "",
            trace.idea_statement.strip(),
            "",
        ])
    if trace.past_work_refs:
        lines.append("## Prior work touched")
        lines.append("")
        for ref in trace.past_work_refs:
            lines.append(f"- {ref}")
        lines.append("")
    if trace.hypotheses:
        lines.append("## Hypotheses")
        lines.append("")
        for h in sorted(trace.hypotheses, key=lambda hyp: hyp.id):
            indent = "  " * h.depth
            line = f"{indent}- **{h.id}** ({h.priority}): {h.statement.strip()}"
            lines.append(line)
            if h.prediction:
                lines.append(f"{indent}  - _Prediction:_ {h.prediction.strip()}")
        lines.append("")
    lines.append("## Discussion")
    lines.append("")
    for i, turn in enumerate(trace.turns, start=1):
        lines.append(f"### Q{i}. {turn.question}")
        lines.append("")
        if turn.answer:
            lines.append(turn.answer)
        else:
            lines.append("_(no answer recorded)_")
        lines.append("")
    return "\n".join(lines).rstrip() + "\n"
