"""Tests for ``/paper archive`` / ``/paper unarchive`` / ``/paper archive list``."""

from __future__ import annotations

import os
from datetime import date
from pathlib import Path

import pytest
import yaml

from research_assistant.common import io as common_io
from research_assistant.mentor import past_work
from research_assistant.papers import archive as archive_mod
from research_assistant.papers import (
    ArchiveError,
    archive_direction,
    list_archived,
    unarchive_direction,
)
from research_assistant.papers import __init__ as papers_init  # noqa: F401  (sanity import)
from research_assistant import papers


# ---------- harness ----------

def _stub_dirs(tmp_path: Path, monkeypatch) -> tuple[Path, Path]:
    """Point both PAST_WORK_DIR and PAPERS_DIR at fresh tmp subdirs."""
    pw_root = tmp_path / "past-work"
    pw_root.mkdir()
    papers_root = tmp_path / "papers"
    papers_root.mkdir()
    monkeypatch.setattr(past_work, "PAST_WORK_DIR", pw_root)
    monkeypatch.setattr(common_io, "PAST_WORK_DIR", pw_root)
    monkeypatch.setattr(archive_mod, "PAST_WORK_DIR", pw_root)
    monkeypatch.setattr(papers, "PAPERS_DIR", papers_root)
    return pw_root, papers_root


def _build_paper(
    papers_root: Path,
    venue: str,
    direction: str,
    *,
    title: str = "Adaptive Weight Sharing",
    abstract: str | None = "An adaptive weight-sharing scheme that ...",
    with_pdf: bool = True,
    with_experiment: str | None = None,
) -> Path:
    direction_dir = papers_root / venue / direction
    direction_dir.mkdir(parents=True)
    (direction_dir / "main.tex").write_text(
        f"\\title{{{title}}}\n"
        + (
            f"\\begin{{abstract}}\n{abstract}\n\\end{{abstract}}\n"
            if abstract is not None else ""
        )
        + "\\input{sections/intro}\n",
        encoding="utf-8",
    )
    (direction_dir / "sections").mkdir()
    (direction_dir / "sections" / "intro.tex").write_text("intro.\n")
    (direction_dir / "refs.bib").write_text("@article{x, title={x}}\n")
    if with_pdf:
        (direction_dir / "main.pdf").write_bytes(b"%PDF-1.7\n%fake\n")
    expert_fm = {"venue": venue, "direction": direction, "title": title}
    if with_experiment:
        expert_fm["experiment"] = with_experiment
    (direction_dir / "expert.md").write_text(
        "---\n" + yaml.safe_dump(expert_fm) + "---\n\nbody\n",
        encoding="utf-8",
    )
    (direction_dir / "status.md").write_text("# status\n[#######] 7/7 stages\n")
    return direction_dir


# ---------- archive_direction ----------

def test_archive_moves_tree_and_creates_entry(tmp_path, monkeypatch):
    pw, papers_root = _stub_dirs(tmp_path, monkeypatch)
    src = _build_paper(papers_root, "OSDI-2027", "weightlet")
    result = archive_direction("OSDI-2027", "weightlet", today=date(2026, 5, 22))
    # Source moved
    assert not src.exists()
    # Dest populated
    assert result.paper_dest.is_dir()
    assert (result.paper_dest / "main.tex").is_file()
    assert (result.paper_dest / "main.pdf").is_file()
    assert (result.paper_dest / "expert.md").is_file()
    # Past-work .md created
    assert result.entry_path.is_file()
    assert result.entry_created is True
    assert result.slug == "osdi-2027-weightlet"
    # Frontmatter has the expected fields
    text = result.entry_path.read_text(encoding="utf-8")
    assert "title: Adaptive Weight Sharing" in text
    assert "venue: OSDI-2027" in text
    assert "status: published" in text
    assert "paper:./paper/main.pdf" in text
    assert "archived-from:outputs/papers/OSDI-2027/weightlet" in text
    # status.md got the archived marker
    status = (result.paper_dest / "status.md").read_text(encoding="utf-8")
    assert "archived: 2026-05-22" in status
    assert "archive-status: published" in status


def test_archive_abandoned_flag(tmp_path, monkeypatch):
    pw, papers_root = _stub_dirs(tmp_path, monkeypatch)
    _build_paper(papers_root, "OSDI-2027", "weightlet")
    result = archive_direction(
        "OSDI-2027", "weightlet", abandoned=True, today=date(2026, 5, 22),
    )
    assert result.status == "abandoned"
    text = result.entry_path.read_text(encoding="utf-8")
    assert "status: abandoned" in text
    status = (result.paper_dest / "status.md").read_text(encoding="utf-8")
    assert "archive-status: abandoned" in status


def test_archive_refuses_symlink(tmp_path, monkeypatch):
    pw, papers_root = _stub_dirs(tmp_path, monkeypatch)
    # Create the venue + a symlinked direction
    (papers_root / "OSDI-2027").mkdir()
    real_target = tmp_path / "bound-paper"
    real_target.mkdir()
    (real_target / "main.tex").write_text("x")
    direction = papers_root / "OSDI-2027" / "weightlet"
    os.symlink(real_target, direction, target_is_directory=True)
    with pytest.raises(ArchiveError, match="symlink"):
        archive_direction("OSDI-2027", "weightlet")


def test_archive_refuses_missing_direction(tmp_path, monkeypatch):
    pw, papers_root = _stub_dirs(tmp_path, monkeypatch)
    with pytest.raises(ArchiveError, match="no such direction"):
        archive_direction("OSDI-2027", "missing")


def test_archive_collision_suffix(tmp_path, monkeypatch):
    """Second archive of the same (venue, direction) gets `-2` suffix."""
    pw, papers_root = _stub_dirs(tmp_path, monkeypatch)
    _build_paper(papers_root, "OSDI-2027", "weightlet")
    r1 = archive_direction("OSDI-2027", "weightlet", today=date(2026, 5, 22))
    assert r1.slug == "osdi-2027-weightlet"
    # Rebuild a fresh paper at the same path, archive again
    _build_paper(papers_root, "OSDI-2027", "weightlet", title="Weightlet v2")
    r2 = archive_direction("OSDI-2027", "weightlet", today=date(2026, 5, 22))
    assert r2.slug == "osdi-2027-weightlet-2"
    assert r2.paper_dest.is_dir()


def test_archive_preserves_user_stub(tmp_path, monkeypatch):
    """If the user pre-created the .md with prose, archive merges (preserves body)."""
    pw, papers_root = _stub_dirs(tmp_path, monkeypatch)
    _build_paper(papers_root, "OSDI-2027", "weightlet")
    # User pre-creates the .md as a stub
    stub = pw / "osdi-2027-weightlet.md"
    stub.write_text(
        "---\nslug: osdi-2027-weightlet\ntitle: \"\"\ntags: [systems]\n"
        "links:\n  - \"arxiv:2401.99999\"\n---\n\n"
        "# Pre-existing prose\n\nThe user already wrote this paragraph.\n",
        encoding="utf-8",
    )
    result = archive_direction("OSDI-2027", "weightlet", today=date(2026, 5, 22))
    assert result.slug == "osdi-2027-weightlet"
    assert result.entry_created is False
    text = result.entry_path.read_text(encoding="utf-8")
    # User's prose survives
    assert "Pre-existing prose" in text
    assert "user already wrote this paragraph" in text
    # User-supplied tags preserved (archive doesn't overwrite a non-empty tags list)
    assert "- systems" in text
    # Title now filled from archived paper since stub had empty title
    assert "title: Adaptive Weight Sharing" in text
    # links deduped — both the user's arxiv and archive's pointers present
    assert "arxiv:2401.99999" in text
    assert "paper:./paper/main.pdf" in text


def test_archive_captures_experiment_binding_link(tmp_path, monkeypatch):
    pw, papers_root = _stub_dirs(tmp_path, monkeypatch)
    _build_paper(papers_root, "OSDI-2027", "weightlet", with_experiment="weightlet-exp")
    result = archive_direction("OSDI-2027", "weightlet")
    text = result.entry_path.read_text(encoding="utf-8")
    assert "experiment:weightlet-exp" in text


def test_archive_falls_back_to_venue_direction_title(tmp_path, monkeypatch):
    """Paper with neither title source still archives cleanly."""
    pw, papers_root = _stub_dirs(tmp_path, monkeypatch)
    d = papers_root / "OSDI-2027" / "weightlet"
    d.mkdir(parents=True)
    (d / "status.md").write_text("# x\n")
    result = archive_direction("OSDI-2027", "weightlet")
    text = result.entry_path.read_text(encoding="utf-8")
    assert "title: OSDI-2027 / weightlet" in text


# ---------- unarchive_direction ----------

def test_unarchive_round_trip(tmp_path, monkeypatch):
    pw, papers_root = _stub_dirs(tmp_path, monkeypatch)
    src = _build_paper(papers_root, "OSDI-2027", "weightlet")
    src_text = (src / "main.tex").read_text()
    r = archive_direction("OSDI-2027", "weightlet")
    venue, direction = unarchive_direction(r.slug)
    assert venue == "OSDI-2027"
    assert direction == "weightlet"
    restored = papers_root / "OSDI-2027" / "weightlet"
    assert restored.is_dir()
    assert (restored / "main.tex").read_text() == src_text
    # paper/ subdir gone; past-work .md preserved
    assert not r.paper_dest.exists()
    assert r.entry_path.is_file()


def test_unarchive_refuses_if_destination_exists(tmp_path, monkeypatch):
    pw, papers_root = _stub_dirs(tmp_path, monkeypatch)
    _build_paper(papers_root, "OSDI-2027", "weightlet")
    r = archive_direction("OSDI-2027", "weightlet")
    # User restarted work — same path exists again
    _build_paper(papers_root, "OSDI-2027", "weightlet")
    with pytest.raises(ArchiveError, match="already exists"):
        unarchive_direction(r.slug)


def test_unarchive_uses_link_fallback_when_expert_missing(tmp_path, monkeypatch):
    """If expert.md is gone (user deleted it), unarchive uses the archived-from link."""
    pw, papers_root = _stub_dirs(tmp_path, monkeypatch)
    _build_paper(papers_root, "OSDI-2027", "weightlet")
    r = archive_direction("OSDI-2027", "weightlet")
    (r.paper_dest / "expert.md").unlink()
    venue, direction = unarchive_direction(r.slug)
    assert venue == "OSDI-2027"
    assert direction == "weightlet"


def test_unarchive_refuses_unknown_slug(tmp_path, monkeypatch):
    _stub_dirs(tmp_path, monkeypatch)
    with pytest.raises(ArchiveError, match="no archived paper"):
        unarchive_direction("not-a-slug")


# ---------- list_archived ----------

def test_list_archived_filters_to_paper_subdirs(tmp_path, monkeypatch):
    pw, papers_root = _stub_dirs(tmp_path, monkeypatch)
    _build_paper(papers_root, "OSDI-2027", "weightlet")
    _build_paper(papers_root, "EuroSys-2027", "vsched")
    archive_direction("OSDI-2027", "weightlet", today=date(2026, 5, 22))
    archive_direction("EuroSys-2027", "vsched", today=date(2026, 5, 22))
    # An external-project past-work entry (no paper/ subdir) — must be excluded
    (pw / "tide.md").write_text(
        "---\nslug: tide\ntitle: Tide\n---\n\n# Tide\n", encoding="utf-8",
    )
    rows = list_archived()
    slugs = {a.slug for a in rows}
    assert slugs == {"osdi-2027-weightlet", "eurosys-2027-vsched"}
    by_slug = {a.slug: a for a in rows}
    assert by_slug["osdi-2027-weightlet"].venue == "OSDI-2027"
    assert by_slug["osdi-2027-weightlet"].title == "Adaptive Weight Sharing"
    assert by_slug["osdi-2027-weightlet"].archived_on == "2026-05-22"
    assert by_slug["osdi-2027-weightlet"].has_pdf is True


def test_list_archived_empty_when_no_archives(tmp_path, monkeypatch):
    _stub_dirs(tmp_path, monkeypatch)
    assert list_archived() == []
