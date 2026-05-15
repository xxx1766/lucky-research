"""Socratic discussion trace for `/idea-check`.

Captures the multi-turn Q&A and the distilled idea statement so the markdown
file is auditable and re-renderable from the trace.
"""
from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, Field


class SocraticTurn(BaseModel):
    """One Q/A round inside a Socratic discussion."""

    question: str
    answer: str


class SocraticTrace(BaseModel):
    """Full discussion trace for one idea."""

    turns: list[SocraticTurn] = Field(default_factory=list)
    idea_statement: str | None = None
    past_work_refs: list[str] = Field(default_factory=list)
    created_at: str = Field(default_factory=lambda: datetime.now().isoformat(timespec="seconds"))


def record_turn(trace: SocraticTrace, question: str, answer: str) -> None:
    """Append a Q/A turn to the trace, in place."""
    if not question.strip():
        raise ValueError("empty question")
    trace.turns.append(SocraticTurn(question=question.strip(), answer=answer.strip()))


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
