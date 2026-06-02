"""Smoke tests for the experiment-runner helpers.

Pure unit tests — no real filesystem outside ``tmp_path``; no real git calls
(``subprocess.run`` is monkeypatched where the code under test would touch it).
"""

from __future__ import annotations

import subprocess
from datetime import date
from pathlib import Path

import pytest
from pydantic import ValidationError

from research_assistant import experiments
from research_assistant.experiments import (
    DataArtifact,
    Experiment,
    ExperimentRepo,
    ExperimentStatus,
    FeasibilityReport,
    FeasibilitySuggestion,
    FleetSnapshot,
    Machine,
    Version,
    bump_major,
    bump_minor,
    capture_env,
    check_repo_updates,
    data_index_path,
    design_version_path,
    experiment_path,
    feasibility_path,
    fleet_input_path,
    format_semver,
    infer_fleet_from_versions,
    latest_design,
    latest_design_path,
    latest_feasibility,
    latest_version,
    list_designs,
    list_versions,
    manifest_path,
    mirror_results,
    next_available_slug,
    next_design_version,
    next_suggested,
    next_version,
    parse_semver,
    register_version,
    render_progress_board,
    render_progress_footer,
    resolve_result_in_repo,
    result_path,
    slugify_experiment,
    stage_status,
    version_path,
)


# ---------- slug + path ----------

def test_slugify_experiment_kebab_case():
    assert slugify_experiment("LoRA Finetune Eval") == "lora-finetune-eval"
    assert slugify_experiment("BERT-finetune sweep") == "bert-finetune-sweep"
    assert slugify_experiment("  spaced  ") == "spaced"


def test_slugify_experiment_rejects_empty():
    with pytest.raises(ValueError):
        slugify_experiment("")
    with pytest.raises(ValueError):
        slugify_experiment("---")


def test_next_available_slug_collision_suffix(tmp_path, monkeypatch):
    monkeypatch.setattr(experiments, "EXPERIMENTS_DIR", tmp_path)
    assert next_available_slug("llm-eval") == "llm-eval"
    (tmp_path / "llm-eval").mkdir()
    assert next_available_slug("llm-eval") == "llm-eval-2"
    (tmp_path / "llm-eval-2").mkdir()
    assert next_available_slug("llm-eval") == "llm-eval-3"


def test_experiment_path_under_experiments_dir(tmp_path, monkeypatch):
    monkeypatch.setattr(experiments, "EXPERIMENTS_DIR", tmp_path)
    p = experiment_path("llm-eval")
    assert p.parent == tmp_path.resolve()
    assert p.name == "llm-eval"


def test_experiment_path_rejects_traversal(tmp_path, monkeypatch):
    monkeypatch.setattr(experiments, "EXPERIMENTS_DIR", tmp_path)
    with pytest.raises(ValueError):
        experiment_path("")
    with pytest.raises(ValueError):
        experiment_path("../escape")
    with pytest.raises(ValueError):
        experiment_path("../../etc/passwd")


def test_version_path_rejects_traversal(tmp_path, monkeypatch):
    monkeypatch.setattr(experiments, "EXPERIMENTS_DIR", tmp_path)
    with pytest.raises(ValueError):
        version_path("exp", "")
    with pytest.raises(ValueError):
        version_path("exp", "../foo")
    with pytest.raises(ValueError):
        version_path("exp", "v1.0/../foo")
    # well-formed shape is fine
    p = version_path("exp", "v1.0")
    assert p.name == "v1.0.md"


def test_result_path_rejects_traversal(tmp_path, monkeypatch):
    monkeypatch.setattr(experiments, "EXPERIMENTS_DIR", tmp_path)
    with pytest.raises(ValueError):
        result_path("exp", "")
    with pytest.raises(ValueError):
        result_path("exp", "../foo")
    p = result_path("exp", "v1.0")
    assert p.name == "v1.0"
    assert p.parent.name == "results"


def test_data_index_path_shape(tmp_path, monkeypatch):
    monkeypatch.setattr(experiments, "EXPERIMENTS_DIR", tmp_path)
    p = data_index_path("exp")
    assert p.name == "index.md"
    assert p.parent.name == "data"


def test_resolve_result_in_repo_rejects_traversal(tmp_path, monkeypatch):
    monkeypatch.setattr(experiments, "EXPERIMENTS_DIR", tmp_path)
    repo = experiment_path("exp") / "repo"
    repo.mkdir(parents=True)
    (repo / "ok.json").write_text("{}")
    p = resolve_result_in_repo("exp", "ok.json")
    assert p.name == "ok.json"
    with pytest.raises(ValueError):
        resolve_result_in_repo("exp", "../escape.json")
    with pytest.raises(ValueError):
        resolve_result_in_repo("exp", "")


# ---------- semver ----------

def test_parse_semver_round_trip():
    assert parse_semver("v1.0") == (1, 0)
    assert parse_semver("v0.3") == (0, 3)
    assert parse_semver("v12.34") == (12, 34)
    assert format_semver(2, 1) == "v2.1"


@pytest.mark.parametrize("bad", ["v1", "1.0", "v1.0.1", "vA.B", "", "v1.0-rc1", "v01.0"])
def test_parse_semver_rejects_malformed(bad):
    if bad == "v01.0":
        # leading zeros are accepted by \d+; document the choice via test
        assert parse_semver(bad) == (1, 0)
    else:
        with pytest.raises(ValueError):
            parse_semver(bad)


def test_bump_major_and_bump_minor():
    assert bump_major("v1.3") == "v2.0"
    assert bump_minor("v1.3") == "v1.4"
    assert bump_major("v0.9") == "v1.0"


def test_next_version_empty(tmp_path, monkeypatch):
    monkeypatch.setattr(experiments, "EXPERIMENTS_DIR", tmp_path)
    experiment_path("exp").mkdir()
    assert next_version("exp", "major") == "v1.0"
    assert next_version("exp", "minor") == "v1.0"


def test_next_version_major_bump(tmp_path, monkeypatch):
    monkeypatch.setattr(experiments, "EXPERIMENTS_DIR", tmp_path)
    vers = experiment_path("exp") / "versions"
    vers.mkdir(parents=True)
    for v in ("v1.0", "v1.1", "v2.0"):
        (vers / f"{v}.md").write_text("---\n---\n")
    assert next_version("exp", "major") == "v3.0"


def test_next_version_minor_bump(tmp_path, monkeypatch):
    monkeypatch.setattr(experiments, "EXPERIMENTS_DIR", tmp_path)
    vers = experiment_path("exp") / "versions"
    vers.mkdir(parents=True)
    for v in ("v1.0", "v1.1", "v2.0"):
        (vers / f"{v}.md").write_text("---\n---\n")
    assert next_version("exp", "minor") == "v2.1"


def test_list_versions_sorted_semver_numeric(tmp_path, monkeypatch):
    monkeypatch.setattr(experiments, "EXPERIMENTS_DIR", tmp_path)
    vers = experiment_path("exp") / "versions"
    vers.mkdir(parents=True)
    # Lexical sort would put v1.10 BEFORE v1.2 — verify numeric sort fixes that.
    for v in ("v1.10", "v1.2", "v1.1", "v2.0"):
        (vers / f"{v}.md").write_text("---\n---\n")
    (vers / "_scratch.md").write_text("not a version")
    assert list_versions("exp") == ["v1.1", "v1.2", "v1.10", "v2.0"]
    assert latest_version("exp") == "v2.0"


def test_next_version_rejects_unknown_kind(tmp_path, monkeypatch):
    monkeypatch.setattr(experiments, "EXPERIMENTS_DIR", tmp_path)
    with pytest.raises(ValueError):
        next_version("exp", "patch")  # type: ignore[arg-type]


# ---------- stage status + progress ----------

def _fresh_status(**overrides) -> ExperimentStatus:
    base = dict(
        has_manifest=False, has_repo=False, has_papers_bound=False,
        has_references=False, has_design=False, has_clone=False,
        version_count=0, last_version=None, last_sync=None,
        last_feasibility_check=None,
    )
    base.update(overrides)
    return ExperimentStatus(**base)


def test_stage_status_empty_dir(tmp_path, monkeypatch):
    monkeypatch.setattr(experiments, "EXPERIMENTS_DIR", tmp_path)
    s = stage_status("exp")
    assert s.has_manifest is False
    assert s.version_count == 0
    assert s.last_version is None
    assert s.last_sync is None


def test_stage_status_tracks_manifest_and_versions(tmp_path, monkeypatch):
    monkeypatch.setattr(experiments, "EXPERIMENTS_DIR", tmp_path)
    exp = experiment_path("exp")
    exp.mkdir()
    manifest_path("exp").write_text(
        "---\nslug: exp\nrepo:\n  url: git@github.com:x/y.git\n"
        "papers:\n  - foo\n  - bar\n---\n",
    )
    vers = exp / "versions"
    vers.mkdir()
    (vers / "v1.0.md").write_text("---\n---\n")
    (vers / "v1.1.md").write_text("---\n---\n")
    s = stage_status("exp")
    assert s.has_manifest is True
    assert s.has_repo is True
    assert s.has_papers_bound is True
    assert s.version_count == 2
    assert s.last_version == "v1.1"
    assert s.last_sync is not None


def test_next_suggested_after_each_gap():
    assert next_suggested(_fresh_status()) == "/experiment init <title>"
    assert next_suggested(_fresh_status(has_manifest=True)) == (
        "/experiment init  (re-run; provide --repo)"
    )
    assert next_suggested(_fresh_status(
        has_manifest=True, has_repo=True, has_papers_bound=True,
    )) == "/experiment scout"
    assert next_suggested(_fresh_status(
        has_manifest=True, has_repo=True,
    )) == "/experiment design"
    # Feasibility step inserted between design done and first version add.
    assert next_suggested(_fresh_status(
        has_manifest=True, has_repo=True, has_design=True,
    )) == "/experiment feasibility"
    # After a feasibility check timestamp lands, suggest version add.
    from datetime import datetime as _dt
    assert next_suggested(_fresh_status(
        has_manifest=True, has_repo=True, has_design=True,
        last_feasibility_check=_dt(2026, 5, 13),
    )) == '/experiment version add v1.0 --description "..."'
    # Once any version exists, the feasibility check is implicitly past.
    assert next_suggested(_fresh_status(
        has_manifest=True, has_repo=True, has_design=True,
        version_count=1, last_version="v1.0",
    )) == "/experiment version add  (or /experiment analyze)"
    assert next_suggested(_fresh_status(
        has_manifest=True, has_repo=True, has_design=True,
        version_count=2, last_version="v1.1",
    )) == "/experiment analyze"


def test_render_progress_footer_no_slug():
    footer = render_progress_footer(None, None)
    assert "no current experiment" in footer
    assert "/experiment init" in footer


def test_render_progress_footer_fresh():
    footer = render_progress_footer("exp", _fresh_status())
    assert "exp" in footer
    assert "[-----] 0/5" in footer


def test_render_progress_footer_with_versions():
    s = _fresh_status(
        has_manifest=True, has_repo=True, has_design=True,
        version_count=2, last_version="v1.1",
    )
    footer = render_progress_footer("exp", s)
    assert "[#####] 5/5" in footer
    assert "/experiment analyze" in footer


def test_render_progress_board_structure():
    s = _fresh_status(
        has_manifest=True, has_repo=True, has_design=True,
        version_count=1, last_version="v1.0",
    )
    board = render_progress_board("exp", s)
    assert board.startswith("exp")
    # init + scout (auto-skip, no papers bound) + design + version = 4/5;
    # analyze needs ≥2 versions.
    assert "[####-] 4/5 stages" in board
    stage_lines = [ln for ln in board.splitlines() if ln.lstrip().startswith(("[x]", "[.]", "[ ]"))]
    assert len(stage_lines) == 5
    assert "Suggested next:" in board


def test_render_progress_board_scout_not_done_when_papers_bound():
    s = _fresh_status(
        has_manifest=True, has_repo=True, has_papers_bound=True,
        has_design=True, version_count=1, last_version="v1.0",
    )
    board = render_progress_board("exp", s)
    # scout is now NOT auto-skipped because papers are bound but references absent;
    # count drops to 3/5. (Bar is count-based, not per-stage — same as /paper.)
    assert "[###--] 3/5 stages" in board
    # The scout line specifically should be marked [ ] with the "run scout" hint.
    scout_line = next(ln for ln in board.splitlines() if "2. scout" in ln)
    assert scout_line.lstrip().startswith("[ ]")
    assert "/experiment scout" in scout_line


# ---------- check_repo_updates ----------

class _FakeCompleted:
    def __init__(self, stdout: str = "", stderr: str = "", returncode: int = 0):
        self.stdout = stdout
        self.stderr = stderr
        self.returncode = returncode


@pytest.fixture
def ssh_agent_loaded(monkeypatch):
    """Pretend an ssh-agent is running with at least one key loaded.

    Lets tests for ``check_repo_updates`` exercise the post-pre-flight
    behavior against SSH URLs without depending on the test host's
    real SSH state.
    """
    monkeypatch.setenv("SSH_AUTH_SOCK", "/tmp/fake-agent.sock")


def test_check_repo_updates_drift(monkeypatch, ssh_agent_loaded):
    def fake_run(cmd, **kwargs):
        return _FakeCompleted(stdout="abc123\trefs/heads/main\n")
    monkeypatch.setattr(subprocess, "run", fake_run)
    result = check_repo_updates("git@github.com:x/y.git", "main", local_sha="def456")
    assert result["remote_sha"] == "abc123"
    assert result["local_sha"] == "def456"
    assert result["drift"] is True
    assert result["error"] is None


def test_check_repo_updates_in_sync(monkeypatch, ssh_agent_loaded):
    def fake_run(cmd, **kwargs):
        return _FakeCompleted(stdout="abc123\trefs/heads/main\n")
    monkeypatch.setattr(subprocess, "run", fake_run)
    result = check_repo_updates("git@github.com:x/y.git", "main", local_sha="abc123")
    assert result["remote_sha"] == "abc123"
    assert result["drift"] is False
    assert result["error"] is None


def test_check_repo_updates_handles_git_failure(monkeypatch, ssh_agent_loaded):
    # ssh-add (pre-flight) returns 0; git ls-remote (the second call) returns 128.
    calls = iter([
        _FakeCompleted(returncode=0),
        _FakeCompleted(returncode=128, stderr="fatal: repository not found"),
    ])

    def fake_run(cmd, **kwargs):
        return next(calls)

    monkeypatch.setattr(subprocess, "run", fake_run)
    result = check_repo_updates("git@github.com:x/y.git", "main")
    assert result["remote_sha"] is None
    assert result["drift"] is None
    assert "repository not found" in result["error"]


def test_check_repo_updates_handles_timeout(monkeypatch, ssh_agent_loaded):
    # Pre-flight succeeds; ls-remote times out.
    calls = iter([
        _FakeCompleted(returncode=0),
    ])

    def fake_run(cmd, **kwargs):
        try:
            return next(calls)
        except StopIteration:
            raise subprocess.TimeoutExpired(cmd, timeout=15)

    monkeypatch.setattr(subprocess, "run", fake_run)
    result = check_repo_updates("git@github.com:x/y.git", "main")
    assert result["remote_sha"] is None
    assert "TimeoutExpired" in result["error"]


def test_check_repo_updates_handles_missing_git(monkeypatch, ssh_agent_loaded):
    # ssh-add OK; git not on PATH for ls-remote.
    calls = iter([
        _FakeCompleted(returncode=0),
    ])

    def fake_run(cmd, **kwargs):
        try:
            return next(calls)
        except StopIteration:
            raise FileNotFoundError("git not on PATH")

    monkeypatch.setattr(subprocess, "run", fake_run)
    result = check_repo_updates("git@github.com:x/y.git", "main")
    assert "FileNotFoundError" in result["error"]


# ---------- check_repo_updates pre-flight ----------


def test_check_repo_updates_ssh_no_agent_socket(monkeypatch):
    monkeypatch.delenv("SSH_AUTH_SOCK", raising=False)
    # subprocess.run should NEVER fire — pre-flight exits early.
    monkeypatch.setattr(subprocess, "run", lambda *a, **k: pytest.fail("git was called"))
    result = check_repo_updates("git@github.com:x/y.git", "main")
    assert result["remote_sha"] is None
    assert "SSH_AUTH_SOCK" in result["error"]
    assert "ssh-add" in result["error"]


def test_check_repo_updates_ssh_agent_running_but_no_keys(monkeypatch, ssh_agent_loaded):
    # ssh-add -l returns 1 ("agent running, no keys") — pre-flight should
    # surface this without calling git.
    git_called = []

    def fake_run(cmd, **kwargs):
        if cmd[:2] == ["ssh-add", "-l"]:
            return _FakeCompleted(returncode=1, stderr="The agent has no identities.")
        git_called.append(cmd)
        return _FakeCompleted()

    monkeypatch.setattr(subprocess, "run", fake_run)
    result = check_repo_updates("git@github.com:x/y.git", "main")
    assert git_called == []
    assert "no keys loaded" in result["error"]
    assert "ssh-add" in result["error"]


def test_check_repo_updates_https_skips_ssh_preflight(monkeypatch):
    # HTTPS URLs don't need an agent — pre-flight shouldn't touch SSH state
    # even when SSH_AUTH_SOCK is unset.
    monkeypatch.delenv("SSH_AUTH_SOCK", raising=False)
    calls: list[list[str]] = []

    def fake_run(cmd, **kwargs):
        calls.append(list(cmd))
        return _FakeCompleted(stdout="abc123\trefs/heads/main\n")

    monkeypatch.setattr(subprocess, "run", fake_run)
    result = check_repo_updates("https://github.com/x/y.git", "main")
    assert result["remote_sha"] == "abc123"
    # ssh-add must never have been called for an HTTPS URL.
    assert all(c[:1] != ["ssh-add"] for c in calls)


def test_check_repo_updates_https_passes_GIT_TERMINAL_PROMPT_zero(monkeypatch):
    captured: dict = {}

    def fake_run(cmd, **kwargs):
        captured["env"] = kwargs.get("env") or {}
        return _FakeCompleted(stdout="abc123\trefs/heads/main\n")

    monkeypatch.setattr(subprocess, "run", fake_run)
    check_repo_updates("https://github.com/x/y.git", "main")
    assert captured["env"].get("GIT_TERMINAL_PROMPT") == "0"


def test_check_repo_updates_preflight_ignores_missing_ssh_add(monkeypatch, ssh_agent_loaded):
    # When ssh-add isn't on PATH, pre-flight should fall through to git
    # rather than block — non-default keys configured via ~/.ssh/config can
    # work even when `ssh-add -l` would have said "no keys".
    def fake_run(cmd, **kwargs):
        if cmd[:2] == ["ssh-add", "-l"]:
            raise FileNotFoundError("ssh-add not on PATH")
        return _FakeCompleted(stdout="abc123\trefs/heads/main\n")

    monkeypatch.setattr(subprocess, "run", fake_run)
    result = check_repo_updates("git@github.com:x/y.git", "main")
    assert result["remote_sha"] == "abc123"
    assert result["error"] is None


# ---------- mirror_results ----------

def test_mirror_results_copies_file(tmp_path, monkeypatch):
    monkeypatch.setattr(experiments, "EXPERIMENTS_DIR", tmp_path / "outputs")
    experiment_path("exp").mkdir(parents=True)
    src = tmp_path / "src.json"
    src.write_text('{"rouge_l": 0.4}')
    dest = mirror_results("exp", "v1.0", src)
    assert dest.is_file()
    assert dest.read_text() == '{"rouge_l": 0.4}'
    assert dest.name == "src.json"
    assert dest.parent.name == "v1.0"


def test_mirror_results_copies_directory(tmp_path, monkeypatch):
    monkeypatch.setattr(experiments, "EXPERIMENTS_DIR", tmp_path / "outputs")
    experiment_path("exp").mkdir(parents=True)
    src = tmp_path / "src-dir"
    src.mkdir()
    (src / "a.txt").write_text("a")
    (src / "b.txt").write_text("b")
    dest = mirror_results("exp", "v1.0", src)
    assert dest.is_dir()
    assert (dest / "a.txt").read_text() == "a"
    assert (dest / "b.txt").read_text() == "b"


def test_mirror_results_rejects_missing_src(tmp_path, monkeypatch):
    monkeypatch.setattr(experiments, "EXPERIMENTS_DIR", tmp_path / "outputs")
    experiment_path("exp").mkdir(parents=True)
    with pytest.raises(FileNotFoundError):
        mirror_results("exp", "v1.0", tmp_path / "nope.json")


def test_mirror_results_refuses_overwrite(tmp_path, monkeypatch):
    monkeypatch.setattr(experiments, "EXPERIMENTS_DIR", tmp_path / "outputs")
    experiment_path("exp").mkdir(parents=True)
    src = tmp_path / "src.json"
    src.write_text("{}")
    mirror_results("exp", "v1.0", src)
    with pytest.raises(FileExistsError):
        mirror_results("exp", "v1.0", src)
    # force=True succeeds
    mirror_results("exp", "v1.0", src, force=True)


def test_mirror_results_traversal_guard(tmp_path, monkeypatch):
    monkeypatch.setattr(experiments, "EXPERIMENTS_DIR", tmp_path / "outputs")
    experiment_path("exp").mkdir(parents=True)
    boundary = tmp_path / "boundary"
    boundary.mkdir()
    escape = tmp_path / "escape.json"
    escape.write_text("{}")
    with pytest.raises(ValueError):
        mirror_results("exp", "v1.0", escape, boundary_root=boundary)


def test_mirror_results_large_file_requires_force(tmp_path, monkeypatch):
    monkeypatch.setattr(experiments, "EXPERIMENTS_DIR", tmp_path / "outputs")
    monkeypatch.setattr(experiments, "_LARGE_RESULT_BYTES", 10)
    experiment_path("exp").mkdir(parents=True)
    big = tmp_path / "big.bin"
    big.write_bytes(b"x" * 100)
    with pytest.raises(ValueError, match="MB"):
        mirror_results("exp", "v1.0", big)
    dest = mirror_results("exp", "v1.0", big, force=True)
    assert dest.is_file()


# ---------- capture_env ----------

def test_capture_env_returns_dict_with_baseline_keys():
    env = capture_env()
    # These never depend on subprocess — must always be present.
    for k in ("hostname", "os", "arch", "python"):
        assert k in env
        assert env[k]


def test_capture_env_omits_keys_on_subprocess_failure(monkeypatch):
    def fake_run(cmd, **kwargs):
        raise FileNotFoundError("no such binary")
    monkeypatch.setattr(subprocess, "run", fake_run)
    env = capture_env()
    # Baseline keys still present (no subprocess needed)
    for k in ("hostname", "os", "arch", "python"):
        assert k in env
    # Probed keys omitted, not crashed
    assert "cuda" not in env
    assert "gpu" not in env
    assert "libraries" not in env


# ---------- Pydantic models ----------

def test_pydantic_experiment_minimal():
    exp = Experiment(
        slug="exp",
        title="Test",
        created_at=date(2026, 5, 13),
        repo=ExperimentRepo(url="git@github.com:x/y.git"),
    )
    assert exp.slug == "exp"
    assert exp.papers == []
    assert exp.repo.branch == "main"
    assert exp.repo.clone_status == "tracked"
    assert exp.status == "active"


def test_pydantic_experiment_requires_repo():
    with pytest.raises(ValidationError):
        Experiment(  # type: ignore[call-arg]
            slug="exp", title="Test", created_at=date(2026, 5, 13),
        )


def test_pydantic_version_minimal():
    v = Version(version="v1.0", description="baseline")
    assert v.version == "v1.0"
    assert v.kind == "minor"
    assert v.status == "completed"
    assert v.seeds == []
    assert v.metrics == {}


def test_data_artifact_categories_validated():
    DataArtifact(slug="ckpt-v1.0", category="checkpoint", path="repo/runs/v1.0/ckpt/")
    DataArtifact(slug="trace-1", category="trace", path="s3://x/y")
    with pytest.raises(ValidationError):
        DataArtifact(slug="x", category="invalid", path="p")  # type: ignore[arg-type]


# ---------- register_version ----------

def _stub_env_and_pip(monkeypatch):
    """Monkeypatch capture_env to a deterministic value and skip pip freeze."""
    monkeypatch.setattr(experiments, "capture_env", lambda: {
        "hostname": "test-host", "os": "Linux", "arch": "x86_64", "python": "3.12.0",
    })
    monkeypatch.setattr(experiments, "_probe_full_pip_freeze", lambda: None)
    monkeypatch.setattr(experiments, "current_commit_sha", lambda slug: None)


def test_register_version_writes_file(tmp_path, monkeypatch):
    monkeypatch.setattr(experiments, "EXPERIMENTS_DIR", tmp_path)
    _stub_env_and_pip(monkeypatch)
    experiment_path("exp").mkdir()
    p = register_version("exp", "v1.0", "baseline run")
    assert p.is_file()
    text = p.read_text()
    assert "---\n" in text
    # Bare YAML scalars are fine — v1.0 doesn't need quoting.
    assert "version: v1.0" in text
    assert "description: baseline run" in text
    assert "hostname: test-host" in text
    assert "python: 3.12.0" in text


def test_register_version_refuses_overwrite(tmp_path, monkeypatch):
    monkeypatch.setattr(experiments, "EXPERIMENTS_DIR", tmp_path)
    _stub_env_and_pip(monkeypatch)
    experiment_path("exp").mkdir()
    register_version("exp", "v1.0", "first")
    with pytest.raises(FileExistsError, match="suggested next"):
        register_version("exp", "v1.0", "second")


def test_register_version_accepts_non_monotonic_user_choice(tmp_path, monkeypatch):
    """Lock the contract: explicit version arg is honored even when it skips
    ahead of what next_version would suggest. Users can deliberately gap."""
    monkeypatch.setattr(experiments, "EXPERIMENTS_DIR", tmp_path)
    _stub_env_and_pip(monkeypatch)
    experiment_path("exp").mkdir()
    register_version("exp", "v1.0", "baseline")
    register_version("exp", "v1.1", "small tweak")
    # next_version would suggest v1.2 (minor) or v2.0 (major); user picks v5.0
    skipped = register_version("exp", "v5.0", "rewrite", kind="major")
    assert skipped.is_file()
    assert list_versions("exp") == ["v1.0", "v1.1", "v5.0"]


def test_register_version_rejects_bad_kind(tmp_path, monkeypatch):
    monkeypatch.setattr(experiments, "EXPERIMENTS_DIR", tmp_path)
    _stub_env_and_pip(monkeypatch)
    experiment_path("exp").mkdir()
    with pytest.raises(ValueError):
        register_version("exp", "v1.0", "x", kind="patch")  # type: ignore[arg-type]


# ---------- feasibility / fleet / design-version models ----------

def test_machine_pydantic_minimal():
    m = Machine(hostname="gpu-box-3")
    assert m.hostname == "gpu-box-3"
    assert m.gpus == []
    assert m.available is True
    assert m.ram_gb is None


def test_machine_pydantic_full():
    m = Machine(
        hostname="lab-a100",
        gpus=[experiments.GPUInfo(name="A100", count=2, driver="545.23")],
        cpu_cores=64, ram_gb=512.0, disk_gb=2000.0,
        network="100 GbE", available=False, notes="Reserved Tue/Thu",
    )
    assert m.gpus[0].name == "A100"
    assert m.available is False
    assert m.ram_gb == 512.0


def test_fleet_snapshot_pydantic_minimal():
    from datetime import date as _date
    snap = FleetSnapshot(as_of=_date(2026, 5, 13))
    assert snap.machines == []
    assert snap.body == ""


def test_feasibility_suggestion_axis_validated():
    FeasibilitySuggestion(id=1, axis="model-size", change="x", rationale="y")
    FeasibilitySuggestion(id=2, axis="baseline-pruning", change="x", rationale="y")
    with pytest.raises(ValidationError):
        FeasibilitySuggestion(  # type: ignore[arg-type]
            id=3, axis="not-an-axis", change="x", rationale="y",
        )


def test_feasibility_report_minimal():
    from datetime import date as _date
    r = FeasibilityReport(
        slug="exp", date=_date(2026, 5, 13),
        design_version="d1.0", verdict="tight",
    )
    assert r.suggestions == []
    assert r.blockers == []
    assert r.fleet_used == []


# ---------- fleet + feasibility paths ----------

def test_fleet_input_path_under_inputs_dir():
    p = fleet_input_path()
    assert p.name == "fleet.md"
    assert p.parent.name == "inputs"


def test_feasibility_path_collision_suffix(tmp_path, monkeypatch):
    monkeypatch.setattr(experiments, "EXPERIMENTS_DIR", tmp_path)
    experiment_path("exp").mkdir()
    from datetime import date as _date
    d = _date(2026, 5, 13)
    first = feasibility_path("exp", d)
    assert first.name == "feasibility-2026-05-13.md"
    first.write_text("first")
    second = feasibility_path("exp", d)
    assert second.name == "feasibility-2026-05-13-2.md"
    second.write_text("second")
    third = feasibility_path("exp", d)
    assert third.name == "feasibility-2026-05-13-3.md"


def test_latest_feasibility_picks_newest(tmp_path, monkeypatch):
    monkeypatch.setattr(experiments, "EXPERIMENTS_DIR", tmp_path)
    exp = experiment_path("exp")
    exp.mkdir()
    # Drop multiple files; lex sort of `.md` vs `-2.md` is wrong (`.` > `-` in ASCII),
    # so the helper must sort by (date, suffix) tuple.
    (exp / "feasibility-2026-05-13.md").write_text("a")
    (exp / "feasibility-2026-05-13-2.md").write_text("b")
    (exp / "feasibility-2026-05-12.md").write_text("c")
    assert latest_feasibility("exp").name == "feasibility-2026-05-13-2.md"


def test_latest_feasibility_none_when_empty(tmp_path, monkeypatch):
    monkeypatch.setattr(experiments, "EXPERIMENTS_DIR", tmp_path)
    experiment_path("exp").mkdir()
    assert latest_feasibility("exp") is None


# ---------- design-plan versioning ----------

def test_list_designs_sorted_semver_numeric(tmp_path, monkeypatch):
    monkeypatch.setattr(experiments, "EXPERIMENTS_DIR", tmp_path)
    designs = experiment_path("exp") / "designs"
    designs.mkdir(parents=True)
    for v in ("d1.10", "d1.2", "d1.1", "d2.0"):
        (designs / f"{v}.md").write_text("---\n---\n")
    (designs / "v1.0.md").write_text("wrong prefix — should be filtered")
    assert list_designs("exp") == ["d1.1", "d1.2", "d1.10", "d2.0"]
    assert latest_design("exp") == "d2.0"


def test_next_design_version_empty(tmp_path, monkeypatch):
    monkeypatch.setattr(experiments, "EXPERIMENTS_DIR", tmp_path)
    experiment_path("exp").mkdir()
    assert next_design_version("exp", "minor") == "d1.0"
    assert next_design_version("exp", "major") == "d1.0"


def test_next_design_version_major_minor_bumps(tmp_path, monkeypatch):
    monkeypatch.setattr(experiments, "EXPERIMENTS_DIR", tmp_path)
    designs = experiment_path("exp") / "designs"
    designs.mkdir(parents=True)
    for v in ("d1.0", "d1.1", "d2.0"):
        (designs / f"{v}.md").write_text("---\n---\n")
    assert next_design_version("exp", "major") == "d3.0"
    assert next_design_version("exp", "minor") == "d2.1"


def test_design_version_path_rejects_traversal(tmp_path, monkeypatch):
    monkeypatch.setattr(experiments, "EXPERIMENTS_DIR", tmp_path)
    with pytest.raises(ValueError):
        design_version_path("exp", "")
    with pytest.raises(ValueError):
        design_version_path("exp", "../foo")
    with pytest.raises(ValueError):
        design_version_path("exp", "v1.0")  # wrong prefix
    p = design_version_path("exp", "d1.0")
    assert p.name == "d1.0.md"
    assert p.parent.name == "designs"


def test_latest_design_path_returns_highest(tmp_path, monkeypatch):
    monkeypatch.setattr(experiments, "EXPERIMENTS_DIR", tmp_path)
    designs = experiment_path("exp") / "designs"
    designs.mkdir(parents=True)
    (designs / "d1.0.md").write_text("---\n---\n")
    (designs / "d1.1.md").write_text("---\n---\n")
    assert latest_design_path("exp").name == "d1.1.md"


def test_latest_design_path_none_when_empty(tmp_path, monkeypatch):
    monkeypatch.setattr(experiments, "EXPERIMENTS_DIR", tmp_path)
    experiment_path("exp").mkdir()
    assert latest_design_path("exp") is None


def test_bump_minor_with_design_prefix():
    assert experiments.bump_minor("d1.3", prefix="d") == "d1.4"
    assert experiments.bump_major("d1.3", prefix="d") == "d2.0"


# ---------- fleet inference from versions ----------

def _write_version_with_host(
    versions_dir: Path, version: str, hostname: str, gpu_name: str | None = None
):
    versions_dir.mkdir(parents=True, exist_ok=True)
    gpu_block = "gpu: []" if gpu_name is None else (
        f"gpu:\n  - name: {gpu_name}\n    count: 1\n    driver: 545.23"
    )
    (versions_dir / f"{version}.md").write_text(
        "---\n"
        f'version: "{version}"\n'
        'description: "x"\n'
        "kind: minor\n"
        "host:\n"
        f"  hostname: {hostname}\n"
        '  os: "Linux"\n'
        "  arch: x86_64\n"
        f"{gpu_block}\n"
        "---\n\n"
        "# body\n"
    )


def test_infer_fleet_from_versions_empty_when_no_experiments(tmp_path, monkeypatch):
    monkeypatch.setattr(experiments, "EXPERIMENTS_DIR", tmp_path / "missing")
    assert infer_fleet_from_versions() == []


def test_infer_fleet_from_versions_dedupes_by_hostname(tmp_path, monkeypatch):
    monkeypatch.setattr(experiments, "EXPERIMENTS_DIR", tmp_path)
    _write_version_with_host(
        experiment_path("exp1") / "versions", "v1.0", "gpu-box-3", "A100",
    )
    _write_version_with_host(
        experiment_path("exp2") / "versions", "v1.0", "gpu-box-3", "A100",
    )
    fleet = infer_fleet_from_versions()
    assert len(fleet) == 1
    assert fleet[0].hostname == "gpu-box-3"
    # GPU only listed once even though seen in two versions on same host
    assert [g.name for g in fleet[0].gpus] == ["A100"]


def test_infer_fleet_from_versions_aggregates_gpus(tmp_path, monkeypatch):
    monkeypatch.setattr(experiments, "EXPERIMENTS_DIR", tmp_path)
    _write_version_with_host(
        experiment_path("exp") / "versions", "v1.0", "host-a", "A100",
    )
    _write_version_with_host(
        experiment_path("exp") / "versions", "v1.1", "host-a", "H100",
    )
    fleet = infer_fleet_from_versions()
    assert len(fleet) == 1
    names = {g.name for g in fleet[0].gpus}
    assert names == {"A100", "H100"}


def test_infer_fleet_from_versions_sorts_by_hostname(tmp_path, monkeypatch):
    monkeypatch.setattr(experiments, "EXPERIMENTS_DIR", tmp_path)
    _write_version_with_host(
        experiment_path("exp1") / "versions", "v1.0", "zeta-host", "A100",
    )
    _write_version_with_host(
        experiment_path("exp2") / "versions", "v1.0", "alpha-host", "A100",
    )
    fleet = infer_fleet_from_versions()
    assert [m.hostname for m in fleet] == ["alpha-host", "zeta-host"]


# ---------- stage_status: feasibility + design refactor ----------

def test_stage_status_tracks_last_feasibility_check(tmp_path, monkeypatch):
    monkeypatch.setattr(experiments, "EXPERIMENTS_DIR", tmp_path)
    exp = experiment_path("exp")
    exp.mkdir()
    manifest_path("exp").write_text("---\nslug: exp\n---\n")
    (exp / "feasibility-2026-05-13.md").write_text("x")
    s = stage_status("exp")
    assert s.last_feasibility_check is not None


def test_stage_status_has_design_via_designs_dir(tmp_path, monkeypatch):
    monkeypatch.setattr(experiments, "EXPERIMENTS_DIR", tmp_path)
    exp = experiment_path("exp")
    exp.mkdir()
    manifest_path("exp").write_text("---\nslug: exp\n---\n")
    designs = exp / "designs"
    designs.mkdir()
    (designs / "d1.0.md").write_text("---\n---\n")
    assert stage_status("exp").has_design is True


def test_stage_status_has_design_via_legacy_singleton(tmp_path, monkeypatch):
    """Defensive: an old design.md (pre-refactor) is still recognized."""
    monkeypatch.setattr(experiments, "EXPERIMENTS_DIR", tmp_path)
    exp = experiment_path("exp")
    exp.mkdir()
    manifest_path("exp").write_text("---\nslug: exp\n---\n")
    (exp / "design.md").write_text("legacy")
    assert stage_status("exp").has_design is True


def test_render_progress_board_shows_last_feasibility():
    from datetime import datetime as _dt
    s = _fresh_status(
        has_manifest=True, has_repo=True, has_design=True,
        version_count=1, last_version="v1.0",
        last_feasibility_check=_dt(2026, 5, 13, 10, 0, 0),
    )
    board = render_progress_board("exp", s)
    assert "Last feasibility:" in board
    assert "2026-05-13" in board
