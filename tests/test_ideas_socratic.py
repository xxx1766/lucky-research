"""Tests for the Socratic trace dataclass + renderer."""
from __future__ import annotations

import pytest

from research_assistant.ideas.socratic import (
    SocraticTrace,
    record_turn,
    render_socratic_md,
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
