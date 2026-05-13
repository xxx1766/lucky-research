"""Smoke tests for the boss-profile corpus helpers."""

import os
from datetime import date

import pytest
from pydantic import ValidationError

from research_assistant.mentor import boss_profile
from research_assistant.mentor.boss_profile import (
    BossMeeting,
    BossProfile,
    latest_report,
    list_meetings,
    list_reports,
    meeting_slug,
    recent_meetings,
    rehearsal_path,
    rehearsal_slug,
    report_path,
)


def test_meeting_slug_iso_shape():
    assert meeting_slug(date(2026, 5, 12)) == "2026-05-12"
    assert meeting_slug(date(2024, 1, 1)) == "2024-01-01"


def test_boss_profile_minimal_dict():
    profile = BossProfile(name="Prof. X")
    assert profile.name == "Prof. X"
    assert profile.research_interests == []
    assert profile.hot_buttons == []
    assert profile.role is None


def test_boss_profile_full_dict():
    profile = BossProfile(
        name="Prof. X",
        role="PI",
        research_interests=["AI for systems", "compilers"],
        recent_papers=["arxiv:2401.xxxxx"],
        collaborators=["Prof. Y"],
        communication_style="terse",
        hot_buttons=["real systems measurement"],
        sore_spots=["over-claiming"],
        preferred_format="written memo",
    )
    assert "compilers" in profile.research_interests
    assert profile.communication_style == "terse"


def test_boss_meeting_minimal_dict():
    meeting = BossMeeting(date=date(2026, 5, 12), topic="Q2 progress")
    assert meeting.date == date(2026, 5, 12)
    assert meeting.topic == "Q2 progress"
    assert meeting.action_items == []
    assert meeting.mood is None


def test_boss_meeting_requires_date_and_topic():
    with pytest.raises(ValidationError):
        BossMeeting(date=date(2026, 5, 12))  # type: ignore[call-arg]
    with pytest.raises(ValidationError):
        BossMeeting(topic="Q2 progress")  # type: ignore[call-arg]


def test_list_meetings_empty_when_dir_absent(tmp_path, monkeypatch):
    monkeypatch.setattr(boss_profile, "BOSS_MEETINGS_DIR", tmp_path / "missing")
    assert list_meetings() == []


def test_list_meetings_skips_underscore_files(tmp_path, monkeypatch):
    (tmp_path / "2026-05-10.md").write_text("ok")
    (tmp_path / "2026-05-11.md").write_text("ok")
    (tmp_path / "_scratch.md").write_text("skip")
    monkeypatch.setattr(boss_profile, "BOSS_MEETINGS_DIR", tmp_path)
    names = [p.name for p in list_meetings()]
    assert names == ["2026-05-10.md", "2026-05-11.md"]


def test_recent_meetings_newest_first(tmp_path, monkeypatch):
    for d in ("2026-05-10", "2026-05-12", "2026-05-11"):
        (tmp_path / f"{d}.md").write_text("ok")
    monkeypatch.setattr(boss_profile, "BOSS_MEETINGS_DIR", tmp_path)
    names = [p.name for p in recent_meetings(n=2)]
    assert names == ["2026-05-12.md", "2026-05-11.md"]


def test_list_reports_empty_when_dir_absent(tmp_path, monkeypatch):
    monkeypatch.setattr(boss_profile, "BOSS_REPORTS_DIR", tmp_path / "missing")
    assert list_reports() == []


def test_list_reports_skips_underscore_files(tmp_path, monkeypatch):
    (tmp_path / "q2-progress.md").write_text("ok")
    (tmp_path / "paper-plan.md").write_text("ok")
    (tmp_path / "_scratch.md").write_text("skip")
    monkeypatch.setattr(boss_profile, "BOSS_REPORTS_DIR", tmp_path)
    names = [p.name for p in list_reports()]
    assert names == ["paper-plan.md", "q2-progress.md"]


def test_latest_report_none_when_empty(tmp_path, monkeypatch):
    monkeypatch.setattr(boss_profile, "BOSS_REPORTS_DIR", tmp_path)
    assert latest_report() is None


def test_latest_report_picks_most_recently_modified(tmp_path, monkeypatch):
    older = tmp_path / "older.md"
    newer = tmp_path / "newer.md"
    older.write_text("o")
    newer.write_text("n")
    os.utime(older, (1_700_000_000, 1_700_000_000))
    os.utime(newer, (1_800_000_000, 1_800_000_000))
    monkeypatch.setattr(boss_profile, "BOSS_REPORTS_DIR", tmp_path)
    assert latest_report() == newer


def test_report_path_appends_md_extension(tmp_path, monkeypatch):
    monkeypatch.setattr(boss_profile, "BOSS_REPORTS_DIR", tmp_path)
    assert report_path("q2-progress").name == "q2-progress.md"
    assert report_path("q2-progress.md").name == "q2-progress.md"


def test_report_path_rejects_traversal(tmp_path, monkeypatch):
    monkeypatch.setattr(boss_profile, "BOSS_REPORTS_DIR", tmp_path)
    with pytest.raises(ValueError):
        report_path("../profile")
    with pytest.raises(ValueError):
        report_path("../../etc/passwd")
    with pytest.raises(ValueError):
        report_path("")


def test_rehearsal_slug_format():
    assert rehearsal_slug(date(2026, 5, 13), "q2-progress") == "2026-05-13-q2-progress"
    # strips trailing .md if caller passes a filename
    assert rehearsal_slug(date(2026, 5, 13), "q2.md") == "2026-05-13-q2"
    with pytest.raises(ValueError):
        rehearsal_slug(date(2026, 5, 13), "")


def test_rehearsal_path_collision_suffix(tmp_path, monkeypatch):
    monkeypatch.setattr(boss_profile, "BOSS_REHEARSALS_DIR", tmp_path)
    d = date(2026, 5, 13)
    first = rehearsal_path(d, "q2-progress")
    assert first.name == "2026-05-13-q2-progress.md"
    first.write_text("first")
    second = rehearsal_path(d, "q2-progress")
    assert second.name == "2026-05-13-q2-progress-2.md"
    second.write_text("second")
    third = rehearsal_path(d, "q2-progress")
    assert third.name == "2026-05-13-q2-progress-3.md"
