"""SVG → PDF/PNG export tests."""
from pathlib import Path

import pytest

from research_assistant.figures import export as fe

_MINIMAL_SVG = """<?xml version="1.0" encoding="UTF-8"?>
<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 100 100" width="100" height="100">
  <rect x="10" y="10" width="80" height="80" fill="#0072B2"/>
  <text x="50" y="55" text-anchor="middle" fill="white" font-size="14">ok</text>
</svg>
"""


def test_export_creates_pdf_and_png(tmp_path: Path):
    svg = tmp_path / "fig.svg"
    svg.write_text(_MINIMAL_SVG, encoding="utf-8")
    pdf, png = fe.export(svg)
    assert pdf.exists() and pdf.stat().st_size > 0
    assert png.exists() and png.stat().st_size > 0
    assert pdf.suffix == ".pdf"
    assert png.suffix == ".png"


def test_export_is_idempotent(tmp_path: Path):
    svg = tmp_path / "fig.svg"
    svg.write_text(_MINIMAL_SVG, encoding="utf-8")
    fe.export(svg)
    first_png_size = (svg.with_suffix(".png")).stat().st_size
    fe.export(svg)
    second_png_size = (svg.with_suffix(".png")).stat().st_size
    # Compare PNG sizes (deterministic for same input); PDF may embed timestamps.
    assert first_png_size == second_png_size


def test_export_rejects_missing_svg(tmp_path: Path):
    with pytest.raises(FileNotFoundError):
        fe.export(tmp_path / "missing.svg")


def test_export_malformed_svg_raises(tmp_path: Path):
    svg = tmp_path / "bad.svg"
    svg.write_text("<not really svg", encoding="utf-8")
    with pytest.raises(fe.ExportError):
        fe.export(svg)
