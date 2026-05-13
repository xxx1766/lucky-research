"""Schema round-trip and validation tests for figure-tool models."""
from datetime import date

import pytest
from pydantic import ValidationError

from research_assistant.figures.schema import (
    FigureNote,
    FigureRef,
    FigureSize,
    PaletteSpec,
)


def test_figure_size_round_trip():
    size = FigureSize(width_in=6.5, height_in=3.0, preset="double-column-half")
    assert size.width_in == 6.5
    assert size.preset == "double-column-half"


def test_figure_size_rejects_negative():
    with pytest.raises(ValidationError):
        FigureSize(width_in=-1.0, height_in=3.0, preset="custom")


def test_figure_note_minimum_valid():
    note = FigureNote(
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
    assert note.slug == "weightlet-arch"
    assert note.backend == "raw-svg"


def test_figure_note_rejects_unknown_kind():
    with pytest.raises(ValidationError):
        FigureNote(
            slug="x", kind="cartoon", scope="paper", anchor="a", intent="i",
            size=FigureSize(width_in=1.0, height_in=1.0, preset="custom"),
            palette="paper-mono", refs=[], backend="raw-svg",
            created=date(2026, 5, 13),
        )


def test_figure_note_rejects_mixed_kind():
    # FigureNote shares FigureKind with FigureRef; the kind_excludes_mixed
    # validator narrows FigureNote to structural|data while FigureRef may keep mixed.
    with pytest.raises(ValidationError):
        FigureNote(
            slug="x", kind="mixed", scope="paper", anchor="a", intent="i",
            size=FigureSize(width_in=1.0, height_in=1.0, preset="custom"),
            palette="paper-mono", refs=[], backend="raw-svg",
            created=date(2026, 5, 13),
        )


def test_figure_ref_accepts_mixed_kind():
    ref = FigureRef(slug="x", source="s", kind="mixed")
    assert ref.kind == "mixed"


def test_figure_ref_minimum_valid():
    ref = FigureRef(
        slug="vaswani-transformer-arch",
        source="Vaswani et al. 2017 (NeurIPS), Fig 1",
        kind="structural",
        tags=["architecture", "encoder-decoder"],
        palette=["#1f77b4", "#ff7f0e"],
        why_i_like_it="Symmetric layout.",
    )
    assert ref.slug == "vaswani-transformer-arch"
    assert ref.kind == "structural"


def test_palette_spec_load():
    p = PaletteSpec(
        name="paper-trio",
        slots={"primary": "#0072B2", "accent": "#D55E00"},
        sequence=["#0072B2", "#D55E00", "#009E73"],
        colorblind_safe=True,
        suggested_for=["single-column"],
    )
    assert p.name == "paper-trio"
    assert p.colorblind_safe is True
