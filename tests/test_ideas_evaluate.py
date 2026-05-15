"""Tests for the idea evaluation rubric."""
from __future__ import annotations

import pytest

from research_assistant.ideas.evaluate import (
    FEASIBILITY_AXES,
    VALUE_AXES,
    IdeaEvaluation,
    IdeaRisk,
    render_evaluate_md,
)


def test_default_evaluation_renders_all_axes():
    ev = IdeaEvaluation(
        value_scores={k: 3 for k in VALUE_AXES},
        feasibility_scores={k: 3 for k in FEASIBILITY_AXES},
        verdict="pivot",
    )
    md = render_evaluate_md(ev)
    for axis in VALUE_AXES + FEASIBILITY_AXES:
        assert axis.replace("_", " ") in md
    assert "PIVOT" in md


def test_out_of_range_score_raises():
    with pytest.raises(ValueError):
        IdeaEvaluation(value_scores={"novelty": 9})


def test_non_int_score_raises():
    with pytest.raises(ValueError):
        IdeaEvaluation(value_scores={"novelty": 3.5})


def test_top_risks_render_numbered():
    ev = IdeaEvaluation(
        verdict="go",
        top_risks=[
            IdeaRisk(name="data licensing", mitigation="switch to public corpus"),
            IdeaRisk(name="compute cost", mitigation="use 3B model"),
        ],
    )
    md = render_evaluate_md(ev)
    assert "1. **data licensing**" in md
    assert "2. **compute cost**" in md


def test_no_risks_renders_placeholder():
    ev = IdeaEvaluation(verdict="drop")
    md = render_evaluate_md(ev)
    assert "_(no risks captured yet)_" in md
    assert "DROP" in md


def test_rationale_appears_inline():
    ev = IdeaEvaluation(
        value_scores={"novelty": 4},
        rationale={"novelty": "no prior work re-ranks by user-specific feedback"},
    )
    md = render_evaluate_md(ev)
    assert "no prior work re-ranks by user-specific feedback" in md
