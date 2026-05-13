"""Tests that /figure new --scope experiment appends to versions/<vN.M>.md."""
from pathlib import Path

import pytest

from research_assistant import experiments as exp


def test_append_figures_to_version_creates_field(tmp_path: Path, monkeypatch):
    fake_exp_dir = tmp_path / "experiments"
    monkeypatch.setattr(exp, "EXPERIMENTS_DIR", fake_exp_dir)
    versions = fake_exp_dir / "weightlet-motivation" / "versions"
    versions.mkdir(parents=True)
    (versions / "v1.2.md").write_text(
        "---\n"
        "version: v1.2\n"
        "description: baseline\n"
        "kind: minor\n"
        "---\n"
        "body text\n"
    )
    exp.append_figures_to_version(
        slug="weightlet-motivation",
        version="v1.2",
        figure_stems=["repo/figures/v1.2/perf", "repo/figures/v1.2/mem"],
    )
    text = (versions / "v1.2.md").read_text()
    assert "figures:" in text
    assert "repo/figures/v1.2/perf" in text
    assert "repo/figures/v1.2/mem" in text


def test_append_figures_dedupes(tmp_path: Path, monkeypatch):
    fake_exp_dir = tmp_path / "experiments"
    monkeypatch.setattr(exp, "EXPERIMENTS_DIR", fake_exp_dir)
    versions = fake_exp_dir / "w" / "versions"
    versions.mkdir(parents=True)
    (versions / "v1.0.md").write_text(
        "---\nversion: v1.0\nfigures:\n  - repo/figures/v1.0/perf\n---\nbody\n"
    )
    exp.append_figures_to_version(
        slug="w", version="v1.0", figure_stems=["repo/figures/v1.0/perf"]
    )
    text = (versions / "v1.0.md").read_text()
    # No duplicate
    assert text.count("repo/figures/v1.0/perf") == 1


def test_append_figures_missing_version_errors(tmp_path: Path, monkeypatch):
    fake_exp_dir = tmp_path / "experiments"
    monkeypatch.setattr(exp, "EXPERIMENTS_DIR", fake_exp_dir)
    (fake_exp_dir / "w" / "versions").mkdir(parents=True)
    with pytest.raises(FileNotFoundError):
        exp.append_figures_to_version(
            slug="w", version="v9.9", figure_stems=["x"]
        )
