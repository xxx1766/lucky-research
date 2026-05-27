"""Tests for the contrarian micro-flow trace + sibling-idea creation."""
from __future__ import annotations

from datetime import date

import pytest

from research_assistant import common
from research_assistant.ideas import registry as registry_mod
from research_assistant.ideas.contrarian import (
    ContrarianTrace,
    record_turn,
    render_contrarian_md,
    render_scout_appendix,
    to_agentdb_payload,
)
from research_assistant.ideas.registry import (
    IdeaManifest,
    create_variant_idea,
    idea_dir,
    load_idea,
    manifest_path,
    save_idea,
)


@pytest.fixture
def fake_dir(tmp_path, monkeypatch):
    fake = tmp_path / "idea-checks"
    monkeypatch.setattr(common.io, "IDEA_CHECKS_DIR", fake)
    monkeypatch.setattr(registry_mod, "IDEA_CHECKS_DIR", fake)
    return fake


def _make_trace(**overrides) -> ContrarianTrace:
    base = ContrarianTrace(
        parent_slug="memory-aware-rag",
        parent_statement="Re-rank RAG chunks by past user feedback.",
    )
    for k, v in overrides.items():
        setattr(base, k, v)
    return base


def _filled_trace(accepted: bool = True) -> ContrarianTrace:
    t = _make_trace(
        mainstream_pattern="Bigger encoders + larger top-k retrieval.",
        shared_assumption="Quality scales with retrieval breadth.",
        inversion="Keep retrieval tiny; learn from feedback at re-rank time.",
        win_condition="Better recall@5 with 10x fewer retrieved chunks.",
        final_statement="Tiny-retrieval RAG re-ranked by per-user feedback signals.",
        accepted=accepted,
    )
    record_turn(t, "Q1?", t.mainstream_pattern)
    record_turn(t, "Q2?", t.shared_assumption)
    record_turn(t, "Q3?", t.inversion)
    record_turn(t, "Q4?", t.win_condition)
    return t


def test_record_turn_appends_four_turns():
    t = _make_trace()
    record_turn(t, "Q1?", "A1")
    record_turn(t, "Q2?", "A2")
    record_turn(t, "Q3?", "A3")
    record_turn(t, "Q4?", "A4")
    assert [tt.question for tt in t.turns] == ["Q1?", "Q2?", "Q3?", "Q4?"]
    assert [tt.answer for tt in t.turns] == ["A1", "A2", "A3", "A4"]


def test_record_turn_rejects_empty_question():
    t = _make_trace()
    with pytest.raises(ValueError):
        record_turn(t, "  ", "answer")


def test_render_scout_appendix_deterministic():
    t = _filled_trace(accepted=True)
    md = render_scout_appendix(t)
    assert md.startswith("## Contrarian framings")
    # Q ordering preserved.
    q1 = md.index("Q1.")
    q2 = md.index("Q2.")
    q3 = md.index("Q3.")
    q4 = md.index("Q4.")
    assert q1 < q2 < q3 < q4
    assert "Distilled framing:" in md
    assert "Tiny-retrieval RAG" in md
    assert "[[memory-aware-rag-contrarian]]" in md


def test_render_scout_appendix_empty_when_skipped():
    t = _make_trace(mainstream_pattern="<skipped>")
    assert t.skipped is True
    assert render_scout_appendix(t) == ""


def test_render_scout_appendix_omits_sibling_link_when_not_accepted():
    t = _filled_trace(accepted=False)
    md = render_scout_appendix(t)
    assert "## Contrarian framings" in md
    assert "Sibling idea:" not in md


def test_render_contrarian_md_includes_parent_backlink():
    t = _filled_trace(accepted=True)
    md = render_contrarian_md(t)
    assert "[[memory-aware-rag]]" in md
    assert "## Distilled contrarian statement" in md
    assert "Tiny-retrieval RAG" in md
    assert "### Q1." in md
    assert "### Q4." in md


def test_to_agentdb_payload_round_trip():
    t = _filled_trace(accepted=True)
    payload = to_agentdb_payload(t)
    assert payload["parent_slug"] == "memory-aware-rag"
    assert payload["mainstream_pattern"] == t.mainstream_pattern
    assert payload["shared_assumption"] == t.shared_assumption
    assert payload["inversion"] == t.inversion
    assert payload["win_condition"] == t.win_condition
    assert payload["final_statement"] == t.final_statement
    assert payload["accepted"] is True
    assert payload["skipped"] is False
    assert len(payload["turns"]) == 4
    assert payload["turns"][0]["question"] == "Q1?"


def _seed_parent(slug: str = "memory-aware-rag") -> IdeaManifest:
    today = date(2026, 5, 15)
    m = IdeaManifest(
        slug=slug,
        created=today,
        updated=today,
        statement="Re-rank RAG chunks by past user feedback signals.",
        area_tags=["ml", "ir"],
        body="Parent context.",
    )
    save_idea(m)
    return m


def test_create_variant_idea_creates_sibling(fake_dir):
    parent = _seed_parent()
    parent_bytes_before = manifest_path(parent.slug).read_bytes()

    sibling = create_variant_idea(
        parent_slug=parent.slug,
        suffix="contrarian",
        new_statement="Tiny-retrieval RAG re-ranked by per-user feedback.",
    )

    assert sibling.slug == "memory-aware-rag-contrarian"
    assert sibling.parent_idea == parent.slug
    assert sibling.area_tags == parent.area_tags
    assert sibling.status == "captured"
    assert idea_dir(sibling.slug).is_dir()
    assert manifest_path(sibling.slug).is_file()

    # Parent untouched.
    assert manifest_path(parent.slug).read_bytes() == parent_bytes_before


def test_create_variant_idea_collision_appends_counter(fake_dir):
    _seed_parent()
    first = create_variant_idea(
        parent_slug="memory-aware-rag",
        suffix="contrarian",
        new_statement="First contrarian framing.",
    )
    assert first.slug == "memory-aware-rag-contrarian"

    second = create_variant_idea(
        parent_slug="memory-aware-rag",
        suffix="contrarian",
        new_statement="Second contrarian framing.",
    )
    assert second.slug == "memory-aware-rag-contrarian-2"


def test_manifest_serializes_parent_idea(fake_dir):
    _seed_parent()
    sibling = create_variant_idea(
        parent_slug="memory-aware-rag",
        suffix="contrarian",
        new_statement="Inverted framing.",
    )
    back = load_idea(sibling.slug)
    assert back.parent_idea == "memory-aware-rag"
    assert back.statement == "Inverted framing."

    # AgentDB payload also carries it.
    from research_assistant.ideas.registry import to_agentdb_payload as manifest_payload

    payload = manifest_payload(back)
    assert payload["parent_idea"] == "memory-aware-rag"
