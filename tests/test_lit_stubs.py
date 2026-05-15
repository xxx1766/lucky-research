"""Tests for lit-layer PDF/arXiv helpers."""
from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from research_assistant.lit import (
    _normalize_arxiv_id,
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


def test_fetch_arxiv_raises_when_not_found(tmp_path):
    fake_search = MagicMock()
    fake_search.results = MagicMock(return_value=iter([]))
    with patch("arxiv.Search", return_value=fake_search):
        with pytest.raises(ValueError, match="not found"):
            fetch_arxiv("2401.99999", tmp_path)
