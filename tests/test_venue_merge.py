"""Idempotent merge of the `## Writing conventions` block into `_venue.md`."""
from __future__ import annotations

import pytest

from research_assistant.papers.venue_merge import (
    SENTINEL_BEGIN,
    SENTINEL_END,
    extract_writing_conventions,
    upsert_writing_conventions,
)


def _write(path, text: str) -> None:
    path.write_text(text, encoding="utf-8")


def test_upsert_initial_insert_appends_block(tmp_path):
    venue_md = tmp_path / "_venue.md"
    _write(
        venue_md,
        "# OSDI 2027\n\n## Quick facts\n\n- Page limit: 14\n",
    )

    upsert_writing_conventions(venue_md, "Body line 1\n\nBody line 2")

    result = venue_md.read_text(encoding="utf-8")
    assert "## Quick facts" in result
    assert "- Page limit: 14" in result
    assert "## Writing conventions" in result
    assert SENTINEL_BEGIN in result
    assert SENTINEL_END in result
    # Body lands between sentinels.
    inside = result.split(SENTINEL_BEGIN, 1)[1].split(SENTINEL_END, 1)[0]
    assert "Body line 1" in inside
    assert "Body line 2" in inside


def test_upsert_replaces_sentinel_fenced_block(tmp_path):
    venue_md = tmp_path / "_venue.md"
    _write(
        venue_md,
        f"# Title\n\n## Writing conventions\n{SENTINEL_BEGIN}\nOLD BODY\n{SENTINEL_END}\n",
    )

    upsert_writing_conventions(venue_md, "NEW BODY")

    result = venue_md.read_text(encoding="utf-8")
    assert "OLD BODY" not in result
    assert "NEW BODY" in result
    # Exactly one pair of sentinels.
    assert result.count(SENTINEL_BEGIN) == 1
    assert result.count(SENTINEL_END) == 1
    # Heading isn't duplicated.
    assert result.count("## Writing conventions") == 1


def test_upsert_preserves_manual_edits_outside_block(tmp_path):
    venue_md = tmp_path / "_venue.md"
    before = "# Title\n\nMy manual note above.\n\n## Quick facts\n\n- Page limit: 14\n"
    after = "\n\n## Trends\n\n- Trend A\n"
    _write(
        venue_md,
        f"{before}\n## Writing conventions\n{SENTINEL_BEGIN}\nold\n{SENTINEL_END}\n{after}",
    )

    upsert_writing_conventions(venue_md, "fresh body")

    result = venue_md.read_text(encoding="utf-8")
    assert result.startswith(before)
    assert result.rstrip().endswith(after.rstrip())
    assert "fresh body" in result
    assert "old" not in result


def test_upsert_upgrades_headed_section_without_sentinels(tmp_path):
    venue_md = tmp_path / "_venue.md"
    _write(
        venue_md,
        "# Title\n\n## Writing conventions\nHand-written prose.\nMore prose.\n\n## Trends\n\n- Trend\n",
    )

    upsert_writing_conventions(venue_md, "BODY")

    result = venue_md.read_text(encoding="utf-8")
    assert "Hand-written prose." not in result
    assert "BODY" in result
    assert SENTINEL_BEGIN in result
    assert SENTINEL_END in result
    # Following section untouched.
    assert "## Trends" in result
    assert "- Trend" in result


def test_upsert_raises_on_corrupted_sentinels(tmp_path):
    venue_md = tmp_path / "_venue.md"
    _write(venue_md, f"# T\n\n## Writing conventions\n{SENTINEL_BEGIN}\nbody\n")
    with pytest.raises(ValueError, match="Corrupted"):
        upsert_writing_conventions(venue_md, "x")


def test_upsert_raises_on_missing_venue_md(tmp_path):
    venue_md = tmp_path / "missing.md"
    with pytest.raises(FileNotFoundError):
        upsert_writing_conventions(venue_md, "x")


def test_extract_writing_conventions_returns_none_when_absent():
    assert extract_writing_conventions("# Title\n\nNo block here.\n") is None


def test_extract_writing_conventions_round_trip(tmp_path):
    venue_md = tmp_path / "_venue.md"
    _write(venue_md, "# Title\n")
    upsert_writing_conventions(venue_md, "BODY CONTENT")
    text = venue_md.read_text(encoding="utf-8")
    inner = extract_writing_conventions(text)
    assert inner is not None
    assert "BODY CONTENT" in inner
