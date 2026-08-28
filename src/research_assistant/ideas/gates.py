"""The five-gate validation pipeline — the only progress axis of `/idea-check`.

An idea advances when a **gate** passes, never because an artifact was
produced. Scout / brainstorm / contrarian / evaluate / venues / knowledge are
*services* the gates call for evidence; they leave the gate ledger untouched.

Gate order and intent:

1. ``failure-case``       — 现有方法到底在什么情况下真的会失效？(具体、可复现)
2. ``problem-standalone`` — 删掉你的方法，这个问题本身还值得研究吗？
3. ``mechanism``          — 原来的方法错在哪？真正起作用的因素是什么？
4. ``predictions``        — 机制若成立，能推出哪些可检验的新预测？(≥2 条)
5. ``minimal-experiment`` — 先用最小实验验证预测，再谈大规模实验。

A gate that has not cleared **blocks every later gate** (see :func:`can_enter`).
The block is overridable per gate by recording the decision with
``forced=True``: the pipeline moves on, but the override stays visible in
``gates.md``, in the manifest's ``forced_gates`` list, and on the status board.
The point of the ledger is that "跑了两个月才发现问题没想清楚" leaves a trace
at the gate where it was skipped.
"""
from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field, model_validator

GateKey = Literal[
    "failure-case",
    "problem-standalone",
    "mechanism",
    "predictions",
    "minimal-experiment",
]

GATE_ORDER: tuple[GateKey, ...] = (
    "failure-case",
    "problem-standalone",
    "mechanism",
    "predictions",
    "minimal-experiment",
)

#: Short human label per gate — used in the board and in prompts.
GATE_LABELS: dict[GateKey, str] = {
    "failure-case": "真实失效场景",
    "problem-standalone": "删掉方法后问题依然成立",
    "mechanism": "机制解释",
    "predictions": "可检验预测",
    "minimal-experiment": "最小实验",
}

#: The one question that decides each gate. The skill asks these verbatim.
GATE_QUESTIONS: dict[GateKey, str] = {
    "failure-case": "现有方法到底在什么情况下真的会失效？给一个具体、可复现的场景或例子。",
    "problem-standalone": "如果没有你这个方法，这个问题本身还值得研究吗？谁会关心？",
    "mechanism": "原来的方法到底错在哪里？真正影响结果的因素是什么？(要机制，不要现象)",
    "predictions": "如果这个解释成立：什么情况下问题会更严重？什么情况下根本不会发生？",
    "minimal-experiment": "用什么最小实验、多久能验证上面的预测？(分钟级，不是两个月)",
}

#: The manifest status an idea reaches once the gate clears. Mirrors
#: ``registry.STATUS_ORDER`` — keep the two in sync.
GATE_STATUS: dict[GateKey, str] = {
    "failure-case": "failure-case-found",
    "problem-standalone": "problem-standalone",
    "mechanism": "mechanism-explained",
    "predictions": "predictions-locked",
    "minimal-experiment": "experiment-ready",
}

GateVerdict = Literal["pass", "doubt", "fail"]

VERDICT_MARKS: dict[GateVerdict, str] = {"pass": "✅", "doubt": "⚠️", "fail": "❌"}

#: Gate 4 needs at least this many usable predictions to pass on its own merit.
MIN_PREDICTIONS = 2


class Prediction(BaseModel):
    """One falsifiable prediction derived from the Gate-3 mechanism.

    ``kind`` records which side of the mechanism the prediction probes —
    ``worse`` ("问题会更严重"), ``absent`` ("问题不会发生"), or ``other``.
    A prediction without a ``cheap_check`` doesn't count toward
    :data:`MIN_PREDICTIONS`: an unfalsifiable prediction is a restatement.
    """

    statement: str
    kind: Literal["worse", "absent", "other"] = "other"
    cheap_check: str = ""

    @property
    def usable(self) -> bool:
        return bool(self.statement.strip() and self.cheap_check.strip())


class GateRecord(BaseModel):
    """One decision on one gate. Re-deciding a gate appends a new record.

    The three output fields mirror the rubric's required response shape:
    ``verdict`` + ``reason`` (关卡状态), ``key_question`` (最关键的一个追问),
    ``next_action`` (下一步低成本行动).
    """

    gate: GateKey
    verdict: GateVerdict
    reason: str = ""
    evidence: list[str] = Field(default_factory=list)
    key_question: str = ""
    next_action: str = ""
    predictions: list[Prediction] = Field(default_factory=list)
    forced: bool = False
    decided_at: str = Field(
        default_factory=lambda: datetime.now().isoformat(timespec="seconds")
    )

    @model_validator(mode="after")
    def _check_gate_specifics(self) -> GateRecord:
        if not self.reason.strip():
            raise ValueError(
                f"gate {self.gate!r}: every decision needs a one-line reason"
            )
        if (
            self.gate == "predictions"
            and self.verdict == "pass"
            and not self.forced
            and sum(1 for p in self.predictions if p.usable) < MIN_PREDICTIONS
        ):
            raise ValueError(
                "gate 'predictions' cannot pass with fewer than "
                f"{MIN_PREDICTIONS} predictions that each carry a cheap_check "
                "(use forced=True to override deliberately)"
            )
        return self

    @property
    def cleared(self) -> bool:
        """Does this decision let the pipeline move past its gate?"""
        return self.verdict == "pass" or self.forced


class GateLedger(BaseModel):
    """Append-only decision log for one idea. Latest record per gate wins."""

    slug: str
    records: list[GateRecord] = Field(default_factory=list)


def record_gate(ledger: GateLedger, record: GateRecord) -> GateRecord:
    """Append a decision to the ledger, in place. Returns the record."""
    ledger.records.append(record)
    return record


def latest(ledger: GateLedger, gate: GateKey) -> GateRecord | None:
    """The most recent decision on ``gate``, or ``None`` if never decided."""
    for record in reversed(ledger.records):
        if record.gate == gate:
            return record
    return None


def cleared(ledger: GateLedger, gate: GateKey) -> bool:
    """Has ``gate`` been cleared (passed, or passed under ``forced``)?"""
    record = latest(ledger, gate)
    return bool(record and record.cleared)


def can_enter(ledger: GateLedger, gate: GateKey) -> tuple[bool, GateKey | None]:
    """Hard block: every earlier gate must be cleared first.

    Returns ``(True, None)`` when the gate is enterable, else
    ``(False, <first uncleared earlier gate>)``. Re-entering an
    already-decided gate is always allowed — that's how a red light gets
    fixed rather than worked around.
    """
    for earlier in GATE_ORDER:
        if earlier == gate:
            return True, None
        if not cleared(ledger, earlier):
            return False, earlier
    return True, None


def open_gate(ledger: GateLedger) -> GateKey | None:
    """The gate the idea is currently sitting at. ``None`` when all cleared."""
    for gate in GATE_ORDER:
        if not cleared(ledger, gate):
            return gate
    return None


def forced_gates(ledger: GateLedger) -> list[GateKey]:
    """Gates whose latest decision was an override, in pipeline order."""
    return [g for g in GATE_ORDER if (r := latest(ledger, g)) and r.forced]


def manifest_status(ledger: GateLedger) -> str | None:
    """The status the manifest should carry, from the cleared prefix of gates.

    Returns ``None`` when no gate has cleared yet (the manifest stays at
    ``captured``). Only a *contiguous* run counts — clearing Gate 3 while
    Gate 2 is red cannot happen through :func:`can_enter`, and if it somehow
    does, the status stops at the hole.
    """
    reached: str | None = None
    for gate in GATE_ORDER:
        if not cleared(ledger, gate):
            break
        reached = GATE_STATUS[gate]
    return reached


def render_gates_md(ledger: GateLedger) -> str:
    """Render the ledger to ``outputs/idea-checks/<slug>/gates.md``."""
    lines = [f"# Gates — `{ledger.slug}`", ""]
    lines.append("| # | Gate | 状态 | 理由 |")
    lines.append("|---|---|---|---|")
    for i, gate in enumerate(GATE_ORDER, start=1):
        record = latest(ledger, gate)
        if record is None:
            lines.append(f"| {i} | {GATE_LABELS[gate]} (`{gate}`) | — 未评估 | |")
            continue
        mark = VERDICT_MARKS[record.verdict]
        if record.forced:
            mark += " (forced)"
        reason = record.reason.replace("|", "\\|").replace("\n", " ").strip()
        lines.append(f"| {i} | {GATE_LABELS[gate]} (`{gate}`) | {mark} | {reason} |")
    lines.append("")

    for gate in GATE_ORDER:
        record = latest(ledger, gate)
        if record is None:
            continue
        lines.extend(_render_gate_detail(gate, record))

    forced = forced_gates(ledger)
    if forced:
        lines.append("## Overrides")
        lines.append("")
        lines.append(
            "以下关卡是在未通过的情况下被强制放行的 —— 后续实验若失败，先回来看这里："
        )
        for gate in forced:
            lines.append(f"- `{gate}` — {GATE_LABELS[gate]}")
        lines.append("")

    nxt = open_gate(ledger)
    if nxt is None:
        lines.append("_五关全部通过 —— 可以 `/idea-check handoff` 交给 `/paper`。_")
    else:
        lines.append(f"_当前关卡: `{nxt}` ({GATE_LABELS[nxt]}) —— `/idea-check {nxt}`_")
    return "\n".join(lines).rstrip() + "\n"


def _render_gate_detail(gate: GateKey, record: GateRecord) -> list[str]:
    mark = VERDICT_MARKS[record.verdict]
    head = f"## {mark} {GATE_LABELS[gate]} (`{gate}`)"
    if record.forced:
        head += " — forced"
    lines = [head, "", f"_{record.decided_at}_", "", record.reason.strip(), ""]
    if record.evidence:
        lines.append("**证据**")
        lines.append("")
        for item in record.evidence:
            lines.append(f"- {item}")
        lines.append("")
    if record.predictions:
        lines.append("**预测**")
        lines.append("")
        for p in record.predictions:
            suffix = f" — 验证方式: {p.cheap_check}" if p.cheap_check else " — _(无验证方式)_"
            lines.append(f"- [{p.kind}] {p.statement}{suffix}")
        lines.append("")
    if record.key_question:
        lines.append(f"**最关键的追问**: {record.key_question}")
        lines.append("")
    if record.next_action:
        lines.append(f"**下一步**: {record.next_action}")
        lines.append("")
    return lines


def to_agentdb_payload(ledger: GateLedger) -> dict:
    """Payload for ``memory_store namespace=ideas, key=<slug>/gates``."""
    return {
        "slug": ledger.slug,
        "open_gate": open_gate(ledger),
        "status": manifest_status(ledger),
        "forced_gates": forced_gates(ledger),
        "records": [r.model_dump() for r in ledger.records],
    }
