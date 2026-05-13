"""Per-figure frontmatter round-trip tests."""
from datetime import date
from pathlib import Path

import pytest
from pydantic import ValidationError

from research_assistant.figures import note as fn
from research_assistant.figures.schema import FigureNote, FigureSize


def _sample() -> FigureNote:
    return FigureNote(
        slug="weightlet-arch",
        kind="structural",
        scope="paper",
        anchor="papers/iclr-2026/main",
        intent="One-second comprehension of weightlet sharing.",
        size=FigureSize(width_in=6.5, height_in=3.0, preset="double-column-half"),
        palette="paper-trio",
        refs=["vaswani-transformer-arch"],
        backend="raw-svg",
        created=date(2026, 5, 13),
    )


def test_write_and_parse_round_trip(tmp_path: Path):
    path = tmp_path / "weightlet-arch.note.md"
    fn.write_note(path, _sample(), body="Optional human notes.\n")
    loaded = fn.read_note(path)
    assert loaded.note == _sample()
    assert loaded.body.strip() == "Optional human notes."


def test_write_overwrites(tmp_path: Path):
    path = tmp_path / "x.note.md"
    fn.write_note(path, _sample(), body="first")
    fn.write_note(path, _sample(), body="second")
    assert "second" in path.read_text()
    assert "first" not in path.read_text()


def test_read_note_rejects_no_frontmatter(tmp_path: Path):
    path = tmp_path / "bad.note.md"
    path.write_text("no frontmatter here\n")
    with pytest.raises(ValueError):
        fn.read_note(path)


def test_read_note_rejects_bad_yaml(tmp_path: Path):
    path = tmp_path / "bad.note.md"
    path.write_text("---\nslug: x\nkind: invalid-kind\n---\n")
    with pytest.raises(ValidationError):
        fn.read_note(path)


def test_read_note_handles_crlf(tmp_path: Path):
    # Some users edit on Windows or have git core.autocrlf=true.
    path = tmp_path / "crlf.note.md"
    fn.write_note(path, _sample())
    text = path.read_text()
    path.write_text(text.replace("\n", "\r\n"), encoding="utf-8")
    loaded = fn.read_note(path)
    assert loaded.note == _sample()


def test_write_note_with_no_body(tmp_path: Path):
    path = tmp_path / "x.note.md"
    fn.write_note(path, _sample())
    loaded = fn.read_note(path)
    assert loaded.body == ""
