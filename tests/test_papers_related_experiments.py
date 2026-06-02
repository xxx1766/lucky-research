"""Tests for `find_experiments_for_paper` in papers.related_experiments.

Mirrors `tests/test_papers_binding.py`'s fake_dirs fixture: monkeypatch
`EXPERIMENTS_DIR` + `PAPERS_DIR` in every module that captured them at import
time, then build a minimal layout under `tmp_path`.
"""
from __future__ import annotations

from pathlib import Path

import pytest

from research_assistant import common
from research_assistant import experiments as exp_pkg
from research_assistant.papers import (
    binding,
    collect_experiment_results_for_paper,
    find_experiments_for_paper,
)


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


def _write_manifest(exp_root: Path, slug: str, *, papers: list[str], title: str = "X") -> None:
    d = exp_root / slug
    d.mkdir(parents=True, exist_ok=True)
    papers_yaml = "\n".join(f"  - {p}" for p in papers) if papers else " []"
    (d / "manifest.md").write_text(
        "---\n"
        f"slug: {slug}\n"
        f"title: {title}\n"
        "created_at: 2026-05-01\n"
        "repo:\n  url: u\n  branch: main\n"
        f"papers:{(chr(10) + papers_yaml) if papers else ' []'}\n"
        "status: active\n"
        "---\n"
        "body\n",
        encoding="utf-8",
    )


def _write_expert_md(papers_root: Path, venue: str, direction: str, *, exp_slug: str | None) -> None:
    d = papers_root / venue / direction
    d.mkdir(parents=True, exist_ok=True)
    fm = "name: expert\n"
    if exp_slug:
        fm += f"experiment: {exp_slug}\n"
    (d / "expert.md").write_text(f"---\n{fm}---\n\nbody\n", encoding="utf-8")


def test_matches_manifest_papers_field(fake_dirs):
    _, exp_root = fake_dirs
    _write_manifest(exp_root, "lora-eval", papers=["OSDI/cool-direction"])
    _write_manifest(exp_root, "other-exp", papers=["NSDI/unrelated"])
    out = find_experiments_for_paper("OSDI", "cool-direction")
    assert [h["slug"] for h in out] == ["lora-eval"]
    assert out[0]["binding_source"] == "manifest"
    assert out[0]["title"] == "X"
    assert out[0]["latest_version"] is None


def test_skips_paper_slug_only_entries(fake_dirs):
    _, exp_root = fake_dirs
    _write_manifest(exp_root, "lora-eval", papers=["just-a-paper-slug", "no-slash"])
    out = find_experiments_for_paper("OSDI", "cool-direction")
    assert out == []


def test_partial_string_match_does_not_count(fake_dirs):
    _, exp_root = fake_dirs
    # "OSDI/cool-direction-2" is a different direction — must not match.
    _write_manifest(exp_root, "neighbor", papers=["OSDI/cool-direction-2"])
    out = find_experiments_for_paper("OSDI", "cool-direction")
    assert out == []


def test_includes_bound_primary_via_expert_md(fake_dirs):
    papers_root, exp_root = fake_dirs
    # experiment manifest does NOT list the (venue, direction) — only the
    # expert.md binding ties them together.
    _write_manifest(exp_root, "lora-eval", papers=["some-paper"])
    _write_expert_md(papers_root, "OSDI", "cool-direction", exp_slug="lora-eval")
    out = find_experiments_for_paper("OSDI", "cool-direction")
    assert [h["slug"] for h in out] == ["lora-eval"]
    assert out[0]["binding_source"] == "expert.md"


def test_binding_source_both_when_manifest_and_expert_agree(fake_dirs):
    papers_root, exp_root = fake_dirs
    _write_manifest(exp_root, "lora-eval", papers=["OSDI/cool-direction"])
    _write_expert_md(papers_root, "OSDI", "cool-direction", exp_slug="lora-eval")
    out = find_experiments_for_paper("OSDI", "cool-direction")
    assert out[0]["binding_source"] == "both"


def test_returns_latest_version_when_present(fake_dirs):
    _, exp_root = fake_dirs
    _write_manifest(exp_root, "lora-eval", papers=["OSDI/cool-direction"])
    versions = exp_root / "lora-eval" / "versions"
    versions.mkdir()
    (versions / "v1.0.md").write_text(
        "---\nversion: v1.0\ndescription: x\nstatus: completed\n---\n",
        encoding="utf-8",
    )
    (versions / "v2.1.md").write_text(
        "---\nversion: v2.1\ndescription: y\nstatus: completed\n---\n",
        encoding="utf-8",
    )
    out = find_experiments_for_paper("OSDI", "cool-direction")
    assert out[0]["latest_version"] == "v2.1"


def test_sorted_by_slug_when_multiple_hits(fake_dirs):
    _, exp_root = fake_dirs
    _write_manifest(exp_root, "z-exp", papers=["OSDI/cool"])
    _write_manifest(exp_root, "a-exp", papers=["OSDI/cool"])
    _write_manifest(exp_root, "m-exp", papers=["OSDI/cool"])
    out = find_experiments_for_paper("OSDI", "cool")
    assert [h["slug"] for h in out] == ["a-exp", "m-exp", "z-exp"]


def test_empty_when_dir_missing(tmp_path, monkeypatch):
    monkeypatch.setattr(common.io, "EXPERIMENTS_DIR", tmp_path / "nope")
    monkeypatch.setattr(exp_pkg, "EXPERIMENTS_DIR", tmp_path / "nope")
    assert find_experiments_for_paper("v", "d") == []


def test_malformed_manifest_skipped(fake_dirs):
    _, exp_root = fake_dirs
    _write_manifest(exp_root, "good", papers=["OSDI/cool"])
    bad = exp_root / "broken"
    bad.mkdir()
    (bad / "manifest.md").write_text(
        "---\nNOT VALID YAML AT ALL ::: }}}\n---\n",
        encoding="utf-8",
    )
    out = find_experiments_for_paper("OSDI", "cool")
    assert [h["slug"] for h in out] == ["good"]


# ---------- collect_experiment_results_for_paper ----------


def _write_version_file(exp_root: Path, slug: str, version: str) -> None:
    versions = exp_root / slug / "versions"
    versions.mkdir(parents=True, exist_ok=True)
    (versions / f"{version}.md").write_text(
        f"---\nversion: {version}\ndescription: x\nstatus: completed\n---\n",
        encoding="utf-8",
    )


def _write_results_dir(
    exp_root: Path, slug: str, version: str,
    *, files: dict[str, str],
) -> Path:
    results = exp_root / slug / "results" / version
    results.mkdir(parents=True, exist_ok=True)
    for name, body in files.items():
        (results / name).write_text(body, encoding="utf-8")
    return results


def test_collect_returns_empty_when_no_binding(fake_dirs):
    assert collect_experiment_results_for_paper("OSDI", "cool") == []


def test_collect_surfaces_analysis_tex_and_md(fake_dirs):
    _, exp_root = fake_dirs
    _write_manifest(exp_root, "lora-eval", papers=["OSDI/cool"])
    _write_version_file(exp_root, "lora-eval", "v1.0")
    _write_results_dir(exp_root, "lora-eval", "v1.0", files={
        "analysis.tex": r"\paragraph{LoRA wins.}",
        "analysis.md": "# audit",
        "main.json": "{}",
    })
    out = collect_experiment_results_for_paper("OSDI", "cool")
    assert len(out) == 1
    hit = out[0]
    assert hit["slug"] == "lora-eval"
    assert hit["latest_version"] == "v1.0"
    assert hit["analysis_tex"] is not None and hit["analysis_tex"].name == "analysis.tex"
    assert hit["analysis_md"] is not None and hit["analysis_md"].name == "analysis.md"
    assert [p.name for p in hit["other_files"]] == ["main.json"]
    assert hit["results_dir"].name == "v1.0"


def test_collect_returns_null_paths_when_no_results_dir(fake_dirs):
    _, exp_root = fake_dirs
    _write_manifest(exp_root, "lora-eval", papers=["OSDI/cool"])
    _write_version_file(exp_root, "lora-eval", "v1.0")
    # No results/v1.0/ directory at all.
    out = collect_experiment_results_for_paper("OSDI", "cool")
    assert len(out) == 1
    hit = out[0]
    assert hit["results_dir"] is None
    assert hit["analysis_tex"] is None
    assert hit["analysis_md"] is None
    assert hit["other_files"] == []


def test_collect_returns_null_when_no_versions_yet(fake_dirs):
    _, exp_root = fake_dirs
    _write_manifest(exp_root, "lora-eval", papers=["OSDI/cool"])
    out = collect_experiment_results_for_paper("OSDI", "cool")
    assert len(out) == 1
    hit = out[0]
    assert hit["latest_version"] is None
    assert hit["results_dir"] is None


def test_collect_handles_partial_results_dir(fake_dirs):
    _, exp_root = fake_dirs
    _write_manifest(exp_root, "lora-eval", papers=["OSDI/cool"])
    _write_version_file(exp_root, "lora-eval", "v1.0")
    # Only mirrored result file — no analysis.tex/md (user hasn't run /experiment analyze yet).
    _write_results_dir(exp_root, "lora-eval", "v1.0", files={"main.json": "{}"})
    out = collect_experiment_results_for_paper("OSDI", "cool")
    hit = out[0]
    assert hit["analysis_tex"] is None
    assert hit["analysis_md"] is None
    assert [p.name for p in hit["other_files"]] == ["main.json"]


def test_collect_aggregates_multiple_experiments(fake_dirs):
    _, exp_root = fake_dirs
    _write_manifest(exp_root, "a-exp", papers=["OSDI/cool"])
    _write_manifest(exp_root, "b-exp", papers=["OSDI/cool"])
    _write_version_file(exp_root, "a-exp", "v1.0")
    _write_version_file(exp_root, "b-exp", "v2.0")
    _write_results_dir(exp_root, "a-exp", "v1.0", files={"analysis.tex": "A"})
    _write_results_dir(exp_root, "b-exp", "v2.0", files={"analysis.tex": "B"})
    out = collect_experiment_results_for_paper("OSDI", "cool")
    assert [h["slug"] for h in out] == ["a-exp", "b-exp"]
    assert out[0]["analysis_tex"].read_text() == "A"
    assert out[1]["analysis_tex"].read_text() == "B"


def test_collect_uses_latest_version_when_multiple_exist(fake_dirs):
    _, exp_root = fake_dirs
    _write_manifest(exp_root, "exp", papers=["OSDI/cool"])
    _write_version_file(exp_root, "exp", "v1.0")
    _write_version_file(exp_root, "exp", "v1.1")
    _write_version_file(exp_root, "exp", "v2.3")
    _write_results_dir(exp_root, "exp", "v1.0", files={"analysis.tex": "old"})
    _write_results_dir(exp_root, "exp", "v2.3", files={"analysis.tex": "new"})
    out = collect_experiment_results_for_paper("OSDI", "cool")
    assert out[0]["latest_version"] == "v2.3"
    assert out[0]["analysis_tex"].read_text() == "new"
