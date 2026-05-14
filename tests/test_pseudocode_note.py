"""Per-algorithm frontmatter round-trip tests."""
from datetime import date
from pathlib import Path

import pytest
from pydantic import ValidationError

from research_assistant.pseudocode import note as pn
from research_assistant.pseudocode.schema import PseudocodeNote


def _sample() -> PseudocodeNote:
    return PseudocodeNote(
        slug="sparse-attn-update",
        kind="train",
        scope="paper",
        anchor="papers/iclr-2026/sparse-attention",
        intent="A single SGD step of the sparse-attention update.",
        package="algpseudocode",
        inputs=[r"$\mathbf{X} \in \mathbb{R}^{B \times L \times d}$", r"parameters $\theta$"],
        outputs=[r"updated parameters $\theta$"],
        complexity_time="O(B L d^2)",
        complexity_space="O(B L d)",
        notation_used=["model", "loss", "gradient"],
        refs=["vaswani-attention-is-all"],
        created=date(2026, 5, 14),
    )


def test_round_trip(tmp_path: Path):
    path = tmp_path / "sparse-attn-update.note.md"
    pn.write_note(path, _sample(), body="Hand notes here.")
    loaded = pn.read_note(path)
    assert loaded.note == _sample()
    assert loaded.body == "Hand notes here."


def test_overwrites(tmp_path: Path):
    path = tmp_path / "x.note.md"
    pn.write_note(path, _sample(), body="first")
    pn.write_note(path, _sample(), body="second")
    assert "second" in path.read_text()
    assert "first" not in path.read_text()


def test_rejects_no_frontmatter(tmp_path: Path):
    path = tmp_path / "bad.note.md"
    path.write_text("no frontmatter here\n")
    with pytest.raises(ValueError):
        pn.read_note(path)


def test_rejects_invalid_kind(tmp_path: Path):
    path = tmp_path / "bad.note.md"
    path.write_text(
        "---\nslug: x\nkind: bogus\nscope: paper\nanchor: a\nintent: i\n"
        "package: algpseudocode\ncreated: 2026-05-14\n---\n",
        encoding="utf-8",
    )
    with pytest.raises(ValidationError):
        pn.read_note(path)


def test_handles_crlf(tmp_path: Path):
    path = tmp_path / "crlf.note.md"
    pn.write_note(path, _sample())
    text = path.read_text()
    path.write_text(text.replace("\n", "\r\n"), encoding="utf-8")
    loaded = pn.read_note(path)
    assert loaded.note == _sample()
