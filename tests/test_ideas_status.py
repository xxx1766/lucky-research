"""Tests for the idea status board (gate axis + service checklist)."""
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


def test_freshly_captured_idea_has_no_gate_cleared(fake_dir):
    save_idea(_sample())
    s = stage_status("smoke")
    # Capture is not a gate — an idea on disk has cleared nothing yet.
    assert s.gates_cleared == ()
    assert s.open_gate == "failure-case"
    md = render_status_md("smoke")
    assert "[ ] 1. 真实失效场景 (`failure-case`)" in md
    assert "`/idea-check failure-case`" in md


def test_gates_clear_as_the_manifest_status_advances(fake_dir):
    save_idea(_sample())
    update_idea("smoke", status="mechanism-explained")
    s = stage_status("smoke")
    assert s.cleared("failure-case")
    assert s.cleared("problem-standalone")
    assert s.cleared("mechanism")
    assert not s.cleared("predictions")
    assert s.open_gate == "predictions"


def test_service_artifact_does_not_clear_a_gate(fake_dir):
    save_idea(_sample())
    (fake_dir / "smoke" / "scout.md").write_text("# scout\n", encoding="utf-8")
    s = stage_status("smoke")
    # scout.md is evidence, not progress — the point of the gate refactor.
    assert s.gates_cleared == ()
    assert s.services["scout"] is True
    md = render_status_md("smoke")
    assert "[x] scout 近三年文献" in md


def test_forced_gate_is_flagged_on_the_board(fake_dir):
    save_idea(_sample())
    update_idea(
        "smoke",
        status="problem-standalone",
        forced_gates=["problem-standalone"],
    )
    md = render_status_md("smoke")
    assert "**forced**" in md
    assert "强制放行" in md


def test_handed_off_board(fake_dir):
    save_idea(_sample())
    update_idea("smoke", status="handed-off")
    s = stage_status("smoke")
    assert s.handed_off is True
    assert s.open_gate is None
    md = render_status_md("smoke")
    assert "[x] handed-off" in md
    assert "已交给" in md


def test_all_gates_cleared_points_at_handoff(fake_dir):
    save_idea(_sample())
    update_idea("smoke", status="experiment-ready")
    md = render_status_md("smoke")
    assert "`/idea-check handoff`" in md


def test_no_manifest_renders_an_empty_board(fake_dir):
    md = render_status_md("ghost")
    assert "[ ] 1. 真实失效场景 (`failure-case`)" in md
    assert "[ ] handed-off" in md
    assert "`/idea-check failure-case`" in md
