"""Sync tests for papers.binding.sync — verb inference + divergence handling.

We use a real local-only git repo (no remote) for the happy paths and
monkeypatch `_run_git` for the divergence scenarios.
"""
import subprocess
from pathlib import Path

import pytest

from research_assistant import common
from research_assistant import experiments as exp_pkg
from research_assistant.papers import binding


@pytest.fixture
def fake_dirs(tmp_path, monkeypatch):
    fake_papers = tmp_path / "papers"
    fake_experiments = tmp_path / "experiments"
    fake_papers.mkdir()
    fake_experiments.mkdir()
    monkeypatch.setattr(common.io, "PAPERS_DIR", fake_papers)
    monkeypatch.setattr(common.io, "EXPERIMENTS_DIR", fake_experiments)
    import research_assistant.papers as papers_pkg
    monkeypatch.setattr(papers_pkg, "PAPERS_DIR", fake_papers)
    monkeypatch.setattr(exp_pkg, "EXPERIMENTS_DIR", fake_experiments)
    monkeypatch.setattr(binding, "EXPERIMENTS_DIR", fake_experiments)
    return fake_papers, fake_experiments


def _init_git_repo(repo: Path) -> None:
    """Initialize a git repo with a baseline commit (identity inherited)."""
    subprocess.run(["git", "init", "-q", "-b", "main", str(repo)], check=True)
    # Use local-only identity if global is unset, so tests work in CI.
    subprocess.run(["git", "-C", str(repo), "config", "user.email", "t@example.com"], check=True)
    subprocess.run(["git", "-C", str(repo), "config", "user.name", "Tester"], check=True)
    (repo / "README.md").write_text("seed\n", encoding="utf-8")
    subprocess.run(["git", "-C", str(repo), "add", "."], check=True)
    subprocess.run(
        ["git", "-C", str(repo), "commit", "-q", "-m", "seed"], check=True,
    )


def _setup_bound_paper(fake_experiments: Path, fake_papers: Path, slug: str) -> Path:
    """Create a real git repo + bind a paper into it. Returns the paper_dir."""
    repo = fake_experiments / slug / "repo"
    repo.mkdir(parents=True)
    _init_git_repo(repo)
    # Build a local paper to migrate.
    local = fake_papers / "OSDI-2027" / "weightlet"
    local.mkdir(parents=True)
    (local / "main.tex").write_text(r"\documentclass{article}", encoding="utf-8")
    (local / "sections").mkdir()
    (local / "sections" / "intro.tex").write_text(r"\section{Intro}\nhi", encoding="utf-8")
    result = binding.bind(
        venue="OSDI-2027", direction="weightlet", experiment_slug=slug,
    )
    # Commit the initial migration so subsequent edits are a real diff.
    subprocess.run(["git", "-C", str(repo), "add", "."], check=True)
    subprocess.run(
        ["git", "-C", str(repo), "commit", "-q", "-m", "initial bind"], check=True,
    )
    return result.paper_dir


# ---------- verb inference ----------

def test_infer_verb_write_only():
    rows = [(10, 0, "paper/v/d/sections/method.tex")]
    assert binding._infer_verb(rows) == binding._VERB_WRITE


def test_infer_verb_prune_only():
    rows = [(0, 5, "paper/v/d/sections/old.tex")]
    assert binding._infer_verb(rows) == binding._VERB_PRUNE


def test_infer_verb_revise_mixed():
    rows = [(3, 2, "paper/v/d/main.tex")]
    assert binding._infer_verb(rows) == binding._VERB_REVISE


def test_infer_verb_render_only_main_pdf():
    rows = [(None, None, "paper/OSDI-2027/weightlet/main.pdf")]
    assert binding._infer_verb(rows) == binding._VERB_RENDER


def test_infer_verb_render_with_only_pdfs():
    rows = [
        (None, None, "paper/A/B/main.pdf"),
    ]
    assert binding._infer_verb(rows) == binding._VERB_RENDER


def test_auto_commit_message_includes_verb_and_files():
    rows = [
        (12, 0, "paper/OSDI-2027/weightlet/sections/method.tex"),
        (3, 0, "paper/OSDI-2027/weightlet/refs.bib"),
    ]
    msg = binding._auto_commit_message("OSDI-2027", "weightlet", rows)
    assert msg.startswith("paper(OSDI-2027/weightlet): write ")
    assert "sections/method.tex" in msg
    assert "refs.bib" in msg


def test_auto_commit_message_truncates_long_file_lists():
    rows = [(1, 0, f"paper/A/B/f{i}.tex") for i in range(5)]
    msg = binding._auto_commit_message("A", "B", rows)
    assert "+2 more" in msg


# ---------- sync end-to-end (no remote — push will fail; covers stage+commit) ----------

def test_sync_no_changes_returns_no_op(fake_dirs):
    fake_papers, fake_experiments = fake_dirs
    _setup_bound_paper(fake_experiments, fake_papers, "weightlet-exp")
    result = binding.sync(venue="OSDI-2027", direction="weightlet")
    assert result.committed is False
    assert "no changes" in result.commit_message.lower()


def test_sync_commits_paper_changes(fake_dirs):
    fake_papers, fake_experiments = fake_dirs
    _setup_bound_paper(fake_experiments, fake_papers, "weightlet-exp")
    # Edit a section file through the symlink path (real edit lands in repo).
    section = fake_papers / "OSDI-2027" / "weightlet" / "sections" / "intro.tex"
    section.write_text(r"\section{Intro}\nNew sentence appended.\n", encoding="utf-8")
    result = binding.sync(venue="OSDI-2027", direction="weightlet")
    assert result.committed is True
    assert result.commit_sha is not None
    assert result.diverged is False
    # Commit message follows the convention
    assert result.commit_message.startswith("paper(OSDI-2027/weightlet): ")
    # The verb should be revise (replaced content has both adds and dels)
    # or write (depending on git diff vs HEAD).  We just assert one of the expected.
    assert any(v in result.commit_message for v in ("write", "revise"))
    # Push will fail (no remote) — `pushed=False` is fine.
    assert result.pushed is False


def test_sync_message_override(fake_dirs):
    fake_papers, fake_experiments = fake_dirs
    _setup_bound_paper(fake_experiments, fake_papers, "weightlet-exp")
    (fake_papers / "OSDI-2027" / "weightlet" / "main.tex").write_text(
        r"\documentclass{article}% edit", encoding="utf-8",
    )
    result = binding.sync(
        venue="OSDI-2027", direction="weightlet", message="custom: my message",
    )
    assert result.commit_message == "custom: my message"


def test_sync_raises_not_bound(fake_dirs):
    fake_papers, _ = fake_dirs
    (fake_papers / "OSDI-2027" / "ghost").mkdir(parents=True)
    (fake_papers / "OSDI-2027" / "ghost" / "main.tex").write_text("", encoding="utf-8")
    with pytest.raises(binding.NotBoundError):
        binding.sync(venue="OSDI-2027", direction="ghost")


def test_sync_diverged_raises(fake_dirs, monkeypatch):
    """Mock `_ahead_behind` to simulate the remote being ahead."""
    fake_papers, fake_experiments = fake_dirs
    _setup_bound_paper(fake_experiments, fake_papers, "weightlet-exp")
    # Make a local change so there's something to commit
    (fake_papers / "OSDI-2027" / "weightlet" / "main.tex").write_text("edited\n", encoding="utf-8")
    monkeypatch.setattr(binding, "_ahead_behind", lambda *a, **kw: (0, 2))
    with pytest.raises(binding.DivergedError):
        binding.sync(venue="OSDI-2027", direction="weightlet")
