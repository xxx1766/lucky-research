"""Brainstorm trace for `/idea-check brainstorm`.

Stage-1.5 escape hatch when Socratic stalls or when the user explicitly
asks for fresh angles. Walks 2–3 ideation frameworks (picked via the
Selection Guide in
``.claude/skills/idea-validate/references/ideation-frameworks.md``) and
captures the diverge → converge → refine session.

Adapted from Orchestra-Research/AI-Research-SKILLs (MIT)
``21-research-ideation/`` — they keep brainstorming as a standalone skill
that ``autoresearch`` invokes when the inner loop is stuck. We mirror that
separation here: brainstorm is a sibling subcommand to Socratic, not a
sub-stage of it. Output lives at
``outputs/idea-checks/<slug>/brainstorm.md`` and AgentDB
``ideas/<slug>/brainstorm``.

The 11-letter framework codes (``F1`` … ``F11``) are the slugs from the
reference file's Selection Guide table. ``brainstorm.FRAMEWORK_NAMES``
keeps the human-readable mapping so renders can show
``F4 (cross-pollination)`` not just ``F4``.
"""
from __future__ import annotations

import re
from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field, field_validator


# Order matches the reference file. Don't renumber — these are slugs cited
# from skill prompts.
FRAMEWORK_NAMES: dict[str, str] = {
    "F1": "problem-first vs solution-first",
    "F2": "abstraction ladder",
    "F3": "tension hunting",
    "F4": "cross-pollination",
    "F5": "what-changed",
    "F6": "boundary probing",
    "F7": "simplicity test",
    "F8": "negation hall of fame",
    "F9": "composition / decomposition",
    "F10": "two-sentence test",
    "F11": "Janusian / dialectical",
}

_FRAMEWORK_CODE_RE = re.compile(r"^F\d+$")

HandoffKind = Literal["spawn-sibling", "refine-active", "park", "none"]


class BrainstormTurn(BaseModel):
    """One Q/A round inside the brainstorm session."""

    framework: str
    """The framework code this turn belongs to (e.g. ``F4``)."""
    question: str
    answer: str

    @field_validator("framework")
    @classmethod
    def _validate_framework(cls, v: str) -> str:
        if not _FRAMEWORK_CODE_RE.match(v):
            raise ValueError(f"framework code {v!r} must look like F<n>")
        if v not in FRAMEWORK_NAMES:
            raise ValueError(
                f"unknown framework {v!r} — known: {sorted(FRAMEWORK_NAMES.keys())}"
            )
        return v


class BrainstormCandidate(BaseModel):
    """One raw idea generated during Phase 2 diverge."""

    pitch: str
    """One- or two-sentence framing of the candidate."""
    framework: str
    """Which framework produced this candidate (e.g. ``F8``)."""
    survived_converge: bool = False
    """True after Phase 3 converge filters passed. Reason in ``kill_reason``
    when False."""
    kill_reason: str = ""

    @field_validator("framework")
    @classmethod
    def _validate_framework(cls, v: str) -> str:
        if v not in FRAMEWORK_NAMES:
            raise ValueError(f"unknown framework {v!r}")
        return v


class BrainstormHandoff(BaseModel):
    """The Phase 4 refine decision."""

    kind: HandoffKind = "none"
    """``spawn-sibling`` → create a new variant idea via
    ``registry.create_variant_idea``. ``refine-active`` → user will re-enter
    Stage 1 with the refined statement. ``park`` → kept in the trace but no
    follow-up action. ``none`` → session ended before Phase 4."""

    statement: str = ""
    """The two-sentence pitch (F10) for the chosen candidate, when ``kind``
    is ``spawn-sibling`` or ``refine-active``."""

    sibling_suffix: str = ""
    """Short tag for ``create_variant_idea`` (e.g. ``cross-pollination``).
    Only used when ``kind == "spawn-sibling"``."""


class BrainstormTrace(BaseModel):
    """Full brainstorm session attached to one parent idea.

    Mirrors the shape of :class:`ContrarianTrace` so the skill prompt can
    use a parallel Q-by-Q rhythm.
    """

    parent_slug: str
    parent_statement: str
    user_situation: str = ""
    """One-line description of why brainstorm was invoked (matches a row
    in the Selection Guide table). Picked at Phase 1."""

    frameworks: list[str] = Field(default_factory=list)
    """The 2–3 framework codes chosen in Phase 1."""

    turns: list[BrainstormTurn] = Field(default_factory=list)
    candidates: list[BrainstormCandidate] = Field(default_factory=list)
    handoff: BrainstormHandoff = Field(default_factory=BrainstormHandoff)
    created_at: str = Field(
        default_factory=lambda: datetime.now().isoformat(timespec="seconds")
    )

    @field_validator("frameworks")
    @classmethod
    def _validate_frameworks(cls, v: list[str]) -> list[str]:
        for code in v:
            if code not in FRAMEWORK_NAMES:
                raise ValueError(f"unknown framework {code!r}")
        if len(v) > 4:
            raise ValueError(
                f"brainstorm picks at most 4 frameworks; got {len(v)}"
            )
        return v


def record_turn(
    trace: BrainstormTrace, framework: str, question: str, answer: str
) -> None:
    """Append a Q/A turn to the trace, in place."""
    if not question.strip():
        raise ValueError("empty question")
    if framework not in trace.frameworks:
        raise ValueError(
            f"framework {framework!r} not in this session's "
            f"selection: {trace.frameworks}"
        )
    trace.turns.append(
        BrainstormTurn(
            framework=framework, question=question.strip(), answer=answer.strip()
        )
    )


def add_candidate(
    trace: BrainstormTrace, framework: str, pitch: str
) -> BrainstormCandidate:
    """Append a Phase-2 raw candidate. Returns it for chaining."""
    pitch = pitch.strip()
    if not pitch:
        raise ValueError("empty candidate pitch")
    if framework not in trace.frameworks:
        raise ValueError(
            f"framework {framework!r} not in this session's "
            f"selection: {trace.frameworks}"
        )
    cand = BrainstormCandidate(pitch=pitch, framework=framework)
    trace.candidates.append(cand)
    return cand


def converge(
    trace: BrainstormTrace,
    keep: list[int],
    kill_reasons: dict[int, str] | None = None,
) -> None:
    """Mark Phase-3 survivors. ``keep`` is a list of candidate indices.

    Indices not in ``keep`` are marked killed; ``kill_reasons[i]`` provides
    the per-index reason (defaults to "filtered" if missing).
    """
    kill_reasons = kill_reasons or {}
    for i, cand in enumerate(trace.candidates):
        if i in keep:
            cand.survived_converge = True
            cand.kill_reason = ""
        else:
            cand.survived_converge = False
            cand.kill_reason = kill_reasons.get(i, "filtered")


def survivors(trace: BrainstormTrace) -> list[BrainstormCandidate]:
    """Return Phase-3 survivors, preserving insertion order."""
    return [c for c in trace.candidates if c.survived_converge]


def render_brainstorm_md(trace: BrainstormTrace) -> str:
    """Render the standalone doc for the active idea's directory.

    Path: ``outputs/idea-checks/<parent_slug>/brainstorm.md``.
    """
    lines: list[str] = ["# Brainstorm session", ""]
    lines.append(f"_Captured {trace.created_at}_")
    lines.append("")
    lines.append(f"Parent: [[{trace.parent_slug}]]")
    lines.append("")
    lines.append(f"> {trace.parent_statement.strip()}")
    lines.append("")

    if trace.user_situation:
        lines.append(f"**User situation:** {trace.user_situation}")
        lines.append("")

    if trace.frameworks:
        lines.append("## Frameworks used")
        lines.append("")
        for code in trace.frameworks:
            lines.append(f"- **{code}** — {FRAMEWORK_NAMES[code]}")
        lines.append("")

    if trace.turns:
        lines.append("## Diverge — Q/A turns")
        lines.append("")
        for i, turn in enumerate(trace.turns, start=1):
            name = FRAMEWORK_NAMES[turn.framework]
            lines.append(f"### Q{i}. [{turn.framework} — {name}] {turn.question}")
            lines.append("")
            lines.append(turn.answer or "_(no answer recorded)_")
            lines.append("")

    if trace.candidates:
        lines.append("## Candidates")
        lines.append("")
        for i, cand in enumerate(trace.candidates, start=1):
            marker = "✓" if cand.survived_converge else "✗"
            line = f"{i}. [{marker} {cand.framework}] {cand.pitch}"
            if not cand.survived_converge and cand.kill_reason:
                line += f"  _(kill: {cand.kill_reason})_"
            lines.append(line)
        lines.append("")

    if trace.handoff.kind != "none":
        lines.append("## Hand-off")
        lines.append("")
        lines.append(f"**Decision:** `{trace.handoff.kind}`")
        if trace.handoff.statement:
            lines.append("")
            lines.append(trace.handoff.statement.strip())
        if trace.handoff.kind == "spawn-sibling" and trace.handoff.sibling_suffix:
            lines.append("")
            lines.append(
                f"Sibling slug suffix: `{trace.handoff.sibling_suffix}` "
                f"→ `{trace.parent_slug}-{trace.handoff.sibling_suffix}`"
            )
        lines.append("")

    return "\n".join(lines).rstrip() + "\n"


def to_agentdb_payload(trace: BrainstormTrace) -> dict:
    """Payload for ``memory_store namespace=ideas, key=<parent>/brainstorm``."""
    return {
        "parent_slug": trace.parent_slug,
        "parent_statement": trace.parent_statement,
        "user_situation": trace.user_situation,
        "frameworks": list(trace.frameworks),
        "created_at": trace.created_at,
        "turn_count": len(trace.turns),
        "candidate_count": len(trace.candidates),
        "survivor_count": sum(1 for c in trace.candidates if c.survived_converge),
        "handoff_kind": trace.handoff.kind,
        "handoff_statement": trace.handoff.statement,
        "survivors": [
            c.model_dump()
            for c in trace.candidates
            if c.survived_converge
        ],
    }
