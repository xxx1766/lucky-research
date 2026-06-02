"""Tests for the project-level research-notes triplet."""
from __future__ import annotations

from datetime import date

import pytest

from research_assistant.mentor import research_notes as rn


@pytest.fixture
def tmp_project(tmp_path, monkeypatch):
    """Redirect RESEARCH_NOTES_DIR to a temp dir so tests don't touch real outputs/."""
    fake_dir = tmp_path / "research-notes"
    monkeypatch.setattr(rn, "RESEARCH_NOTES_DIR", fake_dir)
    return fake_dir


def test_slugify_basic():
    assert rn.slugify("Long-context KV cache study") == "long-context-kv-cache-study"
    assert rn.slugify("  multiple   spaces  ") == "multiple-spaces"


def test_slugify_empty_raises():
    with pytest.raises(ValueError):
        rn.slugify("    ")
    with pytest.raises(ValueError):
        rn.slugify("---")


def test_init_project_creates_triplet(tmp_project):
    pdir = rn.init_project("kv-cache-eviction", "KV-cache eviction policies", question="When does eviction help inference latency?")
    assert pdir == tmp_project / "kv-cache-eviction"
    assert (pdir / "state.yaml").is_file()
    assert (pdir / "findings.md").is_file()
    assert (pdir / "log.md").is_file()


def test_init_project_refuses_overwrite(tmp_project):
    rn.init_project("dup", "Dup project")
    with pytest.raises(FileExistsError):
        rn.init_project("dup", "Dup project")


def test_invalid_slug_raises(tmp_project):
    with pytest.raises(ValueError):
        rn.project_dir("../escape")
    with pytest.raises(ValueError):
        rn.project_dir("")
    with pytest.raises(ValueError):
        rn.project_dir(".hidden")


def test_read_state_roundtrip(tmp_project):
    rn.init_project("rt", "Roundtrip", question="?")
    state = rn.read_state("rt")
    assert state.project.slug == "rt"
    assert state.project.title == "Roundtrip"
    assert state.project.status == "active"
    # Mutate + write back + re-read.
    state.hypotheses.append(rn.Hypothesis(id="H1", statement="X causes Y"))
    state.outer_loop.cycle = 2
    state.outer_loop.last_direction = "deepen"
    rn.write_state("rt", state)
    state2 = rn.read_state("rt")
    assert len(state2.hypotheses) == 1
    assert state2.hypotheses[0].id == "H1"
    assert state2.outer_loop.cycle == 2
    assert state2.outer_loop.last_direction == "deepen"


def test_append_log_first_row_replaces_placeholder(tmp_project):
    rn.init_project("logp", "Log project")
    n = rn.append_log("logp", "bootstrap", "literature scan done", today=date(2026, 6, 2))
    assert n == 1
    rows = rn.parse_log("logp")
    assert rows == [{"n": 1, "date": "2026-06-02", "kind": "bootstrap", "summary": "literature scan done"}]


def test_append_log_multiple_rows_increment(tmp_project):
    rn.init_project("logm", "Many-log project")
    rn.append_log("logm", "bootstrap", "first", today=date(2026, 6, 1))
    rn.append_log("logm", "inner-loop", "second", today=date(2026, 6, 2))
    rn.append_log("logm", "outer-loop", "third", today=date(2026, 6, 3))
    rows = rn.parse_log("logm")
    assert [r["n"] for r in rows] == [1, 2, 3]
    assert [r["kind"] for r in rows] == ["bootstrap", "inner-loop", "outer-loop"]
    assert rows[1]["summary"] == "second"


def test_append_log_rejects_bad_kind(tmp_project):
    rn.init_project("badkind", "Bad kind")
    with pytest.raises(ValueError):
        rn.append_log("badkind", "not-a-kind", "x")


def test_append_log_escapes_pipe(tmp_project):
    rn.init_project("pipe", "Pipe project")
    rn.append_log("pipe", "bootstrap", "a | b | c", today=date(2026, 6, 1))
    rows = rn.parse_log("pipe")
    # The escaped \| survives back through the parser as part of the summary.
    assert rows[0]["summary"] == r"a \| b \| c"


def test_append_finding_appends_under_existing_section(tmp_project):
    rn.init_project("find", "Find project")
    rn.append_finding("find", "Key results", "- KV eviction shaves 12% latency at batch=4.")
    text = rn.findings_path("find").read_text(encoding="utf-8")
    assert "- KV eviction shaves 12% latency at batch=4." in text
    # Section header still intact.
    assert text.count("## Key results") == 1


def test_append_finding_creates_section_if_missing(tmp_project):
    rn.init_project("newsec", "New section")
    rn.append_finding("newsec", "Surprise box", "Something unexpected showed up.")
    text = rn.findings_path("newsec").read_text(encoding="utf-8")
    assert "## Surprise box" in text
    assert "Something unexpected showed up." in text


def test_list_projects(tmp_project):
    assert rn.list_projects() == []
    rn.init_project("a-project", "A")
    rn.init_project("b-project", "B")
    assert rn.list_projects() == ["a-project", "b-project"]


def test_to_agentdb_payload_excludes_long_prose(tmp_project):
    rn.init_project("payload", "Payload project", question="why")
    state = rn.read_state("payload")
    state.experiments.bound_slugs = ["llm-finetune-eval"]
    state.outer_loop.cycle = 1
    payload = rn.to_agentdb_payload(state)
    assert payload["kind"] == "research_notes"
    assert payload["slug"] == "payload"
    assert payload["title"] == "Payload project"
    assert payload["bound_experiments"] == ["llm-finetune-eval"]
    # No giant text fields.
    assert "findings" not in payload
    assert "log" not in payload


def test_read_state_missing_raises(tmp_project):
    with pytest.raises(FileNotFoundError):
        rn.read_state("nonexistent")


def test_append_log_missing_file_raises(tmp_project):
    with pytest.raises(FileNotFoundError):
        rn.append_log("nofile", "bootstrap", "x")
