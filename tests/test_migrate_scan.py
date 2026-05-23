"""``scan_repo`` partition tests — verify MUST / EXCLUDED-REGISTERED /
EXCLUDED-UNREGISTERED / SKIP buckets land where they should.

Uses fixture repos built under ``tmp_path``; monkeypatches the package's
``REPO_ROOT`` / ``INPUTS_DIR`` / ``OUTPUTS_DIR`` / ``EXPERIMENTS_DIR`` so
the scan walks the fixture rather than the real repo.
"""
from __future__ import annotations

from pathlib import Path

import pytest

from research_assistant.common import io as common_io
from research_assistant.migrate import manifest as mf
from research_assistant.migrate import scan as scan_mod
from research_assistant.migrate.manifest import (
    ArtifactRecord,
    ExternalArtifacts,
    write_external_artifacts,
)
from research_assistant.migrate.scan import scan_repo


@pytest.fixture
def fake_repo(tmp_path, monkeypatch):
    """Set up an empty fixture-repo skeleton and redirect all IO paths to it."""
    root = tmp_path / "repo"
    (root / "inputs" / "papers").mkdir(parents=True)
    (root / "outputs" / "experiments").mkdir(parents=True)
    (root / ".claude").mkdir()
    (root / ".claude-flow").mkdir()
    (root / ".swarm").mkdir()
    monkeypatch.setattr(common_io, "REPO_ROOT", root)
    monkeypatch.setattr(common_io, "INPUTS_DIR", root / "inputs")
    monkeypatch.setattr(common_io, "OUTPUTS_DIR", root / "outputs")
    monkeypatch.setattr(common_io, "EXPERIMENTS_DIR", root / "outputs" / "experiments")
    monkeypatch.setattr(scan_mod, "REPO_ROOT", root)
    monkeypatch.setattr(scan_mod, "INPUTS_DIR", root / "inputs")
    monkeypatch.setattr(scan_mod, "OUTPUTS_DIR", root / "outputs")
    monkeypatch.setattr(scan_mod, "EXPERIMENTS_DIR", root / "outputs" / "experiments")
    monkeypatch.setattr(mf, "EXPERIMENTS_DIR", root / "outputs" / "experiments")
    return root


def _touch(path: Path, size: int = 8) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("wb") as f:
        f.write(b"\x00" * size)


# ---------- MUST: simple files in inputs/ + outputs/ ----------

def test_inputs_papers_pdf_goes_to_must(fake_repo):
    _touch(fake_repo / "inputs" / "papers" / "foo.pdf", size=10)
    result = scan_repo(fake_repo)
    paths = [it.rel_path for it in result.must]
    assert "inputs/papers/foo.pdf" in paths
    assert not result.excluded_unregistered
    assert not result.excluded_registered


def test_outputs_papers_md_goes_to_must(fake_repo):
    _touch(fake_repo / "outputs" / "papers" / "venue" / "dir" / "main.tex", size=20)
    result = scan_repo(fake_repo)
    paths = [it.rel_path for it in result.must]
    assert "outputs/papers/venue/dir/main.tex" in paths


# ---------- SKIP: caches / env / editor noise ----------

def test_env_file_in_inputs_is_skipped(fake_repo):
    _touch(fake_repo / "inputs" / ".env", size=20)
    _touch(fake_repo / "inputs" / ".env.local", size=20)
    result = scan_repo(fake_repo)
    rels = [s.rel_path for s in result.skipped]
    assert "inputs/.env" in rels
    assert "inputs/.env.local" in rels
    assert not any(it.rel_path.endswith(".env") for it in result.must)


def test_pycache_dir_is_pruned(fake_repo):
    _touch(fake_repo / "outputs" / "__pycache__" / "x.pyc", size=20)
    result = scan_repo(fake_repo)
    assert not any("__pycache__" in it.rel_path for it in result.must)


def test_dsstore_is_skipped(fake_repo):
    _touch(fake_repo / "inputs" / "papers" / ".DS_Store", size=4)
    result = scan_repo(fake_repo)
    assert not any(it.rel_path.endswith(".DS_Store") for it in result.must)


# ---------- DBs ----------

def test_ruvector_db_goes_to_must(fake_repo):
    _touch(fake_repo / "ruvector.db", size=100)
    _touch(fake_repo / "ruvector.db-wal", size=100)
    _touch(fake_repo / "ruvector.db-shm", size=100)
    result = scan_repo(fake_repo)
    rels = [it.rel_path for it in result.must]
    assert "ruvector.db" in rels
    assert "ruvector.db-wal" in rels
    assert "ruvector.db-shm" in rels  # bundled into MUST; archive layer drops them


def test_swarm_memory_db_goes_to_must(fake_repo):
    _touch(fake_repo / ".swarm" / "memory.db", size=10)
    result = scan_repo(fake_repo)
    rels = [it.rel_path for it in result.must]
    assert ".swarm/memory.db" in rels


# ---------- .claude / .claude-flow ----------

def test_claude_settings_local_goes_to_must(fake_repo):
    _touch(fake_repo / ".claude" / "settings.local.json", size=10)
    result = scan_repo(fake_repo)
    rels = [it.rel_path for it in result.must]
    assert ".claude/settings.local.json" in rels


def test_claude_flow_config_yaml_goes_to_must(fake_repo):
    _touch(fake_repo / ".claude-flow" / "config.yaml", size=20)
    result = scan_repo(fake_repo)
    rels = [it.rel_path for it in result.must]
    assert ".claude-flow/config.yaml" in rels


def test_claude_flow_logs_are_excluded(fake_repo):
    _touch(fake_repo / ".claude-flow" / "logs" / "daemon.log", size=20)
    _touch(fake_repo / ".claude-flow" / "sessions" / "abc.json", size=20)
    _touch(fake_repo / ".claude-flow" / "metrics" / "m.json", size=20)
    _touch(fake_repo / ".claude-flow" / "daemon.pid", size=4)
    result = scan_repo(fake_repo)
    rels = [it.rel_path for it in result.must]
    for prefix in (".claude-flow/logs", ".claude-flow/sessions", ".claude-flow/metrics"):
        assert not any(r.startswith(prefix) for r in rels)
    assert ".claude-flow/daemon.pid" not in rels


# ---------- EXCLUDED-REGISTERED: experiment artifacts ----------

def _make_experiment(root: Path, slug: str, records: list[ArtifactRecord] | None = None) -> Path:
    exp = root / "outputs" / "experiments" / slug
    exp.mkdir(parents=True)
    if records is not None:
        ea = ExternalArtifacts(artifacts=records)
        write_external_artifacts(exp / "external-artifacts.md", ea)
    return exp


def test_registered_artifact_is_excluded(fake_repo):
    exp = _make_experiment(fake_repo, "exp1", records=[
        ArtifactRecord(
            name="base", path="repo/m1/base", glob="model-*.safetensors",
            type="huggingface", repo="meta-llama/Llama-2-7b-hf",
        )
    ])
    _touch(exp / "repo" / "m1" / "base" / "model-00001.safetensors", size=100)
    _touch(exp / "repo" / "m1" / "base" / "config.json", size=10)
    result = scan_repo(fake_repo)
    rels_must = [it.rel_path for it in result.must]
    rels_excl = [rm.rel_path for rm in result.excluded_registered]
    assert "outputs/experiments/exp1/repo/m1/base/config.json" in rels_must
    assert "outputs/experiments/exp1/repo/m1/base/model-00001.safetensors" in rels_excl
    # The artifact bag should know about the record.
    excluded = result.excluded_artifacts()
    assert any(a.experiment == "exp1" and a.name == "base" for a in excluded)


def test_unregistered_large_file_goes_to_unregistered_bucket(fake_repo):
    _make_experiment(fake_repo, "exp1")  # no external-artifacts.md
    huge = fake_repo / "outputs" / "experiments" / "exp1" / "repo" / "weights.bin"
    _touch(huge, size=2 * 1024 * 1024)  # 2 MB
    result = scan_repo(fake_repo, unregistered_threshold=1024 * 1024)  # 1 MB threshold
    assert len(result.excluded_unregistered) == 1
    u = result.excluded_unregistered[0]
    assert u.rel_path == "outputs/experiments/exp1/repo/weights.bin"
    assert u.experiment_slug == "exp1"
    assert u.in_experiment_rel == "repo/weights.bin"
    rels_must = [it.rel_path for it in result.must]
    assert "outputs/experiments/exp1/repo/weights.bin" not in rels_must


def test_small_unregistered_file_goes_to_must(fake_repo):
    _make_experiment(fake_repo, "exp1")
    _touch(
        fake_repo / "outputs" / "experiments" / "exp1" / "results" / "v1.0" / "metrics.json",
        size=200,
    )
    result = scan_repo(fake_repo)
    rels = [it.rel_path for it in result.must]
    assert "outputs/experiments/exp1/results/v1.0/metrics.json" in rels


def test_underscore_slug_dirs_are_not_treated_as_experiments(fake_repo):
    _touch(
        fake_repo / "outputs" / "experiments" / "_index.md",
        size=10,
    )
    result = scan_repo(fake_repo)
    rels = [it.rel_path for it in result.must]
    assert "outputs/experiments/_index.md" in rels


def test_malformed_external_artifacts_raises(fake_repo):
    exp = _make_experiment(fake_repo, "exp1")
    (exp / "external-artifacts.md").write_text("just text, no frontmatter", encoding="utf-8")
    with pytest.raises(ValueError):
        scan_repo(fake_repo)


# ---------- excluded_artifacts() builds correct dest_path ----------

def test_excluded_artifacts_dest_path_is_repo_relative(fake_repo):
    exp = _make_experiment(fake_repo, "exp1", records=[
        ArtifactRecord(name="base", path="repo/m1/base", glob="*.safetensors"),
    ])
    _touch(exp / "repo" / "m1" / "base" / "x.safetensors", size=10)
    result = scan_repo(fake_repo)
    excluded = result.excluded_artifacts()
    assert excluded[0].dest_path == "outputs/experiments/exp1/repo/m1/base"
