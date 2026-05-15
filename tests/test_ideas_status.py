"""Tests for the idea status board."""
from __future__ import annotations

from datetime import date

import pytest

from research_assistant import common
from research_assistant.ideas import registry as registry_mod
from research_assistant.ideas.registry import IdeaManifest, save_idea, update_idea
from research_assistant.ideas.status import render_status_md, stage_status


@pytest.fixture
def fake_dir(tmp_path, monkeypatch):
    fake = tmp_path / "idea-checks"
    monkeypatch.setattr(common.io, "IDEA_CHECKS_DIR", fake)
    monkeypatch.setattr(registry_mod, "IDEA_CHECKS_DIR", fake)
    return fake


def _sample(slug: str = "smoke") -> IdeaManifest:
    today = date(2026, 5, 15)
    return IdeaManifest(
        slug=slug,
        created=today,
        updated=today,
        statement="test idea",
        area_tags=["ml"],
    )


def test_freshly_captured_idea_marks_captured_stage_done(fake_dir):
    save_idea(_sample())
    s = stage_status("smoke")
    # Manifest exists → captured stage is done even without socratic.md.
    assert s.has_socratic is True
    assert s.has_scout is False
    md = render_status_md("smoke")
    assert "[x] captured" in md
    assert "[ ] scouted" in md


def test_status_advances_with_manifest(fake_dir):
    save_idea(_sample())
    update_idea("smoke", status="evaluated")
    s = stage_status("smoke")
    assert s.has_socratic
    assert s.has_scout
    assert s.has_evaluate
    assert not s.has_venues


def test_artifact_file_marks_stage_done_independently(fake_dir):
    save_idea(_sample())
    (fake_dir / "smoke" / "scout.md").write_text("# scout\n", encoding="utf-8")
    s = stage_status("smoke")
    # Manifest still says "captured" but scout.md exists → scout shows done.
    assert s.has_scout is True


def test_handed_off_status(fake_dir):
    save_idea(_sample())
    update_idea("smoke", status="handed-off")
    md = render_status_md("smoke")
    assert "[x] handed-off" in md
    assert "All stages complete" in md


def test_next_subcommand_hint(fake_dir):
    save_idea(_sample())
    md = render_status_md("smoke")
    # First incomplete stage is "scouted" → next subcommand is `scout`.
    assert "`/idea-check scout`" in md


def test_no_manifest_renders_all_empty(fake_dir):
    md = render_status_md("ghost")
    assert "[ ] captured" in md
    assert "[ ] handed-off" in md
    assert "/idea-check socratic" in md
