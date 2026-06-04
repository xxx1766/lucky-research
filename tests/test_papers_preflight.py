"""Tests for `research_assistant.papers.preflight` — write-stage hard gates."""
from __future__ import annotations

from research_assistant.papers.preflight import write_preflight


def _setup(tmp_path, *, venue_brief=True, focus=True, scout=False, exempt=False):
    venue_dir = tmp_path / "NeurIPS-2026"
    direction_dir = venue_dir / "diffusion-ft"
    direction_dir.mkdir(parents=True)
    if venue_brief:
        (venue_dir / "_venue.md").write_text("page limit: 9\n", encoding="utf-8")
    if focus:
        (direction_dir / "focused-problem.md").write_text("# problem\n", encoding="utf-8")
    if scout:
        rp = direction_dir / "related-papers"
        rp.mkdir()
        (rp / "vaswani2017.md").write_text("# attn\n", encoding="utf-8")
    expert = "---\n"
    if exempt:
        expert += "literature_exempt: true\n"
    expert += "---\nbody\n"
    (direction_dir / "expert.md").write_text(expert, encoding="utf-8")
    return direction_dir, venue_dir


def test_all_gates_pass_for_method(tmp_path):
    d, v = _setup(tmp_path)
    res = write_preflight(d, v, "method")
    assert res.blocked is False
    assert res.failures == []
    assert {c.name for c in res.checks} == {"venue", "focus"}


def test_missing_venue_blocks(tmp_path):
    d, v = _setup(tmp_path, venue_brief=False)
    res = write_preflight(d, v, "method")
    assert res.blocked is True
    names = [c.name for c in res.failures]
    assert "venue" in names
    venue_check = next(c for c in res.checks if c.name == "venue")
    assert venue_check.fix_hint == "/paper venue <slug>"


def test_missing_focus_blocks(tmp_path):
    d, v = _setup(tmp_path, focus=False)
    res = write_preflight(d, v, None)  # outline scaffold call
    assert res.blocked is True
    assert "focus" in [c.name for c in res.failures]


def test_intro_without_literature_blocks(tmp_path):
    d, v = _setup(tmp_path, scout=False)
    res = write_preflight(d, v, "intro")
    assert res.blocked is True
    lit = next(c for c in res.checks if c.name == "literature")
    assert lit.passed is False
    assert "/paper scout" in lit.fix_hint


def test_intro_with_scouted_literature_passes(tmp_path):
    d, v = _setup(tmp_path, scout=True)
    res = write_preflight(d, v, "intro")
    assert res.blocked is False


def test_intro_literature_exempt_passes(tmp_path):
    d, v = _setup(tmp_path, scout=False, exempt=True)
    res = write_preflight(d, v, "intro")
    assert res.blocked is False
    lit = next(c for c in res.checks if c.name == "literature")
    assert lit.passed is True


def test_results_without_evidence_warns_not_blocks(tmp_path):
    d, v = _setup(tmp_path)
    res = write_preflight(d, v, "results", evidence_present=False)
    assert res.blocked is False  # evidence gate is a warning
    assert [c.name for c in res.warnings] == ["evidence"]


def test_results_with_evidence_no_warning(tmp_path):
    d, v = _setup(tmp_path)
    res = write_preflight(d, v, "results", evidence_present=True)
    assert res.warnings == []


def test_results_evidence_falls_back_to_disk(tmp_path):
    d, v = _setup(tmp_path)
    results = d / "experiments" / "results"
    results.mkdir(parents=True)
    (results / "v1.0.json").write_text("{}", encoding="utf-8")
    res = write_preflight(d, v, "results")  # evidence_present=None -> disk check
    assert res.warnings == []


def test_render_blocked_message(tmp_path):
    d, v = _setup(tmp_path, venue_brief=False)
    res = write_preflight(d, v, "method")
    msg = res.render()
    assert "blocked" in msg
    assert "venue" in msg
    assert "/paper venue" in msg


def test_render_ok_message(tmp_path):
    d, v = _setup(tmp_path)
    res = write_preflight(d, v, "method")
    assert "ok" in res.render()
