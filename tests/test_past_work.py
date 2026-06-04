"""Smoke tests for the past-work corpus helpers."""

from research_assistant.mentor.past_work import (
    PastWorkEntry,
    list_entries,
    slugify,
)


def test_slugify_shape():
    assert (
        slugify("Contrastive pre-training for code retrieval")
        == "contrastive-pre-training-for-code-retrieval"
    )
    assert slugify("CONTRASTIVE-PRETRAIN") == "contrastive-pretrain"
    assert slugify("  spaced  ") == "spaced"


def test_list_entries_returns_list():
    result = list_entries()
    assert isinstance(result, list)


def test_mentor_package_exposes_submodules():
    # The skills/agents use the attribute form (mentor.past_work.X); the package
    # must re-export submodules so that resolves in a fresh import.
    import research_assistant.mentor as mentor

    assert hasattr(mentor.past_work, "compose_past_work_entry")
    assert hasattr(mentor.research_notes, "__name__")
    assert hasattr(mentor.boss_profile, "__name__")


def test_past_work_entry_minimal_dict():
    entry = PastWorkEntry(slug="x", title="Title")
    assert entry.slug == "x"
    assert entry.title == "Title"
    assert entry.tags == []
    assert entry.year is None


def test_past_work_entry_full_dict():
    entry = PastWorkEntry(
        slug="contrastive-code-retrieval",
        title="Contrastive pre-training for code retrieval",
        year=2024,
        venue="EMNLP",
        status="published",
        tags=["retrieval", "contrastive"],
        links=["arxiv:2401.xxxxx"],
        what_i_learned=["bigger batches > longer training"],
    )
    assert entry.year == 2024
    assert "retrieval" in entry.tags
