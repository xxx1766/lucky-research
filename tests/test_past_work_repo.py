"""Tests for the `/past-work` GitHub repo binding.

Same pattern as `test_experiments.py`: pure unit tests, no real git/network —
``subprocess.run`` is monkeypatched where the code under test would touch it.
"""

from __future__ import annotations

import subprocess
from pathlib import Path

import pytest

from research_assistant.common import git as common_git
from research_assistant.common import io as common_io
from research_assistant.mentor import past_work
from research_assistant.mentor.past_work import (
    PastWorkRepo,
    RepoBindError,
    bind_repo,
    clone_repo,
    companion_dir,
    entry_path,
    list_entries_with_repo,
    next_available_slug,
    paper_dir,
    pull_repo,
    read_repo_block,
    repo_dir,
    sync_repo,
    unbind_repo,
)


# ---------- helpers ----------

class _FakeCompleted:
    def __init__(self, stdout: str = "", stderr: str = "", returncode: int = 0):
        self.stdout = stdout
        self.stderr = stderr
        self.returncode = returncode


def _stub_past_work_dir(tmp_path: Path, monkeypatch) -> Path:
    """Point both past_work and common.io at a fresh tmp dir."""
    root = tmp_path / "past-work"
    root.mkdir()
    monkeypatch.setattr(past_work, "PAST_WORK_DIR", root)
    monkeypatch.setattr(common_io, "PAST_WORK_DIR", root)
    return root


def _write_entry(slug: str, root: Path, *, title: str = "Test", year: int = 2025) -> Path:
    p = root / f"{slug}.md"
    p.write_text(
        f"---\nslug: {slug}\ntitle: \"{title}\"\nyear: {year}\n---\n\n# {title}\n",
        encoding="utf-8",
    )
    return p


# ---------- path helpers ----------

def test_entry_path_under_past_work_dir(tmp_path, monkeypatch):
    root = _stub_past_work_dir(tmp_path, monkeypatch)
    p = entry_path("tide")
    assert p.parent == root
    assert p.name == "tide.md"


def test_entry_path_rejects_traversal(tmp_path, monkeypatch):
    _stub_past_work_dir(tmp_path, monkeypatch)
    with pytest.raises(ValueError):
        entry_path("")
    with pytest.raises(ValueError):
        entry_path("../escape")


def test_companion_dir_traversal_guard(tmp_path, monkeypatch):
    root = _stub_past_work_dir(tmp_path, monkeypatch)
    assert companion_dir("tide").parent == root
    assert repo_dir("tide").name == "repo"
    assert paper_dir("tide").name == "paper"
    with pytest.raises(ValueError):
        companion_dir("../escape")


def test_next_available_slug_checks_only_companion_dir(tmp_path, monkeypatch):
    """Stub .md should NOT block slug allocation — archive needs to merge into it."""
    root = _stub_past_work_dir(tmp_path, monkeypatch)
    # bare .md present, no companion folder yet — slug is still free
    (root / "weightlet.md").write_text("---\nslug: weightlet\ntitle: x\n---\n")
    assert next_available_slug("weightlet") == "weightlet"
    # companion folder present — slug taken, fall through to -2
    (root / "weightlet").mkdir()
    assert next_available_slug("weightlet") == "weightlet-2"
    (root / "weightlet-2").mkdir()
    assert next_available_slug("weightlet") == "weightlet-3"


def test_next_available_slug_rejects_empty(tmp_path, monkeypatch):
    _stub_past_work_dir(tmp_path, monkeypatch)
    with pytest.raises(ValueError):
        next_available_slug("")


# ---------- PastWorkRepo model ----------

def test_past_work_repo_minimal():
    r = PastWorkRepo(url="git@github.com:user/repo.git")
    assert r.branch == "main"
    assert r.clone_status == "tracked"
    assert r.last_known_sha is None
    assert r.cloned_at is None


def test_past_work_repo_full():
    r = PastWorkRepo(
        url="git@github.com:user/repo.git",
        branch="dev",
        last_known_sha="abc1234",
        clone_status="cloned",
        cloned_at="2026-05-22",
    )
    assert r.branch == "dev"
    assert r.clone_status == "cloned"


# ---------- bind_repo ----------

def test_bind_repo_writes_frontmatter(tmp_path, monkeypatch):
    root = _stub_past_work_dir(tmp_path, monkeypatch)
    _write_entry("tide", root)
    repo = bind_repo("tide", "git@github.com:user/tide.git")
    assert repo.url == "git@github.com:user/tide.git"
    assert repo.branch == "main"
    assert repo.clone_status == "tracked"
    # Re-read from disk
    rt = read_repo_block("tide")
    assert rt is not None and rt.url == repo.url


def test_bind_repo_custom_branch(tmp_path, monkeypatch):
    root = _stub_past_work_dir(tmp_path, monkeypatch)
    _write_entry("tide", root)
    repo = bind_repo("tide", "git@github.com:user/tide.git", branch="dev")
    assert repo.branch == "dev"


def test_bind_repo_refuses_without_entry(tmp_path, monkeypatch):
    _stub_past_work_dir(tmp_path, monkeypatch)
    with pytest.raises(RepoBindError, match="no past-work entry"):
        bind_repo("tide", "git@github.com:user/tide.git")


def test_bind_repo_rejects_empty_url(tmp_path, monkeypatch):
    root = _stub_past_work_dir(tmp_path, monkeypatch)
    _write_entry("tide", root)
    with pytest.raises(ValueError):
        bind_repo("tide", "   ")


def test_bind_repo_preserves_existing_clone_state(tmp_path, monkeypatch):
    """Re-binding with the same URL should not clobber last_known_sha."""
    root = _stub_past_work_dir(tmp_path, monkeypatch)
    _write_entry("tide", root)
    bind_repo("tide", "git@github.com:user/tide.git")
    # Simulate prior clone state
    from research_assistant.mentor.past_work import write_repo_block
    write_repo_block("tide", PastWorkRepo(
        url="git@github.com:user/tide.git",
        last_known_sha="abc1234",
        clone_status="cloned",
        cloned_at="2026-05-01",
    ))
    # Re-bind same URL — sha should survive
    rebound = bind_repo("tide", "git@github.com:user/tide.git")
    assert rebound.last_known_sha == "abc1234"
    assert rebound.cloned_at == "2026-05-01"


def test_bind_repo_resets_sha_on_url_change(tmp_path, monkeypatch):
    """Binding a different URL drops sha (old sha is meaningless for new repo)."""
    root = _stub_past_work_dir(tmp_path, monkeypatch)
    _write_entry("tide", root)
    from research_assistant.mentor.past_work import write_repo_block
    write_repo_block("tide", PastWorkRepo(
        url="git@github.com:old/repo.git",
        last_known_sha="oldsha",
        clone_status="cloned",
    ))
    new = bind_repo("tide", "git@github.com:user/tide.git")
    assert new.last_known_sha is None
    assert new.clone_status == "tracked"


# ---------- clone_repo ----------

def _stub_clone_to_create_dir(monkeypatch):
    """Make git_clone_shallow create the dest dir + a fake .git dir, no network."""
    def fake_clone(dest: Path, url: str, branch: str = "main", *, timeout: int = 120):
        dest.parent.mkdir(parents=True, exist_ok=True)
        dest.mkdir()
        (dest / ".git").mkdir()
        (dest / "README.md").write_text("fake")
        return dest
    monkeypatch.setattr(past_work, "git_clone_shallow", fake_clone)


def test_clone_repo_happy_path(tmp_path, monkeypatch):
    root = _stub_past_work_dir(tmp_path, monkeypatch)
    _write_entry("tide", root)
    bind_repo("tide", "git@github.com:user/tide.git")
    _stub_clone_to_create_dir(monkeypatch)
    monkeypatch.setattr(past_work, "git_rev_parse_head", lambda p: "sha-after-clone")
    dest = clone_repo("tide")
    assert dest.is_dir()
    assert dest.name == "repo"
    assert (dest / "README.md").read_text() == "fake"
    # Frontmatter updated
    r = read_repo_block("tide")
    assert r.clone_status == "cloned"
    assert r.last_known_sha == "sha-after-clone"
    assert r.cloned_at is not None


def test_clone_repo_refuses_without_bind(tmp_path, monkeypatch):
    root = _stub_past_work_dir(tmp_path, monkeypatch)
    _write_entry("tide", root)
    with pytest.raises(RepoBindError, match="no repo bound"):
        clone_repo("tide")


def test_clone_repo_refuses_existing_clone_without_force(tmp_path, monkeypatch):
    root = _stub_past_work_dir(tmp_path, monkeypatch)
    _write_entry("tide", root)
    bind_repo("tide", "git@github.com:user/tide.git")
    # Pre-create the clone dir as if it already existed
    repo_dir("tide").mkdir(parents=True)
    _stub_clone_to_create_dir(monkeypatch)
    monkeypatch.setattr(past_work, "git_rev_parse_head", lambda p: "x")
    with pytest.raises(FileExistsError):
        clone_repo("tide")
    # force=True succeeds (wipes existing, re-clones)
    clone_repo("tide", force=True)
    assert (repo_dir("tide") / "README.md").is_file()


# ---------- sync_repo ----------

def test_sync_repo_refreshes_last_known_sha(tmp_path, monkeypatch):
    root = _stub_past_work_dir(tmp_path, monkeypatch)
    _write_entry("tide", root)
    bind_repo("tide", "git@github.com:user/tide.git")

    def fake_run(cmd, **kwargs):
        return _FakeCompleted(stdout="newsha\trefs/heads/main\n")
    monkeypatch.setattr(subprocess, "run", fake_run)

    result = sync_repo("tide")
    assert result["remote_sha"] == "newsha"
    assert result["error"] is None
    # Frontmatter now reflects the new sha
    assert read_repo_block("tide").last_known_sha == "newsha"


def test_sync_repo_reports_drift(tmp_path, monkeypatch):
    root = _stub_past_work_dir(tmp_path, monkeypatch)
    _write_entry("tide", root)
    bind_repo("tide", "git@github.com:user/tide.git")
    # Seed an existing sha
    from research_assistant.mentor.past_work import write_repo_block
    write_repo_block("tide", PastWorkRepo(
        url="git@github.com:user/tide.git",
        last_known_sha="oldsha",
        clone_status="cloned",
    ))

    def fake_run(cmd, **kwargs):
        return _FakeCompleted(stdout="newsha\trefs/heads/main\n")
    monkeypatch.setattr(subprocess, "run", fake_run)

    result = sync_repo("tide")
    assert result["drift"] is True
    assert result["local_sha"] == "oldsha"


def test_sync_repo_handles_git_failure(tmp_path, monkeypatch):
    root = _stub_past_work_dir(tmp_path, monkeypatch)
    _write_entry("tide", root)
    bind_repo("tide", "git@github.com:user/tide.git")

    def fake_run(cmd, **kwargs):
        return _FakeCompleted(returncode=128, stderr="fatal: repository not found")
    monkeypatch.setattr(subprocess, "run", fake_run)

    result = sync_repo("tide")
    assert result["remote_sha"] is None
    assert "repository not found" in result["error"]


def test_sync_repo_handles_timeout(tmp_path, monkeypatch):
    root = _stub_past_work_dir(tmp_path, monkeypatch)
    _write_entry("tide", root)
    bind_repo("tide", "git@github.com:user/tide.git")

    def fake_run(cmd, **kwargs):
        raise subprocess.TimeoutExpired(cmd, timeout=15)
    monkeypatch.setattr(subprocess, "run", fake_run)

    result = sync_repo("tide")
    assert result["remote_sha"] is None
    assert "TimeoutExpired" in result["error"]


# ---------- pull_repo ----------

def test_pull_repo_happy_path(tmp_path, monkeypatch):
    root = _stub_past_work_dir(tmp_path, monkeypatch)
    _write_entry("tide", root)
    bind_repo("tide", "git@github.com:user/tide.git")
    repo_dir("tide").mkdir(parents=True)

    def fake_run(cmd, **kwargs):
        return _FakeCompleted(stdout="Already up to date.\n", returncode=0)
    monkeypatch.setattr(subprocess, "run", fake_run)
    monkeypatch.setattr(past_work, "git_rev_parse_head", lambda p: "post-pull-sha")

    ok, msg = pull_repo("tide")
    assert ok is True
    assert "up to date" in msg.lower() or msg
    assert read_repo_block("tide").last_known_sha == "post-pull-sha"


def test_pull_repo_refuses_without_clone(tmp_path, monkeypatch):
    root = _stub_past_work_dir(tmp_path, monkeypatch)
    _write_entry("tide", root)
    bind_repo("tide", "git@github.com:user/tide.git")
    with pytest.raises(RepoBindError, match="no local clone"):
        pull_repo("tide")


def test_pull_repo_reports_git_error(tmp_path, monkeypatch):
    root = _stub_past_work_dir(tmp_path, monkeypatch)
    _write_entry("tide", root)
    bind_repo("tide", "git@github.com:user/tide.git")
    repo_dir("tide").mkdir(parents=True)

    def fake_run(cmd, **kwargs):
        return _FakeCompleted(returncode=1, stderr="fatal: Not possible to fast-forward")
    monkeypatch.setattr(subprocess, "run", fake_run)

    ok, msg = pull_repo("tide")
    assert ok is False
    assert "fast-forward" in msg


# ---------- unbind_repo ----------

def test_unbind_repo_strips_block_and_deletes_clone(tmp_path, monkeypatch):
    root = _stub_past_work_dir(tmp_path, monkeypatch)
    _write_entry("tide", root)
    bind_repo("tide", "git@github.com:user/tide.git")
    # Pre-create the clone
    repo_dir("tide").mkdir(parents=True)
    (repo_dir("tide") / "x.txt").write_text("x")

    unbind_repo("tide")
    assert read_repo_block("tide") is None
    assert not repo_dir("tide").exists()


def test_unbind_repo_keeps_clone_with_flag(tmp_path, monkeypatch):
    root = _stub_past_work_dir(tmp_path, monkeypatch)
    _write_entry("tide", root)
    bind_repo("tide", "git@github.com:user/tide.git")
    repo_dir("tide").mkdir(parents=True)

    unbind_repo("tide", keep_clone=True)
    assert read_repo_block("tide") is None
    assert repo_dir("tide").is_dir()


def test_unbind_repo_refuses_without_bind(tmp_path, monkeypatch):
    root = _stub_past_work_dir(tmp_path, monkeypatch)
    _write_entry("tide", root)
    with pytest.raises(RepoBindError, match="no repo bound"):
        unbind_repo("tide")


# ---------- list_entries_with_repo ----------

def test_list_entries_with_repo_table(tmp_path, monkeypatch):
    root = _stub_past_work_dir(tmp_path, monkeypatch)
    _write_entry("tide", root)
    _write_entry("emnlp-2024-contrastive", root)
    bind_repo("tide", "git@github.com:user/tide.git")
    # Pretend emnlp paper was archived: companion folder has paper/ subdir
    paper_dir("emnlp-2024-contrastive").mkdir(parents=True)

    rows = list_entries_with_repo()
    by_slug = {p.stem: (repo, has_paper) for p, repo, has_paper in rows}
    assert by_slug["tide"][0] is not None
    assert by_slug["tide"][0].url == "git@github.com:user/tide.git"
    assert by_slug["tide"][1] is False
    assert by_slug["emnlp-2024-contrastive"][0] is None
    assert by_slug["emnlp-2024-contrastive"][1] is True


# ---------- common/git.py primitives ----------

def test_git_ls_remote_sha_parses_first_line(monkeypatch):
    def fake_run(cmd, **kwargs):
        return _FakeCompleted(stdout="abc123\trefs/heads/main\nignored\n")
    monkeypatch.setattr(subprocess, "run", fake_run)
    r = common_git.git_ls_remote_sha("git@github.com:x/y.git", "main")
    assert r["remote_sha"] == "abc123"
    assert r["error"] is None


def test_git_ls_remote_sha_handles_empty_output(monkeypatch):
    def fake_run(cmd, **kwargs):
        return _FakeCompleted(stdout="", returncode=0)
    monkeypatch.setattr(subprocess, "run", fake_run)
    r = common_git.git_ls_remote_sha("git@github.com:x/y.git", "missing-branch")
    assert r["remote_sha"] is None
    assert "no ref matching" in r["error"]


def test_git_pull_ff_only_handles_missing_dir(tmp_path):
    ok, msg = common_git.git_pull_ff_only(tmp_path / "missing")
    assert ok is False
    assert "not a directory" in msg


def test_guard_under_rejects_escape(tmp_path):
    root = tmp_path / "root"
    root.mkdir()
    with pytest.raises(ValueError):
        common_git.guard_under(root, tmp_path / "elsewhere", "x")


def test_guard_under_accepts_same_dir(tmp_path):
    root = tmp_path / "root"
    root.mkdir()
    out = common_git.guard_under(root, root, "self")
    assert out == root.resolve()
