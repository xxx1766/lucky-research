"""Tests for the experiment YAML-frontmatter parsers."""
from __future__ import annotations

from datetime import date

import pytest

from research_assistant.experiments import (
    DataArtifact,
    Experiment,
    FeasibilityReport,
    FleetSnapshot,
    Version,
    parse_data_index,
    parse_design,
    parse_experiment,
    parse_feasibility,
    parse_fleet,
    parse_version,
    to_agentdb_payload,
)


# ---------- parse_experiment ----------


def test_parse_experiment_happy(tmp_path):
    exp_dir = tmp_path / "lora-eval"
    exp_dir.mkdir()
    p = exp_dir / "manifest.md"
    p.write_text(
        "---\n"
        "slug: lora-eval\n"
        "title: LoRA finetune eval\n"
        "created_at: 2026-05-01\n"
        "repo:\n"
        "  url: git@github.com:u/r.git\n"
        "  branch: main\n"
        "  last_known_sha: null\n"
        "  clone_status: tracked\n"
        "papers: [neurips-2024/some-slug]\n"
        "status: active\n"
        "tags: [lora, eval]\n"
        "---\n"
        "Why now: gpu budget tight.\n",
        encoding="utf-8",
    )
    exp = parse_experiment(p)
    assert isinstance(exp, Experiment)
    assert exp.slug == "lora-eval"
    assert exp.repo.url == "git@github.com:u/r.git"
    assert exp.tags == ["lora", "eval"]
    assert "gpu budget" in exp.body


def test_parse_experiment_slug_defaults_to_dirname(tmp_path):
    exp_dir = tmp_path / "auto-slug"
    exp_dir.mkdir()
    p = exp_dir / "manifest.md"
    p.write_text(
        "---\n"
        "title: Auto\n"
        "created_at: 2026-05-01\n"
        "repo:\n  url: x\n"
        "---\n",
        encoding="utf-8",
    )
    exp = parse_experiment(p)
    assert exp.slug == "auto-slug"


# ---------- parse_version ----------


def test_parse_version_full(tmp_path):
    p = tmp_path / "v1.0.md"
    p.write_text(
        "---\n"
        "version: v1.0\n"
        "description: first attempt\n"
        "status: completed\n"
        "commit_sha: abc123\n"
        "python: 3.12.1\n"
        "metrics: {accuracy: 0.83, loss: 0.41}\n"
        "seeds: [0, 1, 2]\n"
        "---\n"
        "Notes about the run.\n",
        encoding="utf-8",
    )
    v = parse_version(p)
    assert isinstance(v, Version)
    assert v.version == "v1.0"
    assert v.metrics == {"accuracy": 0.83, "loss": 0.41}
    assert v.seeds == [0, 1, 2]


def test_parse_version_defaults_version_to_filename(tmp_path):
    p = tmp_path / "v2.3.md"
    p.write_text("---\ndescription: x\nstatus: planned\n---\nbody\n", encoding="utf-8")
    v = parse_version(p)
    assert v.version == "v2.3"


# ---------- parse_data_index ----------


def test_parse_data_index_multiple_blocks(tmp_path):
    p = tmp_path / "index.md"
    p.write_text(
        "---\n"
        "slug: traces-a\n"
        "category: trace\n"
        "path: s3://b/traces-a\n"
        "sha256: deadbeef\n"
        "---\n"
        "First artifact.\n"
        "---\n"
        "slug: dataset-b\n"
        "category: dataset\n"
        "path: hf://org/data-b\n"
        "size: 12GB\n"
        "---\n"
        "Second artifact.\n",
        encoding="utf-8",
    )
    items = parse_data_index(p)
    assert len(items) == 2
    assert isinstance(items[0], DataArtifact)
    assert items[0].slug == "traces-a"
    assert items[0].category == "trace"
    assert items[1].slug == "dataset-b"
    assert items[1].size == "12GB"


def test_parse_data_index_missing_file_returns_empty(tmp_path):
    assert parse_data_index(tmp_path / "nonexistent.md") == []


def test_parse_data_index_skips_invalid_blocks(tmp_path):
    p = tmp_path / "index.md"
    p.write_text(
        "---\nslug: ok\ncategory: trace\npath: x\n---\nbody\n"
        "---\nslug: bad\ncategory: NOT_A_VALID_CATEGORY\npath: y\n---\nbody\n"
        "---\nslug: ok2\ncategory: log\npath: z\n---\nbody\n",
        encoding="utf-8",
    )
    items = parse_data_index(p)
    assert [a.slug for a in items] == ["ok", "ok2"]


# ---------- parse_fleet ----------


def test_parse_fleet_happy(tmp_path):
    p = tmp_path / "fleet.md"
    p.write_text(
        "---\n"
        "as_of: 2026-05-10\n"
        "machines:\n"
        "  - hostname: gpu-box\n"
        "    gpus: [{name: A100, count: 4}]\n"
        "    cpu_cores: 64\n"
        "    available: true\n"
        "---\n"
        "Usage notes here.\n",
        encoding="utf-8",
    )
    f = parse_fleet(p)
    assert isinstance(f, FleetSnapshot)
    assert f.as_of == date(2026, 5, 10)
    assert len(f.machines) == 1
    assert f.machines[0].hostname == "gpu-box"
    assert f.machines[0].gpus[0].count == 4


# ---------- parse_feasibility ----------


def test_parse_feasibility_with_explicit_date(tmp_path):
    p = tmp_path / "feasibility-2026-05-12.md"
    p.write_text(
        "---\n"
        "slug: lora-eval\n"
        "date: 2026-05-12\n"
        "design_version: d1.0\n"
        "verdict: tight\n"
        "fleet_used: [gpu-box]\n"
        "blockers: [\"single A100 insufficient\"]\n"
        "suggestions:\n"
        "  - id: 1\n"
        "    axis: model-size\n"
        "    change: shrink to 7B\n"
        "    rationale: fits 1xA100\n"
        "    cost: 2 days\n"
        "---\n"
        "Body of report.\n",
        encoding="utf-8",
    )
    r = parse_feasibility(p)
    assert isinstance(r, FeasibilityReport)
    assert r.verdict == "tight"
    assert r.suggestions[0].axis == "model-size"


def test_parse_feasibility_date_falls_back_to_filename(tmp_path):
    p = tmp_path / "feasibility-2026-05-12.md"
    p.write_text(
        "---\n"
        "slug: x\n"
        "design_version: d1.0\n"
        "verdict: feasible\n"
        "---\n",
        encoding="utf-8",
    )
    r = parse_feasibility(p)
    assert r.date == date(2026, 5, 12)


# ---------- parse_design ----------


def test_parse_design_returns_frontmatter_dict(tmp_path):
    p = tmp_path / "d1.0.md"
    p.write_text(
        "---\n"
        "design_version: d1.0\n"
        "created_at: 2026-05-01\n"
        "derived_from: null\n"
        "adopted_suggestions: []\n"
        "---\n"
        "## Research question\n\nfree prose.\n",
        encoding="utf-8",
    )
    d = parse_design(p)
    assert d["design_version"] == "d1.0"
    assert d["adopted_suggestions"] == []


# ---------- to_agentdb_payload ----------


def test_payload_experiment_excludes_body():
    e = Experiment(
        slug="x", title="X", created_at=date(2026, 5, 1),
        repo={"url": "u"}, tags=["a"], body="long prose",
    )
    p = to_agentdb_payload(e)
    assert p["kind"] == "experiment"
    assert p["slug"] == "x"
    assert p["repo_url"] == "u"
    assert "body" not in p
    assert "long prose" not in str(p)


def test_payload_version_excludes_notes():
    v = Version(version="v1.0", description="d", metrics={"acc": 0.9}, notes="long notes")
    p = to_agentdb_payload(v)
    assert p["kind"] == "experiment_version"
    assert p["metrics"] == {"acc": 0.9}
    assert "notes" not in p


def test_payload_data_artifact():
    a = DataArtifact(
        slug="trace-a", category="trace", path="s3://b/x",
        sha256="deadbeef", description="long description",
    )
    p = to_agentdb_payload(a)
    assert p["kind"] == "experiment_data"
    assert p["category"] == "trace"
    assert "description" not in p


def test_payload_rejects_unknown_type():
    with pytest.raises(TypeError):
        to_agentdb_payload({"not": "valid"})  # type: ignore[arg-type]
