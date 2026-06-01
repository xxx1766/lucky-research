"""Tests for the OpenReview search + unified search_for_direction dispatcher.

Uses monkeypatch to avoid real network calls — we mock the OpenReviewClient
class and the search_arxiv helper to assert routing + mapping behavior.
"""
from __future__ import annotations

from types import SimpleNamespace

import pytest

from research_assistant.lit import sourcing
from research_assistant.lit.sourcing import (
    PaperRef,
    _openreview_group_for,
    _unwrap_v2,
    _year_from_invitations,
    search_for_direction,
    search_openreview,
)


# ---------- venue → group ----------


def test_group_known_venues():
    assert _openreview_group_for("ICLR") == "ICLR"
    assert _openreview_group_for("iclr-2024") == "ICLR"
    assert _openreview_group_for("NeurIPS_2023") == "NeurIPS"
    assert _openreview_group_for("colm") == "COLM"
    assert _openreview_group_for("TMLR") == "TMLR"


def test_group_unknown_returns_none():
    assert _openreview_group_for("") is None
    assert _openreview_group_for("USENIX") is None
    assert _openreview_group_for("acl") is None


# ---------- helpers ----------


def test_unwrap_v2_handles_dict_and_plain():
    assert _unwrap_v2({"value": "x"}) == "x"
    assert _unwrap_v2("x") == "x"
    assert _unwrap_v2(["a", "b"]) == ["a", "b"]
    assert _unwrap_v2(None) is None


def test_year_from_invitations_picks_first_4digit():
    assert _year_from_invitations(["ICLR.cc/2024/Conference/-/Submission"]) == 2024
    assert _year_from_invitations(["NeurIPS.cc/2023/Conference/-/Edit"]) == 2023
    assert _year_from_invitations(None) is None
    assert _year_from_invitations(["bad/string"]) is None


# ---------- mock notes ----------


def _make_note(*, nid: str, title: str, abstract: str, authors: list[str],
               invitations: list[str]):
    """Build a v2-shape mock note."""
    return SimpleNamespace(
        id=nid,
        content={
            "title": {"value": title},
            "abstract": {"value": abstract},
            "authors": {"value": authors},
        },
        invitations=invitations,
    )


def _make_review_note():
    """A non-paper note (review) that should be filtered out."""
    return SimpleNamespace(
        id="REV1",
        content={"summary": {"value": "good"}, "rating": {"value": "8"}},
        invitations=["ICLR.cc/2024/Conference/Submission1/-/Official_Review"],
    )


def _install_fake_client(monkeypatch, notes_to_return):
    class _FakeClient:
        def __init__(self, *a, **kw):
            pass

        def search_notes(self, term, content="all", group="all", limit=None, **_):
            self.last_term = term
            self.last_group = group
            return list(notes_to_return)

    import openreview.api as oa
    monkeypatch.setattr(oa, "OpenReviewClient", _FakeClient)
    return _FakeClient


# ---------- search_openreview ----------


def test_search_openreview_unsupported_venue_returns_empty(monkeypatch):
    # Should not even try to import / call OpenReview
    assert search_openreview("USENIX-OSDI", "query") == []


def test_search_openreview_maps_paper_notes(monkeypatch):
    fake_notes = [
        _make_note(
            nid="ABC123",
            title="My Paper",
            abstract="An abstract about LoRA.",
            authors=["A. Author", "B. Author"],
            invitations=["ICLR.cc/2024/Conference/-/Submission"],
        ),
        _make_review_note(),  # should be filtered
        _make_note(
            nid="DEF456",
            title="Another Paper",
            abstract="Different abstract.",
            authors=["C. Author"],
            invitations=["ICLR.cc/2024/Conference/-/Submission"],
        ),
    ]
    _install_fake_client(monkeypatch, fake_notes)
    refs = search_openreview("ICLR", "lora")
    assert len(refs) == 2
    assert refs[0].id == "ABC123"
    assert refs[0].title == "My Paper"
    assert refs[0].authors == ["A. Author", "B. Author"]
    assert refs[0].year == 2024
    assert refs[0].venue == "ICLR"
    assert refs[0].url == "https://openreview.net/forum?id=ABC123"
    assert refs[0].pdf_url == "https://openreview.net/pdf?id=ABC123"


def test_search_openreview_year_range_filters(monkeypatch):
    fake = [
        _make_note(nid="A", title="A", abstract="x", authors=["x"],
                   invitations=["ICLR.cc/2024/Conference/-/Submission"]),
        _make_note(nid="B", title="B", abstract="x", authors=["x"],
                   invitations=["ICLR.cc/2022/Conference/-/Submission"]),
        _make_note(nid="C", title="C", abstract="x", authors=["x"],
                   invitations=["ICLR.cc/2025/Conference/-/Submission"]),
    ]
    _install_fake_client(monkeypatch, fake)
    refs = search_openreview("ICLR", "x", year_range=(2024, 2025))
    assert sorted([r.id for r in refs]) == ["A", "C"]


def test_search_openreview_swallows_network_errors(monkeypatch):
    class _BrokenClient:
        def __init__(self, *a, **kw):
            raise RuntimeError("network down")
    import openreview.api as oa
    monkeypatch.setattr(oa, "OpenReviewClient", _BrokenClient)
    # Should not raise — return empty
    assert search_openreview("ICLR", "x") == []


def test_search_openreview_respects_max_results(monkeypatch):
    fake = [
        _make_note(nid=f"N{i}", title=f"T{i}", abstract="x", authors=["a"],
                   invitations=["ICLR.cc/2024/Conference/-/Submission"])
        for i in range(50)
    ]
    _install_fake_client(monkeypatch, fake)
    refs = search_openreview("ICLR", "x", max_results=10)
    assert len(refs) == 10


# ---------- search_for_direction ----------


def test_dispatch_supported_venue_uses_openreview(monkeypatch):
    fake = [_make_note(nid="X", title="t", abstract="a", authors=["A"],
                        invitations=["ICLR.cc/2024/Conference/-/Submission"])]
    _install_fake_client(monkeypatch, fake)
    called_arxiv = []
    monkeypatch.setattr(sourcing, "search_arxiv",
                        lambda *a, **kw: called_arxiv.append(True) or [])
    refs = search_for_direction("ICLR", ["lora", "finetuning"])
    assert len(refs) == 1
    assert refs[0].id == "X"
    assert called_arxiv == []  # arxiv NOT called


def test_dispatch_unsupported_venue_falls_back_to_arxiv(monkeypatch):
    sentinel = [PaperRef(id="arxiv-1", title="t", authors=["a"], abstract="x", year=2024)]
    monkeypatch.setattr(sourcing, "search_arxiv", lambda *a, **kw: sentinel)
    refs = search_for_direction("USENIX-OSDI", ["scheduling"])
    assert refs == sentinel


def test_dispatch_empty_openreview_falls_back_to_arxiv(monkeypatch):
    _install_fake_client(monkeypatch, [])  # OpenReview returns nothing
    sentinel = [PaperRef(id="arxiv-2", title="t", authors=["a"], abstract="x", year=2024)]
    monkeypatch.setattr(sourcing, "search_arxiv", lambda *a, **kw: sentinel)
    refs = search_for_direction("ICLR", ["something"])
    assert refs == sentinel


def test_dispatch_empty_keywords_returns_empty(monkeypatch):
    monkeypatch.setattr(sourcing, "search_arxiv",
                        lambda *a, **kw: pytest.fail("should not be called"))
    assert search_for_direction("ICLR", []) == []
    assert search_for_direction("ICLR", ["", "  "]) == []
