"""Tests for idea persistence — manifest, registry, status advancement."""
from __future__ import annotations

from datetime import date

import pytest

from research_assistant import common
from research_assistant.ideas import registry as registry_mod
from research_assistant.ideas.registry import (
    IdeaManifest,
    index_path,
    list_ideas,
    load_idea,
    manifest_path,
    render_index_md,
    save_idea,
    to_agentdb_payload,
    update_idea,
)


@pytest.fixture
def fake_dir(tmp_path, monkeypatch):
    fake = tmp_path / "idea-checks"
    monkeypatch.setattr(common.io, "IDEA_CHECKS_DIR", fake)
    monkeypatch.setattr(registry_mod, "IDEA_CHECKS_DIR", fake)
    return fake


def _sample(slug: str = "memory-aware-rag") -> IdeaManifest:
    today = date(2026, 5, 15)
    return IdeaManifest(
        slug=slug,
        created=today,
        updated=today,
        statement="Re-rank RAG chunks by past user feedback signals.",
        area_tags=["ml", "ir"],
        body="One-paragraph context.",
    )


def test_save_and_load_round_trip(fake_dir):
    m = _sample()
    save_idea(m)
    assert manifest_path(m.slug).is_file()
    back = load_idea(m.slug)
    assert back.slug == m.slug
    assert back.statement == m.statement
    assert back.area_tags == ["ml", "ir"]
    assert back.status == "captured"


def test_save_rewrites_index(fake_dir):
    save_idea(_sample("alpha-idea"))
    save_idea(_sample("beta-idea"))
    idx = index_path().read_text(encoding="utf-8")
    assert "alpha-idea" in idx
    assert "beta-idea" in idx


def test_list_ideas_sorted_by_updated_desc(fake_dir):
    older = _sample("old")
    save_idea(older)
    newer = _sample("new").model_copy(update={"updated": date(2026, 6, 1)})
    save_idea(newer)
    items = list_ideas()
    assert [i.slug for i in items] == ["new", "old"]


def test_update_idea_bumps_updated_and_advances_status(fake_dir, monkeypatch):
    m = _sample()
    save_idea(m)

    fake_today = date(2026, 6, 10)

    class _Date(date):
        @classmethod
        def today(cls):  # type: ignore[override]
            return fake_today

    monkeypatch.setattr(registry_mod, "date", _Date)
    new = update_idea(m.slug, status="mechanism-explained")
    assert new.status == "mechanism-explained"
    assert new.updated == fake_today


def test_status_is_monotonically_forward(fake_dir):
    m = _sample().model_copy(update={"status": "mechanism-explained"})
    save_idea(m)
    # Try to "regress" back to captured — should stay mechanism-explained.
    new = update_idea(m.slug, status="captured")
    assert new.status == "mechanism-explained"


def test_invalid_slug_rejected(fake_dir):
    bad = _sample().model_copy(update={"slug": "Bad Slug"})
    with pytest.raises(ValueError):
        save_idea(bad)


def test_load_nonexistent_raises(fake_dir):
    with pytest.raises(FileNotFoundError):
        load_idea("ghost")


def test_render_index_empty(fake_dir):
    md = render_index_md([])
    assert "no ideas captured" in md


def test_to_agentdb_payload_shape(fake_dir):
    payload = to_agentdb_payload(_sample())
    assert payload["slug"] == "memory-aware-rag"
    assert payload["area_tags"] == ["ml", "ir"]
    assert payload["status"] == "captured"


def test_reindex_from_disk_returns_manifests(fake_dir):
    save_idea(_sample("a"))
    save_idea(_sample("b"))
    rebuilt = registry_mod.reindex_from_disk()
    assert {m.slug for m in rebuilt} == {"a", "b"}


def test_malformed_manifest_is_skipped_in_list(fake_dir):
    save_idea(_sample("good"))
    bad_dir = fake_dir / "broken"
    bad_dir.mkdir()
    (bad_dir / "idea.md").write_text("no frontmatter here\n", encoding="utf-8")
    items = list_ideas()
    assert [i.slug for i in items] == ["good"]


def test_forced_gates_roundtrip_and_show_on_the_index(fake_dir):
    save_idea(_sample("forced"))
    update_idea("forced", status="problem-standalone",
                forced_gates=["problem-standalone"])
    assert load_idea("forced").forced_gates == ["problem-standalone"]
    # An override must stay visible in the vault listing, not just in gates.md.
    md = render_index_md(list_ideas())
    assert "forced" in md
    assert "⚠1 forced" in md


def test_manifest_without_forced_gates_omits_the_key(fake_dir):
    save_idea(_sample("clean"))
    text = (fake_dir / "clean" / "idea.md").read_text(encoding="utf-8")
    assert "forced_gates" not in text
    assert load_idea("clean").forced_gates == []
