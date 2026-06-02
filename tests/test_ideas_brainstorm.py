"""Tests for the brainstorm trace + renderer."""
from __future__ import annotations

import pytest

from research_assistant.ideas.brainstorm import (
    FRAMEWORK_NAMES,
    BrainstormHandoff,
    BrainstormTrace,
    add_candidate,
    converge,
    record_turn,
    render_brainstorm_md,
    survivors,
    to_agentdb_payload,
)


def _trace(frameworks=("F3", "F4")) -> BrainstormTrace:
    return BrainstormTrace(
        parent_slug="rag-feedback-rerank",
        parent_statement="Re-rank chunks by past user feedback signals.",
        user_situation="Idea feels incremental, want fresh angles",
        frameworks=list(frameworks),
    )


def test_framework_codes_are_dense_and_known():
    # F1 through F11 — keep this tight so the reference file's table stays accurate.
    assert set(FRAMEWORK_NAMES.keys()) == {f"F{i}" for i in range(1, 12)}


def test_invalid_framework_rejected():
    with pytest.raises(ValueError):
        BrainstormTrace(
            parent_slug="x",
            parent_statement="y",
            frameworks=["F99"],
        )


def test_too_many_frameworks_rejected():
    with pytest.raises(ValueError):
        BrainstormTrace(
            parent_slug="x",
            parent_statement="y",
            frameworks=["F1", "F2", "F3", "F4", "F5"],
        )


def test_record_turn_rejects_framework_not_in_session():
    t = _trace(frameworks=["F3"])
    with pytest.raises(ValueError):
        record_turn(t, "F4", "Q?", "A")


def test_record_turn_appends_with_framework_label():
    t = _trace()
    record_turn(t, "F3", "Which trade-off?", "Performance vs efficiency.")
    record_turn(t, "F4", "Borrow from where?", "Mechanism design.")
    assert len(t.turns) == 2
    assert t.turns[0].framework == "F3"
    assert t.turns[1].framework == "F4"


def test_add_candidate_rejects_empty_pitch():
    t = _trace()
    with pytest.raises(ValueError):
        add_candidate(t, "F3", "   ")


def test_add_candidate_rejects_framework_not_in_session():
    t = _trace(frameworks=["F3"])
    with pytest.raises(ValueError):
        add_candidate(t, "F4", "Some pitch")


def test_converge_marks_survivors_and_kills():
    t = _trace()
    add_candidate(t, "F3", "Candidate A")
    add_candidate(t, "F3", "Candidate B")
    add_candidate(t, "F4", "Candidate C")
    converge(t, keep=[0, 2], kill_reasons={1: "no clear beneficiary"})
    assert [c.survived_converge for c in t.candidates] == [True, False, True]
    assert t.candidates[1].kill_reason == "no clear beneficiary"
    assert t.candidates[2].kill_reason == ""


def test_survivors_returns_only_kept_in_order():
    t = _trace()
    add_candidate(t, "F3", "A")
    add_candidate(t, "F3", "B")
    add_candidate(t, "F4", "C")
    converge(t, keep=[0, 2])
    surv = survivors(t)
    assert [c.pitch for c in surv] == ["A", "C"]


def test_render_includes_frameworks_section():
    t = _trace(frameworks=["F3", "F8"])
    md = render_brainstorm_md(t)
    assert "## Frameworks used" in md
    assert "F3" in md
    assert "tension hunting" in md
    assert "F8" in md
    assert "negation hall of fame" in md


def test_render_includes_turns_labelled_with_framework_name():
    t = _trace()
    record_turn(t, "F3", "Which trade-off?", "Performance vs efficiency.")
    md = render_brainstorm_md(t)
    assert "[F3 — tension hunting] Which trade-off?" in md
    assert "Performance vs efficiency." in md


def test_render_candidate_markers():
    t = _trace()
    add_candidate(t, "F3", "Surviving idea")
    add_candidate(t, "F4", "Killed idea")
    converge(t, keep=[0], kill_reasons={1: "duplicate of active"})
    md = render_brainstorm_md(t)
    assert "1. [✓ F3] Surviving idea" in md
    assert "2. [✗ F4] Killed idea" in md
    assert "duplicate of active" in md


def test_render_handoff_block_for_spawn_sibling():
    t = _trace()
    t.handoff = BrainstormHandoff(
        kind="spawn-sibling",
        statement="Re-rank chunks by clipboard-history embeddings.",
        sibling_suffix="clipboard-rerank",
    )
    md = render_brainstorm_md(t)
    assert "## Hand-off" in md
    assert "`spawn-sibling`" in md
    assert "clipboard-history embeddings" in md
    assert "rag-feedback-rerank-clipboard-rerank" in md


def test_render_omits_handoff_section_when_none():
    t = _trace()
    md = render_brainstorm_md(t)
    assert "## Hand-off" not in md


def test_to_agentdb_payload_is_compact():
    t = _trace()
    record_turn(t, "F3", "Q1", "A1")
    add_candidate(t, "F3", "Pitch A")
    add_candidate(t, "F4", "Pitch B")
    converge(t, keep=[0])
    t.handoff = BrainstormHandoff(kind="park", statement="Save for later.")
    payload = to_agentdb_payload(t)
    assert payload["parent_slug"] == "rag-feedback-rerank"
    assert payload["frameworks"] == ["F3", "F4"]
    assert payload["turn_count"] == 1
    assert payload["candidate_count"] == 2
    assert payload["survivor_count"] == 1
    assert payload["handoff_kind"] == "park"
    # Only survivors are embedded — kept idea pitches yes, killed-only no.
    assert len(payload["survivors"]) == 1
    assert payload["survivors"][0]["pitch"] == "Pitch A"
