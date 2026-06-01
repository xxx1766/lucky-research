"""Tests for mentor.diff_goals + mentor.weekly_checkin_template."""
from __future__ import annotations

from datetime import date

from research_assistant.mentor import (
    _tokens,
    diff_goals,
    weekly_checkin_template,
)


# ---------- _tokens ----------


def test_tokens_drops_stopwords_and_short_fluff():
    assert _tokens("Use the LoRA finetune on Llama") == {"lora", "finetune", "llama"}


def test_tokens_keeps_hyphenated_terms():
    assert _tokens("kv-cache offload to CPU") == {"kv-cache", "offload", "cpu"}


def test_tokens_empty_inputs():
    assert _tokens("") == set()
    assert _tokens("   ") == set()


# ---------- diff_goals ----------


def test_diff_buckets_by_overlap_count():
    goals = [
        "Ship LoRA finetune eval",       # 2+ activity hits → on_track
        "Investigate KV-cache offload",  # 1 hit → drifting
        "Write talk on retrieval",       # 0 hits → missing
    ]
    activity = [
        "ran LoRA experiments on 7B model",
        "drafted LoRA results figure",
        "looked into KV-cache eviction policy",
    ]
    result = diff_goals(goals, activity)
    assert result["on_track"] == ["Ship LoRA finetune eval"]
    assert result["drifting"] == ["Investigate KV-cache offload"]
    assert result["missing"] == ["Write talk on retrieval"]


def test_diff_preserves_goal_input_order_within_bucket():
    goals = ["alpha foo", "beta foo", "gamma foo"]
    activity = ["foo bar", "foo baz"]
    # all three goals share 'foo' with both entries → all on_track, original order
    assert diff_goals(goals, activity)["on_track"] == ["alpha foo", "beta foo", "gamma foo"]


def test_diff_trims_whitespace_and_skips_empty():
    goals = ["  LoRA work  ", "", "   "]
    activity = ["did some LoRA things"]
    out = diff_goals(goals, activity)
    assert out == {"on_track": [], "drifting": ["LoRA work"], "missing": []}


def test_diff_goal_with_no_content_tokens_is_missing():
    # All-stopword goal — no meaningful tokens to match against.
    goals = ["the and of"]
    activity = ["the system works"]
    out = diff_goals(goals, activity)
    assert out["missing"] == ["the and of"]


def test_diff_no_activity_all_missing():
    out = diff_goals(["finish paper", "run experiments"], [])
    assert out["missing"] == ["finish paper", "run experiments"]
    assert out["on_track"] == []
    assert out["drifting"] == []


def test_diff_empty_goals_returns_empty_buckets():
    assert diff_goals([], ["did stuff"]) == {
        "on_track": [],
        "drifting": [],
        "missing": [],
    }


def test_diff_case_insensitive_match():
    out = diff_goals(["Investigate FlashAttention"], ["used flashattention v3", "ran flashattention bench"])
    assert out["on_track"] == ["Investigate FlashAttention"]


# ---------- weekly_checkin_template ----------


def test_template_includes_date_in_frontmatter_and_heading():
    s = weekly_checkin_template(date(2026, 6, 1))
    assert s.startswith("---\n")
    assert "date: 2026-06-01" in s
    assert "kind: weekly-checkin" in s
    assert "# Weekly check-in — 2026-06-01" in s


def test_template_has_required_sections():
    s = weekly_checkin_template(date(2026, 6, 1))
    for header in (
        "## Goals vs. activity",
        "## Done this week",
        "## Blockers",
        "## Decisions logged",
        "## Mood / energy",
        "## Next week",
    ):
        assert header in s, f"missing section: {header}"


def test_template_references_diff_goals_helper():
    # The template should point users at the actual helper so they don't
    # forget how to bucket their week.
    s = weekly_checkin_template(date(2026, 6, 1))
    assert "mentor.diff_goals" in s
