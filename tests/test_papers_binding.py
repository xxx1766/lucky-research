"""Bind / unbind / restore / is_bound tests for papers.binding.

We monkeypatch `PAPERS_DIR` and `EXPERIMENTS_DIR` (in `common.io` AND in every
module that captured them at import time) to redirect everything into a
pytest `tmp_path` so we can build a realistic experiment-repo layout without
touching the real filesystem.
"""
from pathlib import Path

import pytest

from research_assistant import common
from research_assistant.papers import binding
from research_assistant import experiments as exp_pkg


@pytest.fixture
def fake_dirs(tmp_path, monkeypatch):
    """Redirect PAPERS_DIR + EXPERIMENTS_DIR into tmp_path everywhere."""
    fake_papers = tmp_path / "papers"
    fake_experiments = tmp_path / "experiments"
    fake_papers.mkdir()
    fake_experiments.mkdir()
    monkeypatch.setattr(common.io, "PAPERS_DIR", fake_papers)
    monkeypatch.setattr(common.io, "EXPERIMENTS_DIR", fake_experiments)
    # Modules that captured these at import time:
    import research_assistant.papers as papers_pkg
    monkeypatch.setattr(papers_pkg, "PAPERS_DIR", fake_papers)
    monkeypatch.setattr(exp_pkg, "EXPERIMENTS_DIR", fake_experiments)
    monkeypatch.setattr(binding, "EXPERIMENTS_DIR", fake_experiments)
    return fake_papers, fake_experiments


def _make_experiment(experiments_dir: Path, slug: str) -> Path:
    """Build a minimal experiment-repo clone at `<experiments_dir>/<slug>/repo/`."""
    repo = experiments_dir / slug / "repo"
    repo.mkdir(parents=True)
    (repo / "src").mkdir()
    (repo / "src" / "main.py").write_text("# experiment code\n", encoding="utf-8")
    return repo


def _make_local_paper(papers_dir: Path, venue: str, direction: str) -> Path:
    """Build a non-empty local-authored paper directory."""
    d = papers_dir / venue / direction
    d.mkdir(parents=True)
    (d / "main.tex").write_text(r"\documentclass{article}", encoding="utf-8")
    (d / "sections").mkdir()
    (d / "sections" / "intro.tex").write_text(r"\section{Intro}", encoding="utf-8")
    (d / "refs.bib").write_text("", encoding="utf-8")
    (d / "expert.md").write_text(
        "---\nname: weightlet expert\n---\n\nA scoped expert role.\n",
        encoding="utf-8",
    )
    return d


# ---------- bind ----------

def test_bind_happy_path(fake_dirs):
    fake_papers, fake_experiments = fake_dirs
    _make_experiment(fake_experiments, "weightlet-exp")
    src = _make_local_paper(fake_papers, "OSDI-2027", "weightlet")
    # Also build a venue-level _venue.md inside the experiment repo so the copy step has something to do.
    (fake_experiments / "weightlet-exp" / "repo" / "paper" / "OSDI-2027").mkdir(parents=True)
    (fake_experiments / "weightlet-exp" / "repo" / "paper" / "OSDI-2027" / "_venue.md").write_text(
        "---\nname: OSDI 2027\npseudocode-package: algpseudocode\n---\nVenue notes.\n",
        encoding="utf-8",
    )

    result = binding.bind(
        venue="OSDI-2027", direction="weightlet", experiment_slug="weightlet-exp"
    )

    assert result.experiment_slug == "weightlet-exp"
    # Original src is now a symlink
    assert src.is_symlink()
    assert src.resolve() == result.paper_dir.resolve()
    # Real files live in the experiment repo
    assert (result.paper_dir / "main.tex").is_file()
    assert (result.paper_dir / "sections" / "intro.tex").is_file()
    # expert.md gained `experiment: weightlet-exp`
    expert_text = (result.paper_dir / "expert.md").read_text()
    assert "experiment: weightlet-exp" in expert_text
    # .gitignore written
    gi = (result.paper_dir / ".gitignore").read_text()
    assert "algorithms/*.pdf" in gi
    assert "status.md" in gi
    # Venue-level _venue.md was copied (NOT symlinked) to outputs/papers/<venue>/
    local_venue_md = fake_papers / "OSDI-2027" / "_venue.md"
    assert local_venue_md.is_file()
    assert not local_venue_md.is_symlink()
    assert "OSDI 2027" in local_venue_md.read_text()
    assert "_venue.md" in result.venue_files_copied


def test_bind_idempotent_same_experiment(fake_dirs):
    fake_papers, fake_experiments = fake_dirs
    _make_experiment(fake_experiments, "weightlet-exp")
    _make_local_paper(fake_papers, "OSDI-2027", "weightlet")
    first = binding.bind(
        venue="OSDI-2027", direction="weightlet", experiment_slug="weightlet-exp"
    )
    # Second call: same (v, d, slug) → no-op, no exception.
    second = binding.bind(
        venue="OSDI-2027", direction="weightlet", experiment_slug="weightlet-exp"
    )
    assert second.paper_dir == first.paper_dir
    assert second.symlink_path.is_symlink()


def test_bind_raises_already_bound_when_target_differs(fake_dirs):
    fake_papers, fake_experiments = fake_dirs
    _make_experiment(fake_experiments, "exp-a")
    _make_experiment(fake_experiments, "exp-b")
    _make_local_paper(fake_papers, "OSDI-2027", "weightlet")
    binding.bind(venue="OSDI-2027", direction="weightlet", experiment_slug="exp-a")
    with pytest.raises(binding.AlreadyBoundError):
        binding.bind(
            venue="OSDI-2027", direction="weightlet", experiment_slug="exp-b"
        )


def test_bind_force_overrides_already_bound(fake_dirs):
    fake_papers, fake_experiments = fake_dirs
    _make_experiment(fake_experiments, "exp-a")
    _make_experiment(fake_experiments, "exp-b")
    _make_local_paper(fake_papers, "OSDI-2027", "weightlet")
    binding.bind(venue="OSDI-2027", direction="weightlet", experiment_slug="exp-a")
    result = binding.bind(
        venue="OSDI-2027", direction="weightlet", experiment_slug="exp-b", force=True
    )
    assert result.experiment_slug == "exp-b"
    assert "exp-b" in str(result.paper_dir)


def test_bind_raises_conflict_when_dest_populated(fake_dirs):
    fake_papers, fake_experiments = fake_dirs
    repo = _make_experiment(fake_experiments, "exp-a")
    # Pre-populate <exp-repo>/paper/<v>/<d>/ with foreign content:
    pre = repo / "paper" / "OSDI-2027" / "weightlet"
    pre.mkdir(parents=True)
    (pre / "old.tex").write_text("foreign content", encoding="utf-8")
    _make_local_paper(fake_papers, "OSDI-2027", "weightlet")
    with pytest.raises(binding.ConflictError):
        binding.bind(
            venue="OSDI-2027", direction="weightlet", experiment_slug="exp-a"
        )


def test_bind_requires_cloned_experiment(fake_dirs):
    fake_papers, fake_experiments = fake_dirs
    # NOTE: do NOT create the experiment dir — clone is missing.
    _make_local_paper(fake_papers, "OSDI-2027", "weightlet")
    with pytest.raises(binding.BindError):
        binding.bind(
            venue="OSDI-2027", direction="weightlet", experiment_slug="absent-exp"
        )


def test_bind_creates_empty_dir_when_no_local_content(fake_dirs):
    """Edge case: /paper bind called before any local authoring exists."""
    fake_papers, fake_experiments = fake_dirs
    _make_experiment(fake_experiments, "exp-a")
    result = binding.bind(
        venue="OSDI-2027", direction="fresh", experiment_slug="exp-a"
    )
    assert result.paper_dir.is_dir()
    assert result.symlink_path.is_symlink()


# ---------- unbind ----------

def test_unbind_removes_symlink(fake_dirs):
    fake_papers, fake_experiments = fake_dirs
    _make_experiment(fake_experiments, "exp-a")
    _make_local_paper(fake_papers, "OSDI-2027", "weightlet")
    binding.bind(venue="OSDI-2027", direction="weightlet", experiment_slug="exp-a")
    link = fake_papers / "OSDI-2027" / "weightlet"
    assert link.is_symlink()
    binding.unbind(venue="OSDI-2027", direction="weightlet")
    assert not link.exists()


def test_unbind_keep_files_restores_real_directory(fake_dirs):
    fake_papers, fake_experiments = fake_dirs
    _make_experiment(fake_experiments, "exp-a")
    _make_local_paper(fake_papers, "OSDI-2027", "weightlet")
    binding.bind(venue="OSDI-2027", direction="weightlet", experiment_slug="exp-a")
    binding.unbind(venue="OSDI-2027", direction="weightlet", keep_files=True)
    real = fake_papers / "OSDI-2027" / "weightlet"
    assert real.is_dir()
    assert not real.is_symlink()
    assert (real / "main.tex").is_file()
    assert (real / "sections" / "intro.tex").is_file()


def test_unbind_raises_on_real_dir(fake_dirs):
    fake_papers, _ = fake_dirs
    _make_local_paper(fake_papers, "OSDI-2027", "weightlet")
    with pytest.raises(binding.NotBoundError):
        binding.unbind(venue="OSDI-2027", direction="weightlet")


# ---------- is_bound ----------

def test_is_bound_returns_slug_for_symlink(fake_dirs):
    fake_papers, fake_experiments = fake_dirs
    _make_experiment(fake_experiments, "weightlet-exp")
    _make_local_paper(fake_papers, "OSDI-2027", "weightlet")
    binding.bind(
        venue="OSDI-2027", direction="weightlet", experiment_slug="weightlet-exp"
    )
    assert binding.is_bound("OSDI-2027", "weightlet") == "weightlet-exp"


def test_is_bound_returns_none_for_real_dir(fake_dirs):
    fake_papers, _ = fake_dirs
    _make_local_paper(fake_papers, "OSDI-2027", "weightlet")
    assert binding.is_bound("OSDI-2027", "weightlet") is None


def test_is_bound_returns_none_for_missing(fake_dirs):
    assert binding.is_bound("OSDI-2027", "ghost") is None


def test_read_binding_from_expert_md(fake_dirs):
    fake_papers, fake_experiments = fake_dirs
    _make_experiment(fake_experiments, "weightlet-exp")
    _make_local_paper(fake_papers, "OSDI-2027", "weightlet")
    binding.bind(
        venue="OSDI-2027", direction="weightlet", experiment_slug="weightlet-exp"
    )
    assert binding.read_binding_from_expert_md("OSDI-2027", "weightlet") == "weightlet-exp"


def test_read_binding_from_expert_md_absent(fake_dirs):
    assert binding.read_binding_from_expert_md("OSDI-2027", "ghost") is None


# ---------- restore ----------

def test_restore_all_recreates_symlinks(fake_dirs):
    fake_papers, fake_experiments = fake_dirs
    # Build experiment repos with paper subtrees but NO local symlinks.
    for slug, venue, direction in (
        ("exp-a", "OSDI-2027", "weightlet"),
        ("exp-b", "ASPLOS-2028", "sparse-attn"),
    ):
        repo = _make_experiment(fake_experiments, slug)
        d = repo / "paper" / venue / direction
        d.mkdir(parents=True)
        (d / "main.tex").write_text("hi", encoding="utf-8")
    results = binding.restore(all_papers=True)
    assert len(results) == 2
    assert (fake_papers / "OSDI-2027" / "weightlet").is_symlink()
    assert (fake_papers / "ASPLOS-2028" / "sparse-attn").is_symlink()


def test_restore_specific_venue_direction(fake_dirs):
    fake_papers, fake_experiments = fake_dirs
    repo = _make_experiment(fake_experiments, "exp-a")
    (repo / "paper" / "OSDI-2027" / "weightlet").mkdir(parents=True)
    (repo / "paper" / "OSDI-2027" / "weightlet" / "main.tex").write_text("", encoding="utf-8")
    # also another paper that should NOT be restored
    (repo / "paper" / "ASPLOS-2028" / "other").mkdir(parents=True)
    results = binding.restore(venue="OSDI-2027", direction="weightlet")
    assert len(results) == 1
    assert results[0].venue == "OSDI-2027"
    assert results[0].direction == "weightlet"
    assert not (fake_papers / "ASPLOS-2028" / "other").exists()


def test_restore_skips_real_local_dirs(fake_dirs):
    """User has a real local directory at outputs/papers/<v>/<d>/ — don't clobber."""
    fake_papers, fake_experiments = fake_dirs
    repo = _make_experiment(fake_experiments, "exp-a")
    (repo / "paper" / "OSDI-2027" / "weightlet").mkdir(parents=True)
    _make_local_paper(fake_papers, "OSDI-2027", "weightlet")
    results = binding.restore(all_papers=True)
    # No symlink created; the real dir survives.
    assert results == []
    assert (fake_papers / "OSDI-2027" / "weightlet").is_dir()
    assert not (fake_papers / "OSDI-2027" / "weightlet").is_symlink()


def test_restore_idempotent_existing_symlink(fake_dirs):
    fake_papers, fake_experiments = fake_dirs
    _make_experiment(fake_experiments, "weightlet-exp")
    _make_local_paper(fake_papers, "OSDI-2027", "weightlet")
    binding.bind(
        venue="OSDI-2027", direction="weightlet", experiment_slug="weightlet-exp"
    )
    # Restore should detect the existing-correct symlink and report it.
    results = binding.restore(all_papers=True)
    assert len(results) == 1
    assert results[0].experiment_slug == "weightlet-exp"


def test_restore_requires_target_or_all(fake_dirs):
    with pytest.raises(ValueError):
        binding.restore()
