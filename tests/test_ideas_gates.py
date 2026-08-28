"""Tests for the five-gate validation pipeline."""
from __future__ import annotations

import pytest
from pydantic import ValidationError

from research_assistant.ideas.gates import (
    GATE_ORDER,
    GATE_STATUS,
    GateLedger,
    GateRecord,
    Prediction,
    can_enter,
    cleared,
    forced_gates,
    latest,
    manifest_status,
    open_gate,
    record_gate,
    render_gates_md,
    to_agentdb_payload,
)


def _pass(gate: str, **kw) -> GateRecord:
    kw.setdefault("reason", "ok")
    return GateRecord(gate=gate, verdict="pass", **kw)


def _two_predictions() -> list[Prediction]:
    return [
        Prediction(statement="长上下文时更严重", kind="worse", cheap_check="截断到 2k 重跑"),
        Prediction(statement="短输入时不出现", kind="absent", cheap_check="512 token 子集"),
    ]


def test_empty_ledger_opens_at_first_gate():
    led = GateLedger(slug="demo")
    assert open_gate(led) == GATE_ORDER[0]
    assert manifest_status(led) is None


def test_every_decision_needs_a_reason():
    with pytest.raises(ValidationError):
        GateRecord(gate="mechanism", verdict="fail", reason="   ")


def test_later_gate_is_blocked_until_earlier_one_clears():
    led = GateLedger(slug="demo")
    ok, blocker = can_enter(led, "mechanism")
    assert ok is False
    assert blocker == "failure-case"

    record_gate(led, _pass("failure-case"))
    ok, blocker = can_enter(led, "mechanism")
    assert ok is False
    assert blocker == "problem-standalone"


def test_first_gate_is_always_enterable_and_reentrant():
    led = GateLedger(slug="demo")
    assert can_enter(led, "failure-case") == (True, None)
    record_gate(led, GateRecord(gate="failure-case", verdict="fail", reason="没有例子"))
    # A red gate must stay re-enterable — that's how it gets fixed.
    assert can_enter(led, "failure-case") == (True, None)
    assert cleared(led, "failure-case") is False


def test_latest_record_wins_when_a_gate_is_redecided():
    led = GateLedger(slug="demo")
    record_gate(led, GateRecord(gate="failure-case", verdict="fail", reason="第一次说不清"))
    record_gate(led, _pass("failure-case", reason="补了可复现例子"))
    assert cleared(led, "failure-case") is True
    assert latest(led, "failure-case").reason == "补了可复现例子"


def test_doubt_does_not_clear_a_gate():
    led = GateLedger(slug="demo")
    record_gate(led, GateRecord(gate="failure-case", verdict="doubt", reason="只在一个数据集上"))
    assert cleared(led, "failure-case") is False
    assert open_gate(led) == "failure-case"


def test_forced_gate_clears_but_stays_flagged():
    led = GateLedger(slug="demo")
    record_gate(
        led,
        GateRecord(gate="failure-case", verdict="fail", reason="说不清", forced=True),
    )
    assert cleared(led, "failure-case") is True
    assert forced_gates(led) == ["failure-case"]
    assert manifest_status(led) == GATE_STATUS["failure-case"]
    assert "forced" in render_gates_md(led)


def test_predictions_gate_needs_two_usable_predictions():
    with pytest.raises(ValidationError):
        GateRecord(gate="predictions", verdict="pass", reason="有想法")

    with pytest.raises(ValidationError):
        # Present but unfalsifiable — no cheap_check means it doesn't count.
        GateRecord(
            gate="predictions",
            verdict="pass",
            reason="两条预测",
            predictions=[
                Prediction(statement="会更严重"),
                Prediction(statement="不会发生"),
            ],
        )

    ok = GateRecord(
        gate="predictions",
        verdict="pass",
        reason="两条可验证预测",
        predictions=_two_predictions(),
    )
    assert ok.cleared is True


def test_predictions_gate_can_be_forced_past_the_minimum():
    rec = GateRecord(
        gate="predictions",
        verdict="doubt",
        reason="只有一条",
        predictions=[Prediction(statement="更严重", cheap_check="小 run")],
        forced=True,
    )
    assert rec.cleared is True


def test_manifest_status_follows_the_cleared_prefix_only():
    led = GateLedger(slug="demo")
    record_gate(led, _pass("failure-case"))
    record_gate(led, GateRecord(gate="problem-standalone", verdict="fail", reason="没人关心"))
    record_gate(led, _pass("mechanism"))
    # Gate 2 is red, so the status must stop at Gate 1 despite Gate 3 passing.
    assert manifest_status(led) == GATE_STATUS["failure-case"]
    assert open_gate(led) == "problem-standalone"


def test_full_clear_leaves_no_open_gate():
    led = GateLedger(slug="demo")
    for gate in GATE_ORDER:
        if gate == "predictions":
            record_gate(led, _pass(gate, predictions=_two_predictions()))
        else:
            record_gate(led, _pass(gate))
    assert open_gate(led) is None
    assert manifest_status(led) == GATE_STATUS["minimal-experiment"]
    assert can_enter(led, "minimal-experiment") == (True, None)


def test_render_lists_every_gate_and_the_current_one():
    led = GateLedger(slug="demo")
    record_gate(
        led,
        _pass(
            "failure-case",
            evidence=["Paper X (arXiv:2401.00001) — 在长上下文下崩"],
            key_question="还有哪个方法在同一处失效？",
            next_action="跑 /idea-check scout",
        ),
    )
    md = render_gates_md(led)
    for gate in GATE_ORDER:
        assert f"`{gate}`" in md
    assert "arXiv:2401.00001" in md
    assert "最关键的追问" in md
    assert "/idea-check problem-standalone" in md


def test_agentdb_payload_shape():
    led = GateLedger(slug="demo")
    record_gate(led, _pass("failure-case", forced=False))
    payload = to_agentdb_payload(led)
    assert payload["slug"] == "demo"
    assert payload["open_gate"] == "problem-standalone"
    assert payload["status"] == GATE_STATUS["failure-case"]
    assert payload["forced_gates"] == []
    assert payload["records"][0]["gate"] == "failure-case"
