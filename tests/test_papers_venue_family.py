"""Tests for `family_for_venue` in papers.venue_family.

Covers the built-in prefix map (case + slug-variant tolerance), the
explicit `Family:` override in `_venue.md`, and graceful fallback for
unknown venues.
"""
from __future__ import annotations

import pytest

from research_assistant import common
from research_assistant.papers import family_for_venue


@pytest.fixture
def fake_papers_dir(tmp_path, monkeypatch):
    fake = tmp_path / "papers"
    fake.mkdir()
    monkeypatch.setattr(common.io, "PAPERS_DIR", fake)
    import research_assistant.papers as papers_pkg
    monkeypatch.setattr(papers_pkg, "PAPERS_DIR", fake)
    return fake


# ---------- built-in prefix map ----------


@pytest.mark.parametrize("slug,expected", [
    ("OSDI-2027", "systems"),
    ("SOSP-2026", "systems"),
    ("NSDI-2027", "systems"),
    ("EuroSys-2027", "systems"),
    ("ATC-2026", "systems"),
    ("ASPLOS-2026", "systems"),
    ("MLSys-2027", "systems"),
    ("ACL-2026", "nlp"),
    ("EMNLP-2025", "nlp"),
    ("NAACL-2026", "nlp"),
    ("CVPR-2026", "cv"),
    ("ICCV-2025", "cv"),
    ("ECCV-2026", "cv"),
    ("ICML-2026", "ml"),
    ("NeurIPS-2026", "ml"),
    ("ICLR-2027", "ml"),
    ("VLDB-2026", "db"),
    ("SIGMOD-2026", "db"),
    ("SIGIR-2026", "ir"),
    ("WWW-2027", "ir"),
])
def test_known_venue_resolves_to_family(slug, expected):
    assert family_for_venue(slug) == expected


def test_case_insensitive_match():
    assert family_for_venue("osdi-2027") == "systems"
    assert family_for_venue("Cvpr-2026") == "cv"
    assert family_for_venue("emnlp") == "nlp"


def test_slug_without_year_still_matches():
    assert family_for_venue("OSDI") == "systems"
    assert family_for_venue("CVPR") == "cv"


def test_underscore_separator_also_works():
    assert family_for_venue("OSDI_2027") == "systems"


def test_unknown_venue_falls_back_to_default():
    assert family_for_venue("MyNicheConf-2027") == "default"


def test_empty_input_returns_default():
    assert family_for_venue("") == "default"


# ---------- _venue.md override ----------


def _write_venue_md(papers_root, slug: str, body: str) -> None:
    d = papers_root / slug
    d.mkdir(parents=True, exist_ok=True)
    (d / "_venue.md").write_text(body, encoding="utf-8")


def test_explicit_family_override_wins(fake_papers_dir):
    # A user pins a niche venue to "systems" even though the prefix map
    # doesn't know it.
    _write_venue_md(fake_papers_dir, "HotPlatform-2027",
                    "# HotPlatform '27\n\nFamily: systems\n\nbody\n")
    assert family_for_venue("HotPlatform-2027") == "systems"


def test_explicit_override_can_change_known_venue_family(fake_papers_dir):
    # OSDI is "systems" by default. A user could pin their OSDI submission
    # to "ml" if their paper is theoretical — override wins over the map.
    _write_venue_md(fake_papers_dir, "OSDI-2027",
                    "# OSDI '27\n\nFamily: ml\n")
    assert family_for_venue("OSDI-2027") == "ml"


def test_override_tolerates_bullet_and_emphasis(fake_papers_dir):
    _write_venue_md(fake_papers_dir, "X-2027",
                    "- **Family**: cv\n")
    assert family_for_venue("X-2027") == "cv"


def test_override_case_insensitive(fake_papers_dir):
    _write_venue_md(fake_papers_dir, "X-2027",
                    "family: NLP\n")
    assert family_for_venue("X-2027") == "nlp"


def test_invalid_override_value_falls_through_to_prefix_map(fake_papers_dir):
    # "Family: rubbish" should NOT be honored; OSDI-2027 still resolves to systems.
    _write_venue_md(fake_papers_dir, "OSDI-2027",
                    "# OSDI\n\nFamily: rubbish\n")
    assert family_for_venue("OSDI-2027") == "systems"


def test_override_only_reads_first_50_lines(fake_papers_dir):
    # A Family: line on line 100 should NOT be honored — too easy to false-match
    # against body prose. Stick to the conventional placement near the top.
    body = "\n".join(["# OSDI"] + ["filler"] * 80 + ["Family: ml"])
    _write_venue_md(fake_papers_dir, "OSDI-2027", body)
    assert family_for_venue("OSDI-2027") == "systems"


def test_missing_venue_md_falls_back_to_prefix_map(fake_papers_dir):
    # No _venue.md at all → prefix map only.
    assert family_for_venue("CVPR-2027") == "cv"
