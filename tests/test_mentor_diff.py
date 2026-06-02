"""Tests for mentor.diff_goals + mentor.weekly_checkin_template + stale_experiments."""
from __future__ import annotations

import os
from datetime import date, datetime, timezone

import pytest

from research_assistant import common
from research_assistant import experiments as exp_pkg
from research_assistant.mentor import (
    _tokens,
    diff_goals,
    stale_experiments,
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
        "## Stale experiments",
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


# ---------- stale_experiments ----------


@pytest.fixture
def fake_experiments(tmp_path, monkeypatch):
    fake = tmp_path / "experiments"
    fake.mkdir()
    monkeypatch.setattr(common.io, "EXPERIMENTS_DIR", fake)
    monkeypatch.setattr(exp_pkg, "EXPERIMENTS_DIR", fake)
    return fake


def _seed_experiment(
    root, slug: str, *,
    status: str = "active",
    title: str = "X",
    version_ages_days: list[int] | None = None,
    manifest_age_days: int = 0,
    reference: date,
) -> None:
    """Create an experiment with versions whose mtimes are set so the LATEST
    version is ``version_ages_days[-1]`` days before ``reference``.

    If ``version_ages_days`` is None, no versions are created and the manifest
    mtime is set to ``manifest_age_days`` before ``reference``.
    """
    d = root / slug
    d.mkdir(parents=True, exist_ok=True)
    manifest = d / "manifest.md"
    manifest.write_text(
        "---\n"
        f"slug: {slug}\n"
        f"title: {title}\n"
        "created_at: 2026-01-01\n"
        "repo:\n  url: u\n  branch: main\n"
        "papers: []\n"
        f"status: {status}\n"
        "---\nbody\n",
        encoding="utf-8",
    )
    if version_ages_days is None:
        ts = _date_to_epoch(reference, manifest_age_days)
        os.utime(manifest, (ts, ts))
        return
    versions_dir = d / "versions"
    versions_dir.mkdir()
    for i, age in enumerate(version_ages_days):
        vfile = versions_dir / f"v1.{i}.md"
        vfile.write_text(
            f"---\nversion: v1.{i}\ndescription: x\nstatus: completed\n---\nbody\n",
            encoding="utf-8",
        )
        ts = _date_to_epoch(reference, age)
        os.utime(vfile, (ts, ts))


def _date_to_epoch(reference: date, days_before: int) -> float:
    target = datetime.combine(reference, datetime.min.time(), tzinfo=timezone.utc)
    return target.timestamp() - days_before * 86400


def test_stale_returns_empty_when_dir_missing(tmp_path, monkeypatch):
    monkeypatch.setattr(common.io, "EXPERIMENTS_DIR", tmp_path / "nope")
    monkeypatch.setattr(exp_pkg, "EXPERIMENTS_DIR", tmp_path / "nope")
    assert stale_experiments(today=date(2026, 6, 1)) == []


def test_stale_excludes_recent_versions(fake_experiments):
    today = date(2026, 6, 1)
    # Two versions: latest is 3 days old → not stale at default 14d threshold.
    _seed_experiment(fake_experiments, "fresh", version_ages_days=[30, 3], reference=today)
    assert stale_experiments(today=today) == []


def test_stale_flags_old_latest_version(fake_experiments):
    today = date(2026, 6, 1)
    # Latest version is 20 days old → stale at default 14d.
    _seed_experiment(fake_experiments, "drift", version_ages_days=[40, 20], reference=today)
    out = stale_experiments(today=today)
    assert len(out) == 1
    assert out[0]["slug"] == "drift"
    assert out[0]["latest_version"] == "v1.1"
    assert out[0]["days_since_update"] == 20


def test_stale_uses_manifest_mtime_when_no_versions(fake_experiments):
    today = date(2026, 6, 1)
    # No versions; manifest itself is 30d old → stale.
    _seed_experiment(fake_experiments, "no-versions", version_ages_days=None,
                     manifest_age_days=30, reference=today)
    out = stale_experiments(today=today)
    assert len(out) == 1
    assert out[0]["latest_version"] is None
    assert out[0]["days_since_update"] == 30


def test_stale_excludes_paused_archived_abandoned(fake_experiments):
    today = date(2026, 6, 1)
    for status in ("paused", "archived", "abandoned"):
        _seed_experiment(fake_experiments, f"x-{status}",
                         status=status, version_ages_days=[60], reference=today)
    assert stale_experiments(today=today) == []


def test_stale_threshold_is_inclusive_lower_bound(fake_experiments):
    today = date(2026, 6, 1)
    _seed_experiment(fake_experiments, "edge", version_ages_days=[14], reference=today)
    # 14 days old at min_age_days=14 → stale (>=)
    out = stale_experiments(min_age_days=14, today=today)
    assert [h["slug"] for h in out] == ["edge"]
    # 14 days old at min_age_days=15 → not stale (<)
    assert stale_experiments(min_age_days=15, today=today) == []


def test_stale_sorted_oldest_first(fake_experiments):
    today = date(2026, 6, 1)
    _seed_experiment(fake_experiments, "mid", version_ages_days=[30], reference=today)
    _seed_experiment(fake_experiments, "oldest", version_ages_days=[90], reference=today)
    _seed_experiment(fake_experiments, "newish-stale", version_ages_days=[15], reference=today)
    out = stale_experiments(today=today)
    assert [h["slug"] for h in out] == ["oldest", "mid", "newish-stale"]
    assert [h["days_since_update"] for h in out] == [90, 30, 15]
