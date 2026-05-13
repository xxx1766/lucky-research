"""Path / slug / scope-resolution tests for figures package."""
from pathlib import Path

import pytest

from research_assistant.figures import paths as fp


def test_slugify_kebab_case():
    assert fp.slugify("Weightlet Architecture") == "weightlet-architecture"
    assert fp.slugify("CNN vs. Transformer") == "cnn-vs-transformer"
    assert fp.slugify("  spaced  ") == "spaced"


def test_slugify_rejects_empty():
    with pytest.raises(ValueError):
        fp.slugify("   ")


def test_paper_figures_dir(tmp_path, monkeypatch):
    fake_papers = tmp_path / "papers"
    monkeypatch.setattr(fp, "PAPERS_DIR", fake_papers)
    out = fp.paper_figures_dir("ICLR-2026", "main-direction")
    assert out == fake_papers / "ICLR-2026" / "main-direction" / "figures"


def test_experiment_figures_dir_versioned(tmp_path, monkeypatch):
    fake_exp = tmp_path / "experiments"
    monkeypatch.setattr(fp, "EXPERIMENTS_DIR", fake_exp)
    out = fp.experiment_figures_dir("weightlet-motivation", version="v1.2")
    assert out == fake_exp / "weightlet-motivation" / "repo" / "figures" / "v1.2"


def test_experiment_figures_dir_arch(tmp_path, monkeypatch):
    fake_exp = tmp_path / "experiments"
    monkeypatch.setattr(fp, "EXPERIMENTS_DIR", fake_exp)
    out = fp.experiment_figures_dir("weightlet-motivation", version=None)
    assert out == fake_exp / "weightlet-motivation" / "repo" / "figures" / "_arch"


def test_resolve_scope_paper_only():
    out = fp.resolve_scope(
        paper_ctx=("ICLR-2026", "main"),
        experiment_ctx=None,
        cli_scope=None,
    )
    assert out == "paper"


def test_resolve_scope_experiment_only():
    out = fp.resolve_scope(
        paper_ctx=None,
        experiment_ctx="weightlet-motivation",
        cli_scope=None,
    )
    assert out == "experiment"


def test_resolve_scope_both_requires_explicit():
    with pytest.raises(fp.AmbiguousScopeError):
        fp.resolve_scope(
            paper_ctx=("ICLR-2026", "main"),
            experiment_ctx="weightlet-motivation",
            cli_scope=None,
        )


def test_resolve_scope_both_with_cli_choice():
    out = fp.resolve_scope(
        paper_ctx=("ICLR-2026", "main"),
        experiment_ctx="weightlet-motivation",
        cli_scope="experiment",
    )
    assert out == "experiment"


def test_resolve_scope_neither_errors():
    with pytest.raises(fp.NoScopeError):
        fp.resolve_scope(paper_ctx=None, experiment_ctx=None, cli_scope=None)


def test_safe_join_blocks_traversal(tmp_path):
    with pytest.raises(ValueError):
        fp.safe_join(tmp_path, "../escape")
    with pytest.raises(ValueError):
        fp.safe_join(tmp_path, "/absolute/path")
