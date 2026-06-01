"""Tests for the boss-profile + past-work YAML-frontmatter parsers."""
from __future__ import annotations

from datetime import date

import pytest

from research_assistant.mentor.boss_profile import (
    BossMeeting,
    BossProfile,
    parse_meeting,
    parse_profile,
)
from research_assistant.mentor.boss_profile import to_agentdb_payload as boss_payload
from research_assistant.mentor.past_work import (
    PastWorkEntry,
    parse_entry,
)
from research_assistant.mentor.past_work import to_agentdb_payload as past_payload


# ---------- boss profile ----------


def test_parse_profile_full_frontmatter(tmp_path):
    p = tmp_path / "profile.md"
    p.write_text(
        "---\n"
        "name: Prof. X\n"
        "role: PI\n"
        "research_interests:\n"
        "  - systems\n"
        "  - networking\n"
        "hot_buttons: [originality]\n"
        "sore_spots: []\n"
        "communication_style: terse + concrete\n"
        "---\n"
        "Body paragraph about Prof. X.\n",
        encoding="utf-8",
    )
    prof = parse_profile(p)
    assert isinstance(prof, BossProfile)
    assert prof.name == "Prof. X"
    assert prof.role == "PI"
    assert prof.research_interests == ["systems", "networking"]
    assert prof.hot_buttons == ["originality"]
    assert "Body paragraph" in prof.body


def test_parse_profile_minimal(tmp_path):
    p = tmp_path / "profile.md"
    p.write_text("---\nname: X\n---\n", encoding="utf-8")
    prof = parse_profile(p)
    assert prof.name == "X"
    assert prof.research_interests == []


def test_parse_profile_missing_required_raises(tmp_path):
    p = tmp_path / "profile.md"
    p.write_text("---\nrole: PI\n---\n", encoding="utf-8")  # no 'name'
    with pytest.raises(Exception):
        parse_profile(p)


# ---------- boss meeting ----------


def test_parse_meeting_with_explicit_date(tmp_path):
    p = tmp_path / "2026-05-12.md"
    p.write_text(
        "---\n"
        "date: 2026-05-12\n"
        "topic: q2 progress\n"
        'mode: "1:1"\n'
        "duration_min: 45\n"
        "mood: positive\n"
        "feedback: keep iterating\n"
        "action_items:\n"
        "  - draft v2\n"
        "  - run benchmark\n"
        "---\n"
        "Notes from the meeting.\n",
        encoding="utf-8",
    )
    m = parse_meeting(p)
    assert isinstance(m, BossMeeting)
    assert m.date == date(2026, 5, 12)
    assert m.topic == "q2 progress"
    assert m.duration_min == 45
    assert m.action_items == ["draft v2", "run benchmark"]


def test_parse_meeting_date_falls_back_to_filename(tmp_path):
    p = tmp_path / "2025-11-01.md"
    p.write_text("---\ntopic: standup\n---\nbody\n", encoding="utf-8")
    m = parse_meeting(p)
    assert m.date == date(2025, 11, 1)


# ---------- payload shape ----------


def test_boss_payload_profile_excludes_prose():
    prof = BossProfile(
        name="X", role="PI", research_interests=["a"],
        hot_buttons=["b"], sore_spots=["c"], communication_style="terse",
        body="long prose here that should not be in the index",
    )
    payload = boss_payload(prof)
    assert payload["kind"] == "boss_profile"
    assert payload["name"] == "X"
    assert "body" not in payload
    assert "long prose" not in str(payload)


def test_boss_payload_meeting_serializes_date():
    m = BossMeeting(date=date(2026, 5, 12), topic="t", action_items=["a"])
    payload = boss_payload(m)
    assert payload["kind"] == "boss_meeting"
    assert payload["date"] == "2026-05-12"
    assert payload["action_items"] == ["a"]


def test_boss_payload_rejects_other_types():
    with pytest.raises(TypeError):
        boss_payload({"not": "an entry"})  # type: ignore[arg-type]


# ---------- past_work ----------


def test_parse_entry_full(tmp_path):
    p = tmp_path / "memory-rag.md"
    p.write_text(
        "---\n"
        "slug: memory-rag\n"
        "title: Memory-Aware RAG\n"
        "year: 2024\n"
        "venue: NeurIPS\n"
        "status: published\n"
        "tags: [rag, memory]\n"
        "links: [arxiv:2401.0001]\n"
        "what_i_learned:\n"
        "  - lesson 1\n"
        "  - lesson 2\n"
        "---\n"
        "Free-form body about the project.\n",
        encoding="utf-8",
    )
    e = parse_entry(p)
    assert isinstance(e, PastWorkEntry)
    assert e.slug == "memory-rag"
    assert e.year == 2024
    assert e.tags == ["rag", "memory"]
    assert e.what_i_learned == ["lesson 1", "lesson 2"]
    assert "Free-form body" in e.body


def test_parse_entry_slug_defaults_to_filename(tmp_path):
    p = tmp_path / "alpha-beta.md"
    p.write_text("---\ntitle: Alpha-Beta\n---\nbody\n", encoding="utf-8")
    e = parse_entry(p)
    assert e.slug == "alpha-beta"
    assert e.title == "Alpha-Beta"


def test_past_payload_excludes_prose():
    e = PastWorkEntry(
        slug="x", title="X", tags=["a"], what_i_learned=["w"],
        body="long prose", abstract="long abstract",
    )
    payload = past_payload(e)
    assert payload["kind"] == "past_work"
    assert payload["slug"] == "x"
    assert payload["what_i_learned"] == ["w"]
    assert "body" not in payload
    assert "abstract" not in payload


# ---------- smoke: real on-disk profile if present ----------


def test_real_profile_md_parses_if_present():
    """If the user has a real inputs/boss-profile/profile.md, parsing should not crash."""
    from research_assistant.common.io import INPUTS_DIR

    real = INPUTS_DIR / "boss-profile" / "profile.md"
    if not real.is_file():
        pytest.skip("no real profile.md present")
    prof = parse_profile(real)
    assert isinstance(prof, BossProfile)
    assert prof.name  # at least name must be present
