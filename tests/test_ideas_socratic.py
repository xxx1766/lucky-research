"""Tests for the Socratic trace dataclass + renderer."""
from __future__ import annotations

import pytest

from research_assistant.ideas.socratic import (
    Hypothesis,
    SocraticTrace,
    record_turn,
    render_socratic_md,
    to_experiment_hypothesis_seed,
)


def test_record_turn_appends():
    t = SocraticTrace()
    record_turn(t, "Q1?", "A1")
    record_turn(t, "Q2?", "A2")
    assert [tt.question for tt in t.turns] == ["Q1?", "Q2?"]
    assert [tt.answer for tt in t.turns] == ["A1", "A2"]


def test_record_turn_rejects_empty_question():
    t = SocraticTrace()
    with pytest.raises(ValueError):
        record_turn(t, "", "answer")


def test_render_includes_idea_statement():
    t = SocraticTrace(idea_statement="Re-rank chunks by past user feedback.")
    record_turn(t, "What problem?", "RAG re-ranking is feedback-blind.")
    md = render_socratic_md(t)
    assert "# Socratic discussion" in md
    assert "Re-rank chunks by past user feedback." in md
    assert "### Q1. What problem?" in md
    assert "RAG re-ranking is feedback-blind." in md


def test_render_handles_no_answer_gracefully():
    t = SocraticTrace()
    record_turn(t, "Did you skip this?", "")
    md = render_socratic_md(t)
    assert "_(no answer recorded)_" in md


def test_render_includes_past_work_refs():
    t = SocraticTrace(past_work_refs=["[[memory-bank-v1]]"])
    md = render_socratic_md(t)
    assert "## Prior work touched" in md
    assert "memory-bank-v1" in md


def test_hypothesis_id_validation():
    with pytest.raises(ValueError):
        Hypothesis(id="X1", statement="bad prefix")
    with pytest.raises(ValueError):
        Hypothesis(id="h1", statement="lowercase prefix")
    with pytest.raises(ValueError):
        Hypothesis(id="H1.x", statement="non-numeric segment")
    # All these are valid.
    assert Hypothesis(id="H1", statement="root").parent is None
    assert Hypothesis(id="H1.2", statement="child").parent == "H1"
    assert Hypothesis(id="H1.2.3", statement="grandchild").parent == "H1.2"


def test_hypothesis_depth():
    assert Hypothesis(id="H1", statement="x").depth == 0
    assert Hypothesis(id="H1.2", statement="x").depth == 1
    assert Hypothesis(id="H1.2.3", statement="x").depth == 2


def test_render_includes_hypotheses_indented_by_depth():
    t = SocraticTrace(
        hypotheses=[
            Hypothesis(id="H1", statement="Root claim", prediction="metric goes up"),
            Hypothesis(id="H1.1", statement="Sub-claim under H1", priority="high"),
            Hypothesis(id="H2", statement="Independent root", priority="low"),
        ]
    )
    md = render_socratic_md(t)
    assert "## Hypotheses" in md
    # H1 line at column 0; H1.1 line indented with 2 spaces.
    assert "- **H1** (medium): Root claim" in md
    assert "  - **H1.1** (high): Sub-claim under H1" in md
    assert "- **H2** (low): Independent root" in md
    # Prediction renders under H1, indented one more level.
    assert "  - _Prediction:_ metric goes up" in md


def test_render_omits_hypotheses_section_when_empty():
    t = SocraticTrace()
    md = render_socratic_md(t)
    assert "## Hypotheses" not in md


def test_to_experiment_hypothesis_seed_empty_when_no_hypotheses():
    assert to_experiment_hypothesis_seed(SocraticTrace()) == ""


def test_to_experiment_hypothesis_seed_renders_tree_markdown():
    t = SocraticTrace(
        hypotheses=[
            Hypothesis(id="H1", statement="X causes Y", prediction="speedup ≥ 2x"),
            Hypothesis(id="H1.1", statement="X via mechanism A"),
        ]
    )
    seed = to_experiment_hypothesis_seed(t)
    assert "- **H1**: X causes Y" in seed
    assert "  - Prediction: speedup ≥ 2x" in seed
    assert "  - **H1.1**: X via mechanism A" in seed
