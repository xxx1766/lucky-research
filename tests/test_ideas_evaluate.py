"""Tests for the idea evaluation rubric."""
from __future__ import annotations

import pytest

from research_assistant.ideas.evaluate import (
    FEASIBILITY_AXES,
    VALUE_AXES,
    IdeaEvaluation,
    IdeaRisk,
    PreRegistration,
    render_evaluate_md,
    to_experiment_metrics_seed,
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


def test_pre_registration_block_renders_when_set():
    ev = IdeaEvaluation(
        verdict="go",
        pre_registration=PreRegistration(
            proxy_metric="ROUGE-L on KILT-NQ",
            baseline_value=0.412,
            baseline_source="Atlas-XL (2024)",
            target_delta="+0.03 absolute",
            notes="run on the held-out KILT slice only",
        ),
    )
    md = render_evaluate_md(ev)
    assert "## Pre-registration" in md
    assert "ROUGE-L on KILT-NQ" in md
    assert "0.412" in md
    assert "Atlas-XL (2024)" in md
    assert "+0.03 absolute" in md
    assert "run on the held-out KILT slice only" in md


def test_pre_registration_placeholder_when_missing():
    ev = IdeaEvaluation(verdict="pivot")
    md = render_evaluate_md(ev)
    assert "## Pre-registration" in md
    assert "Not yet locked" in md


def test_to_experiment_metrics_seed_returns_none_without_preregistration():
    ev = IdeaEvaluation(verdict="pivot")
    assert to_experiment_metrics_seed(ev) is None


def test_to_experiment_metrics_seed_returns_dict_when_locked():
    ev = IdeaEvaluation(
        verdict="go",
        pre_registration=PreRegistration(
            proxy_metric="val_loss", baseline_value=4.82, target_delta="-0.2",
        ),
    )
    seed = to_experiment_metrics_seed(ev)
    assert seed is not None
    assert seed["metric"] == "val_loss"
    assert seed["baseline_value"] == 4.82
    assert seed["target_delta"] == "-0.2"


def test_to_experiment_metrics_seed_returns_none_when_preregistration_is_empty():
    ev = IdeaEvaluation(verdict="go", pre_registration=PreRegistration())
    assert to_experiment_metrics_seed(ev) is None
