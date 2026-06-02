"""Tests for lit-layer PDF/arXiv helpers."""
from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from research_assistant.lit import (
    _normalize_arxiv_id,
    _year_from_date,
    extract_pdf_text,
    fetch_arxiv,
    parse_metadata,
)

fitz = pytest.importorskip("fitz")


def _build_pdf(path: Path, *pages: str) -> Path:
    doc = fitz.open()
    for content in pages:
        page = doc.new_page()
        page.insert_text((72, 72), content)
    doc.set_metadata({"title": "Test Title", "author": "Doe, Jane; Roe, Richard"})
    doc.save(str(path))
    doc.close()
    return path


def test_extract_pdf_text_returns_concatenated_pages(tmp_path):
    pdf = _build_pdf(tmp_path / "two.pdf", "Hello page one.", "Goodbye page two.")
    text = extract_pdf_text(pdf)
    assert "Hello page one." in text
    assert "Goodbye page two." in text


def test_extract_pdf_text_raises_on_missing(tmp_path):
    with pytest.raises(FileNotFoundError):
        extract_pdf_text(tmp_path / "nope.pdf")


def test_parse_metadata_returns_dict(tmp_path):
    pdf = _build_pdf(tmp_path / "x.pdf", "Hello world.")
    meta = parse_metadata(pdf)
    assert meta["title"] == "Test Title"
    assert "Doe, Jane" in meta["authors"] or "Doe" in " ".join(meta["authors"])
    assert isinstance(meta["authors"], list)


def _build_unmetadated_pdf(path: Path, *pages: str) -> Path:
    """Like _build_pdf, but leaves PDF metadata explicitly empty so the
    title/author fall through to the `_guess_*` heuristics."""
    doc = fitz.open()
    for content in pages:
        page = doc.new_page()
        page.insert_text((72, 72), content)
    # Override the default toolchain metadata: PyMuPDF stamps `creator`/
    # `producer` automatically, but the user-relevant fields stay blank.
    doc.set_metadata({"title": "", "author": ""})
    doc.save(str(path))
    doc.close()
    return path


def test_parse_metadata_falls_back_to_first_line_when_pdf_metadata_blank(tmp_path):
    # No PDF metadata; first non-empty line is treated as title; the next
    # comma-separated line is treated as the author list.
    pdf = _build_unmetadated_pdf(
        tmp_path / "guess.pdf",
        "Toward Better Slugs in Research Code\nAlice Doe, Bob Roe, Carol Lin\n"
        "\n1. Introduction\nbody starts here",
    )
    meta = parse_metadata(pdf)
    assert meta["title"] == "Toward Better Slugs in Research Code"
    # _guess_authors splits on commas and strips whitespace.
    assert "Alice Doe" in meta["authors"]
    assert "Bob Roe" in meta["authors"]
    assert "Carol Lin" in meta["authors"]


def test_parse_metadata_guess_authors_returns_empty_for_no_separator(tmp_path):
    # Single-name byline with no comma/semicolon → heuristic returns [].
    # This is the documented behaviour (audit pass 2 flagged it as a known
    # gap rather than a bug — we lock it in so future tightening is
    # deliberate).
    pdf = _build_unmetadated_pdf(
        tmp_path / "single.pdf",
        "Solo Title Line\nSoloAuthor\n\n1. Introduction\nbody",
    )
    meta = parse_metadata(pdf)
    assert meta["title"] == "Solo Title Line"
    assert meta["authors"] == []


def test_normalize_arxiv_id_handles_versions_and_urls():
    assert _normalize_arxiv_id("2401.12345") == "2401.12345"
    assert _normalize_arxiv_id("2401.12345v3") == "2401.12345"
    assert _normalize_arxiv_id("https://arxiv.org/abs/2401.12345v2") == "2401.12345"


def test_normalize_arxiv_id_rejects_garbage():
    with pytest.raises(ValueError):
        _normalize_arxiv_id("not-an-id")


def test_fetch_arxiv_uses_search_and_downloads(tmp_path):
    fake_result = MagicMock()
    fake_result.download_pdf = MagicMock(return_value=str(tmp_path / "2401.12345.pdf"))
    fake_search = MagicMock()
    fake_search.results = MagicMock(return_value=iter([fake_result]))
    with patch("arxiv.Search", return_value=fake_search) as patched:
        out = fetch_arxiv("2401.12345", tmp_path)
    patched.assert_called_once_with(id_list=["2401.12345"])
    fake_result.download_pdf.assert_called_once()
    assert out == tmp_path / "2401.12345.pdf"


def test_year_from_date_handles_iso_and_dcolon_forms():
    """PyMuPDF normalizes modern PDFs to ``D:YYYYMMDD…`` but hand-exported /
    older PDFs ship raw ``YYYY-MM-DD`` or ``YYYY:MM:DD``. All three forms
    must yield the same year, otherwise arXiv exports silently get year=None.
    """
    assert _year_from_date("D:20240512000000+02'00'") == 2024
    assert _year_from_date("2024-05-12") == 2024
    assert _year_from_date("2024:05:12 11:00:00") == 2024
    assert _year_from_date(None) is None
    assert _year_from_date("") is None
    # Years outside the 1900-2100 sanity window are rejected.
    assert _year_from_date("1500-01-01") is None


def test_fetch_arxiv_raises_when_not_found(tmp_path):
    fake_search = MagicMock()
    fake_search.results = MagicMock(return_value=iter([]))
    with patch("arxiv.Search", return_value=fake_search):
        with pytest.raises(ValueError, match="not found"):
            fetch_arxiv("2401.99999", tmp_path)
