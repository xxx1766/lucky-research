"""Tests for venue suggestion."""
from __future__ import annotations

from datetime import date

import pytest

from research_assistant import common
from research_assistant.ideas import venues as venues_mod
from research_assistant.ideas.venues import (
    VENUE_REGISTRY,
    render_venues_md,
    suggest_venues,
)


@pytest.fixture
def fake_papers_dir(tmp_path, monkeypatch):
    """Redirect PAPERS_DIR into tmp_path so _venue.md curation tests are isolated."""
    fake = tmp_path / "papers"
    fake.mkdir()
    monkeypatch.setattr(common.io, "PAPERS_DIR", fake)
    monkeypatch.setattr(venues_mod, "PAPERS_DIR", fake)
    return fake


def test_ml_tag_returns_neurips_icml_iclr_first(fake_papers_dir):
    matches = suggest_venues(["ml"], today=date(2026, 5, 15), top_k=5)
    names = {m.venue.slug for m in matches}
    assert {"neurips", "icml", "iclr"}.issubset(names)


def test_unknown_tag_returns_empty(fake_papers_dir):
    matches = suggest_venues(["does-not-exist"], today=date(2026, 5, 15))
    assert matches == []


def test_user_curated_venue_is_boosted(fake_papers_dir):
    # User has curated SOSP _venue.md but not OSDI.
    sosp_dir = fake_papers_dir / "SOSP-2027"
    sosp_dir.mkdir()
    (sosp_dir / "_venue.md").write_text("# SOSP\n", encoding="utf-8")

    matches = suggest_venues(["sys"], today=date(2026, 5, 15), top_k=10)
    by_slug = {m.venue.slug: m for m in matches}
    assert by_slug["sosp"].is_user_curated
    assert by_slug["sosp"].fit_score > by_slug["osdi"].fit_score
    # Top of the list should be the curated one
    assert matches[0].venue.slug == "sosp"


def test_user_curated_multi_token_venue_matches_with_year_suffix(fake_papers_dir):
    """Curated dir like ``USENIX-SEC-2027`` must match registry slug
    ``usenix-sec``. The old alpha-only fallback produced ``usenixsec`` and
    silently failed."""
    venue_dir = fake_papers_dir / "USENIX-SEC-2027"
    venue_dir.mkdir()
    (venue_dir / "_venue.md").write_text("# USENIX Security\n", encoding="utf-8")

    matches = suggest_venues(["sec"], today=date(2026, 5, 15), top_k=10)
    by_slug = {m.venue.slug: m for m in matches}
    assert by_slug["usenix-sec"].is_user_curated


def test_next_deadline_picks_future_year(fake_papers_dir):
    # ICML deadline_month=1; today in May → next deadline should be Jan next year.
    matches = suggest_venues(["ml"], today=date(2026, 5, 15), top_k=10)
    by_slug = {m.venue.slug: m for m in matches}
    assert by_slug["icml"].next_deadline == date(2027, 1, 1)
    # NeurIPS deadline_month=5; we're on the 15th, month is current → also future
    # (we treat "today.month" as already-past for safety: next year).
    assert by_slug["neurips"].next_deadline >= date(2026, 5, 1)


def test_render_includes_deadlines_and_curated_star(fake_papers_dir):
    sosp_dir = fake_papers_dir / "SOSP-2027"
    sosp_dir.mkdir()
    (sosp_dir / "_venue.md").write_text("# SOSP\n", encoding="utf-8")

    matches = suggest_venues(["sys"], today=date(2026, 5, 15), top_k=3)
    md = render_venues_md(matches, ["sys"])
    assert "SOSP" in md
    assert "⭐" in md  # curated marker
    assert "Next deadline" in md


def test_render_empty_matches():
    md = render_venues_md([], ["zzz"])
    assert "No registry venues match" in md


def test_registry_has_no_duplicate_slugs():
    slugs = [v.slug for v in VENUE_REGISTRY]
    assert len(slugs) == len(set(slugs))


def test_registry_deadline_months_in_range():
    for v in VENUE_REGISTRY:
        assert 1 <= v.deadline_month <= 12
