"""Tests for compose_past_work_entry + quick_capture_defaults.

Used by ``/mentor add-past-work``. See `tests/test_past_work_repo.py` for the
companion test style (monkeypatched PAST_WORK_DIR fixture).
"""
from __future__ import annotations

from datetime import date
from pathlib import Path

import pytest

from research_assistant.common import io as common_io
from research_assistant.mentor import past_work
from research_assistant.mentor.past_work import (
    compose_past_work_entry,
    parse_entry,
    quick_capture_defaults,
)


@pytest.fixture
def fake_past_work_dir(tmp_path, monkeypatch) -> Path:
    root = tmp_path / "past-work"
    root.mkdir()
    monkeypatch.setattr(past_work, "PAST_WORK_DIR", root)
    monkeypatch.setattr(common_io, "PAST_WORK_DIR", root)
    return root


# ---------- quick_capture_defaults ----------


def test_quick_capture_defaults_basic_fields():
    d = quick_capture_defaults("LoRA finetune scratchpad", today=date(2026, 6, 2))
    assert d["slug"] == "lora-finetune-scratchpad"
    assert d["title"] == "LoRA finetune scratchpad"
    assert d["year"] == 2026
    assert d["venue"] == "internal"
    assert d["status"] == "in-progress"
    assert d["tags"] == []
    assert d["links"] == []
    assert d["abstract"] is None
    assert d["what_i_learned"] == []
    assert d["methods_used"] is None
    assert d["outcome"] is None
    assert d["notes_for_future"] is None


def test_quick_capture_defaults_today_defaults_to_now():
    # No today= passed — function should use date.today(); year must be a
    # current 4-digit year, not None.
    d = quick_capture_defaults("X")
    assert isinstance(d["year"], int)
    assert d["year"] >= 2026


def test_quick_capture_defaults_picks_collision_safe_slug(fake_past_work_dir):
    # Pre-create a companion folder at the natural slug so next_available_slug
    # has to bump.
    (fake_past_work_dir / "lora-finetune").mkdir()
    d = quick_capture_defaults("LoRA finetune", today=date(2026, 6, 2))
    assert d["slug"] == "lora-finetune-2"


# ---------- compose_past_work_entry ----------


def test_compose_writes_minimal_entry(fake_past_work_dir):
    path = compose_past_work_entry(
        slug="x", title="Just X", year=2026,
        venue="internal", status="in-progress",
    )
    assert path == fake_past_work_dir / "x.md"
    text = path.read_text()
    # Frontmatter
    assert "slug: x" in text
    assert "title: Just X" in text
    assert "year: 2026" in text
    assert "venue: internal" in text
    assert "status: in-progress" in text
    # All five sections present, with TODO placeholders for the empty ones
    for header in (
        "## Abstract", "## What I learned", "## Methods used",
        "## Outcome / impact", "## Notes for future-me",
    ):
        assert header in text
    assert text.count("_TODO_:") == 5  # all sections empty → 5 TODOs


def test_compose_renders_provided_fields_without_todo(fake_past_work_dir):
    path = compose_past_work_entry(
        slug="lora", title="LoRA notes",
        abstract="One paragraph on LoRA.",
        what_i_learned=["rank 8 is usually enough", "merge before inference"],
        methods_used="HF transformers + peft + a single A100.",
        outcome="Used as a building block for two downstream projects.",
        notes_for_future="If revisiting, start from commit abc1234.",
    )
    text = path.read_text()
    assert "_TODO_:" not in text
    assert "One paragraph on LoRA." in text
    assert "- rank 8 is usually enough" in text
    assert "- merge before inference" in text
    assert "HF transformers + peft + a single A100." in text
    assert "two downstream projects" in text
    assert "commit abc1234" in text


def test_compose_refuses_overwrite(fake_past_work_dir):
    compose_past_work_entry(slug="x", title="first")
    with pytest.raises(FileExistsError):
        compose_past_work_entry(slug="x", title="second attempt")


def test_compose_force_overwrites(fake_past_work_dir):
    compose_past_work_entry(slug="x", title="first")
    compose_past_work_entry(slug="x", title="overwritten", force=True)
    text = (fake_past_work_dir / "x.md").read_text()
    assert "overwritten" in text
    assert "first\n" not in text  # title in frontmatter is replaced


def test_compose_emits_tags_and_links(fake_past_work_dir):
    path = compose_past_work_entry(
        slug="x", title="X",
        tags=["lora", "inference"],
        links=["arxiv:2106.09685", "github:huggingface/peft"],
    )
    text = path.read_text()
    assert "- lora" in text
    assert "- inference" in text
    assert "arxiv:2106.09685" in text
    assert "github:huggingface/peft" in text


def test_compose_output_round_trips_through_parse_entry(fake_past_work_dir):
    path = compose_past_work_entry(
        slug="lora", title="LoRA notes", year=2026,
        venue="internal", status="in-progress",
        tags=["lora"], links=["github:x/y"],
        abstract="A study of low-rank adapters.",
        what_i_learned=["rank 8 is usually enough", "alpha scaling matters"],
    )
    entry = parse_entry(path)
    assert entry.slug == "lora"
    assert entry.title == "LoRA notes"
    assert entry.year == 2026
    assert entry.venue == "internal"
    assert entry.status == "in-progress"
    assert entry.tags == ["lora"]
    assert entry.links == ["github:x/y"]
    # abstract + what_i_learned live in the body; parse_entry must recover them
    # (they feed the AgentDB index value via to_agentdb_payload).
    assert entry.what_i_learned == ["rank 8 is usually enough", "alpha scaling matters"]
    assert entry.abstract == "A study of low-rank adapters."


def test_parse_entry_skips_todo_placeholders(fake_past_work_dir):
    # An entry left with default _TODO_ placeholders must parse to empty, not
    # capture the placeholder text into the index.
    path = compose_past_work_entry(slug="bare", title="Bare")
    entry = parse_entry(path)
    assert entry.what_i_learned == []
    assert entry.abstract is None


def test_compose_omits_optional_frontmatter_fields_when_None(fake_past_work_dir):
    path = compose_past_work_entry(slug="x", title="X")
    text = path.read_text()
    # year / venue / status are None → not in the YAML
    assert "year:" not in text
    assert "venue:" not in text
    assert "status:" not in text
    # tags / links are always emitted (defaults to []), so the schema stays
    # predictable for downstream readers.
    assert "tags: []" in text
    assert "links: []" in text


# ---------- compose + quick_capture_defaults together ----------


def test_full_capture_flow_works_end_to_end(fake_past_work_dir):
    """Mirrors what `/mentor add-past-work` does internally: defaults → compose."""
    d = quick_capture_defaults("Diffusion finetune", today=date(2026, 6, 2))
    path = compose_past_work_entry(**d)
    entry = parse_entry(path)
    assert entry.slug == "diffusion-finetune"
    assert entry.title == "Diffusion finetune"
    assert entry.year == 2026
    assert entry.status == "in-progress"
