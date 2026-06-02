"""Tests for the scout helper — uses mocked arxiv search."""
from __future__ import annotations

from datetime import date

import pytest

from research_assistant.ideas import scout as scout_mod
from research_assistant.ideas.scout import (
    ScoutedPaper,
    ScoutGaps,
    ScoutResult,
    default_year_range,
    render_scout_md,
    scout_recent_papers,
    to_agentdb_payload,
)
from research_assistant.lit.sourcing import PaperRef


def _ref(rid: str, year: int, title: str = "Paper Title") -> PaperRef:
    return PaperRef(
        id=rid,
        title=title,
        authors=["A. Author", "B. Author"],
        abstract="abstract",
        year=year,
        venue="arXiv",
        url=f"https://arxiv.org/abs/{rid}",
        pdf_url=f"https://arxiv.org/pdf/{rid}.pdf",
    )


def test_default_year_range_is_last_3_years_inclusive():
    today = date(2026, 5, 15)
    assert default_year_range(today) == (2023, 2026)


def test_scout_recent_papers_passes_query_and_year(monkeypatch):
    calls: dict = {}

    def fake_search(query, year_range=None, max_results=25):
        calls["query"] = query
        calls["year_range"] = year_range
        calls["max_results"] = max_results
        return [_ref("2401.00001", 2024), _ref("2310.00001", 2023)]

    monkeypatch.setattr(scout_mod, "search_arxiv", fake_search)
    result = scout_recent_papers("retrieval augmented generation",
                                 year_range=(2023, 2026), max_results=10)
    assert calls["query"] == "retrieval augmented generation"
    assert calls["year_range"] == (2023, 2026)
    assert calls["max_results"] == 10
    assert len(result.papers) == 2
    assert result.papers[0].relation_note == ""  # filled by skill prompt


def test_scout_empty_query_raises(monkeypatch):
    monkeypatch.setattr(scout_mod, "search_arxiv", lambda **kw: [])
    with pytest.raises(ValueError):
        scout_recent_papers("   ")


def test_scout_uses_default_range_when_unspecified(monkeypatch):
    captured: dict = {}

    def fake_search(query, year_range=None, max_results=25):
        captured["year_range"] = year_range
        return []

    monkeypatch.setattr(scout_mod, "search_arxiv", fake_search)
    scout_recent_papers("rag")
    assert captured["year_range"] is not None
    lo, hi = captured["year_range"]
    assert hi - lo == 3


def test_render_groups_by_year_descending():
    result = ScoutResult(
        query="rag",
        year_range=(2023, 2026),
        papers=[
            ScoutedPaper(ref=_ref("a", 2024, "Newer paper")),
            ScoutedPaper(ref=_ref("b", 2023, "Older paper")),
        ],
    )
    md = render_scout_md(result)
    assert md.index("## 2024") < md.index("## 2023")
    assert "Newer paper" in md
    assert "Older paper" in md


def test_render_includes_relation_note_when_present():
    result = ScoutResult(
        query="rag",
        year_range=(2023, 2026),
        papers=[
            ScoutedPaper(
                ref=_ref("a", 2024),
                relation_note="They do X; we propose Y on top.",
            ),
        ],
    )
    md = render_scout_md(result)
    assert "They do X; we propose Y on top." in md
    assert "Relation note pending" not in md


def test_render_empty_result_explains_fallback():
    result = ScoutResult(query="rag", year_range=(2023, 2026), papers=[])
    md = render_scout_md(result)
    assert "No arXiv hits" in md
    assert "WebSearch" in md


def test_agentdb_payload_round_trip():
    result = ScoutResult(
        query="rag",
        year_range=(2023, 2026),
        papers=[ScoutedPaper(ref=_ref("a", 2024), relation_note="note")],
    )
    payload = to_agentdb_payload(result)
    assert payload["query"] == "rag"
    assert payload["year_range"] == [2023, 2026]
    assert payload["papers"][0]["ref"]["id"] == "a"
    assert payload["papers"][0]["relation_note"] == "note"
    # Empty gaps still appear in the payload as an empty struct.
    assert "gaps" in payload
    assert payload["gaps"]["tried"] == []


def test_render_omits_gaps_section_when_all_buckets_empty():
    result = ScoutResult(
        query="rag",
        year_range=(2023, 2026),
        papers=[ScoutedPaper(ref=_ref("a", 2024))],
    )
    md = render_scout_md(result)
    assert "## Gaps from this scout" not in md


def test_render_includes_gaps_section_with_populated_buckets():
    result = ScoutResult(
        query="rag",
        year_range=(2023, 2026),
        papers=[ScoutedPaper(ref=_ref("a", 2024))],
        gaps=ScoutGaps(
            tried=["Dense re-ranking with cross-encoders"],
            untried=["Re-ranking by per-user feedback signals"],
            where_broken=["Cross-encoders degrade past 8k context"],
            future_work=[
                "Atlas-XL §6: extending to multimodal retrieval (https://x.org/abs/...)"
            ],
        ),
    )
    md = render_scout_md(result)
    assert "## Gaps from this scout" in md
    assert "### Tried in the last 3 years" in md
    assert "### Not tried yet" in md
    assert "### Where existing methods break" in md
    assert "### Discussion-section future work" in md
    assert "Re-ranking by per-user feedback signals" in md
    assert "Cross-encoders degrade past 8k context" in md


def test_render_omits_empty_buckets_but_keeps_populated_ones():
    result = ScoutResult(
        query="rag",
        year_range=(2023, 2026),
        papers=[],
        gaps=ScoutGaps(untried=["Just one bucket has content"]),
    )
    md = render_scout_md(result)
    assert "## Gaps from this scout" in md
    assert "### Not tried yet" in md
    assert "### Tried in the last 3 years" not in md
    assert "### Where existing methods break" not in md


def test_gaps_in_agentdb_payload():
    result = ScoutResult(
        query="rag",
        year_range=(2023, 2026),
        papers=[],
        gaps=ScoutGaps(tried=["X"], untried=["Y"]),
    )
    payload = to_agentdb_payload(result)
    assert payload["gaps"]["tried"] == ["X"]
    assert payload["gaps"]["untried"] == ["Y"]
