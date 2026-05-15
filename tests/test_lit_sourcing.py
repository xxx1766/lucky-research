"""Tests for the real arxiv search implementation in lit.sourcing.

Uses a fake `arxiv` module loaded into ``sys.modules`` so no network is hit.
"""
from __future__ import annotations

import sys
import types
from datetime import datetime

import pytest

from research_assistant.lit import sourcing


class _FakeAuthor:
    def __init__(self, name: str):
        self.name = name


class _FakeResult:
    def __init__(self, rid: str, title: str, year: int, authors: list[str]):
        # entry_id mirrors arxiv's format: full URL with version
        self.entry_id = f"http://arxiv.org/abs/{rid}v1"
        self.title = title
        self.authors = [_FakeAuthor(n) for n in authors]
        self.summary = f"Abstract for {title}."
        self.published = datetime(year, 6, 1)
        self.pdf_url = f"http://arxiv.org/pdf/{rid}v1"


class _FakeSearch:
    def __init__(self, *, query, max_results, sort_by):
        self.query = query
        self.max_results = max_results
        self.sort_by = sort_by


class _FakeSortCriterion:
    Relevance = "relevance"


class _FakeClient:
    """Hand-rolled fake of ``arxiv.Client`` for unit tests."""

    canned: list[_FakeResult] = []

    def results(self, _search: _FakeSearch):  # noqa: D401
        return iter(self.canned)


@pytest.fixture
def fake_arxiv(monkeypatch):
    mod = types.ModuleType("arxiv")
    mod.Client = _FakeClient
    mod.Search = _FakeSearch
    mod.SortCriterion = _FakeSortCriterion
    monkeypatch.setitem(sys.modules, "arxiv", mod)
    yield _FakeClient


def test_search_arxiv_no_year_filter_returns_all(fake_arxiv):
    fake_arxiv.canned = [
        _FakeResult("2401.00001", "Modern paper", 2024, ["Alice"]),
        _FakeResult("1801.00001", "Older paper", 2018, ["Bob"]),
    ]
    refs = sourcing.search_arxiv("rag", max_results=10)
    assert len(refs) == 2
    assert refs[0].title == "Modern paper"
    assert refs[0].id == "2401.00001"
    assert refs[0].venue == "arXiv"
    assert refs[0].url.endswith("v1")
    assert refs[0].year == 2024


def test_search_arxiv_year_filter_drops_old(fake_arxiv):
    fake_arxiv.canned = [
        _FakeResult("2401.00001", "Modern", 2024, ["A"]),
        _FakeResult("1801.00001", "Older", 2018, ["B"]),
        _FakeResult("2310.00001", "In range", 2023, ["C"]),
    ]
    refs = sourcing.search_arxiv("rag", year_range=(2023, 2026), max_results=10)
    titles = [r.title for r in refs]
    assert "Older" not in titles
    assert "Modern" in titles
    assert "In range" in titles


def test_search_arxiv_truncates_to_max_results(fake_arxiv):
    fake_arxiv.canned = [
        _FakeResult(f"24{i:02d}.00001", f"Paper {i}", 2024, ["A"]) for i in range(10)
    ]
    refs = sourcing.search_arxiv("rag", max_results=3)
    assert len(refs) == 3


def test_search_arxiv_maps_author_names(fake_arxiv):
    fake_arxiv.canned = [
        _FakeResult("2401.00001", "Paper", 2024, ["Alice X", "Bob Y", "Carol Z"]),
    ]
    refs = sourcing.search_arxiv("rag", max_results=5)
    assert refs[0].authors == ["Alice X", "Bob Y", "Carol Z"]


def test_search_arxiv_strips_version_from_id(fake_arxiv):
    fake_arxiv.canned = [
        _FakeResult("2401.12345", "Paper", 2024, ["A"]),
    ]
    refs = sourcing.search_arxiv("rag", max_results=5)
    # entry_id is "http://arxiv.org/abs/2401.12345v1"; bare id should be "2401.12345"
    assert refs[0].id == "2401.12345"
