"""Contrarian micro-flow trace for `/idea-check` Stage 2.5.

Captures the 4-Q 反其道而行 discussion that fires at the end of Scout. The
trace is durable on disk (rendered into the sibling idea directory and as an
appendix on the parent's ``scout.md``) and mirrored to AgentDB for audit.

Mirrors the shape of :mod:`research_assistant.ideas.socratic` so the skill
prompt can use the same Q-by-Q rhythm.
"""
from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, Field

_SKIP_SENTINEL = "<skipped>"


class ContrarianTurn(BaseModel):
    """One Q/A round inside the contrarian micro-flow."""

    question: str
    answer: str


class ContrarianTrace(BaseModel):
    """Full trace for the 4-Q contrarian discussion on one parent idea."""

    turns: list[ContrarianTurn] = Field(default_factory=list)
    parent_slug: str
    parent_statement: str
    mainstream_pattern: str | None = None
    shared_assumption: str | None = None
    inversion: str | None = None
    win_condition: str | None = None
    final_statement: str | None = None
    accepted: bool = False
    created_at: str = Field(
        default_factory=lambda: datetime.now().isoformat(timespec="seconds")
    )

    @property
    def skipped(self) -> bool:
        return self.mainstream_pattern == _SKIP_SENTINEL


def record_turn(trace: ContrarianTrace, question: str, answer: str) -> None:
    """Append a Q/A turn to the trace, in place."""
    if not question.strip():
        raise ValueError("empty question")
    trace.turns.append(
        ContrarianTurn(question=question.strip(), answer=answer.strip())
    )


def render_contrarian_md(trace: ContrarianTrace) -> str:
    """Render the standalone doc for the sibling dir.

    Path: ``outputs/idea-checks/<parent_slug>-contrarian/contrarian.md``.
    """
    lines: list[str] = ["# Contrarian framing", ""]
    lines.append(f"_Captured {trace.created_at}_")
    lines.append("")
    lines.append(f"Parent: [[{trace.parent_slug}]]")
    lines.append("")
    lines.append(f"> {trace.parent_statement.strip()}")
    lines.append("")
    if trace.final_statement:
        lines.extend(
            [
                "## Distilled contrarian statement",
                "",
                trace.final_statement.strip(),
                "",
            ]
        )
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


def render_scout_appendix(trace: ContrarianTrace) -> str:
    """Render the section appended to the parent's ``scout.md``.

    Returns ``""`` when the user skipped at Q1 so the caller can append
    unconditionally. Always returns a string that starts with the
    ``## Contrarian framings`` header so the idempotent rewrite-in-place
    logic can locate it.
    """
    if trace.skipped:
        return ""
    lines: list[str] = ["## Contrarian framings", ""]
    lines.append(f"_Captured {trace.created_at}_")
    lines.append("")
    for i, turn in enumerate(trace.turns, start=1):
        lines.append(f"- **Q{i}. {turn.question}**")
        if turn.answer:
            lines.append(f"  - {turn.answer}")
        else:
            lines.append("  - _(no answer recorded)_")
    lines.append("")
    if trace.final_statement:
        lines.append(f"**Distilled framing:** {trace.final_statement.strip()}")
        lines.append("")
    if trace.accepted:
        lines.append(
            f"**Sibling idea:** [[{trace.parent_slug}-contrarian]]"
        )
        lines.append("")
    return "\n".join(lines).rstrip() + "\n"


def to_agentdb_payload(trace: ContrarianTrace) -> dict:
    """Payload for ``memory_store`` namespace=``ideas`` key=``<parent>/contrarian``."""
    return {
        "parent_slug": trace.parent_slug,
        "parent_statement": trace.parent_statement,
        "mainstream_pattern": trace.mainstream_pattern,
        "shared_assumption": trace.shared_assumption,
        "inversion": trace.inversion,
        "win_condition": trace.win_condition,
        "final_statement": trace.final_statement,
        "accepted": trace.accepted,
        "skipped": trace.skipped,
        "created_at": trace.created_at,
        "turns": [t.model_dump() for t in trace.turns],
    }
