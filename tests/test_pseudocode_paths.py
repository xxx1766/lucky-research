"""Path / slug / scope-resolution tests for pseudocode package."""
import pytest

from research_assistant.pseudocode import paths as pp
from research_assistant.pseudocode.paths import (
    AmbiguousScopeError,
    NoScopeError,
)


def test_slugify_kebab_case():
    assert pp.slugify("Sparse Attention Update") == "sparse-attention-update"
    assert pp.slugify("DDIM Sampler") == "ddim-sampler"
    assert pp.slugify("  spaced  ") == "spaced"


def test_slugify_rejects_empty():
    with pytest.raises(ValueError):
        pp.slugify("   ")


def test_paper_algorithms_dir(tmp_path, monkeypatch):
    fake_papers = tmp_path / "papers"
    monkeypatch.setattr(pp, "PAPERS_DIR", fake_papers)
    out = pp.paper_algorithms_dir("ICLR-2026", "sparse-attention")
    assert out == fake_papers / "ICLR-2026" / "sparse-attention" / "algorithms"


def test_experiment_algorithms_dir_versioned(tmp_path, monkeypatch):
    fake_exp = tmp_path / "experiments"
    monkeypatch.setattr(pp, "EXPERIMENTS_DIR", fake_exp)
    out = pp.experiment_algorithms_dir("warmup-study", version="v1.2")
    assert out == fake_exp / "warmup-study" / "repo" / "algorithms" / "v1.2"


def test_experiment_algorithms_dir_unversioned(tmp_path, monkeypatch):
    fake_exp = tmp_path / "experiments"
    monkeypatch.setattr(pp, "EXPERIMENTS_DIR", fake_exp)
    out = pp.experiment_algorithms_dir("warmup-study", version=None)
    assert out == fake_exp / "warmup-study" / "repo" / "algorithms" / "_unversioned"


def test_resolve_scope_paper_only():
    scope = pp.resolve_scope(
        paper_ctx=("ICLR-2026", "sparse-attention"),
        experiment_ctx=None,
        cli_scope=None,
    )
    assert scope == "paper"


def test_resolve_scope_experiment_only():
    scope = pp.resolve_scope(
        paper_ctx=None,
        experiment_ctx="warmup-study",
        cli_scope=None,
    )
    assert scope == "experiment"


def test_resolve_scope_cli_override():
    scope = pp.resolve_scope(
        paper_ctx=("ICLR-2026", "sparse"),
        experiment_ctx="warmup",
        cli_scope="paper",
    )
    assert scope == "paper"


def test_resolve_scope_ambiguous():
    with pytest.raises(AmbiguousScopeError):
        pp.resolve_scope(
            paper_ctx=("ICLR-2026", "sparse"),
            experiment_ctx="warmup",
            cli_scope=None,
        )


def test_resolve_scope_no_scope():
    with pytest.raises(NoScopeError):
        pp.resolve_scope(paper_ctx=None, experiment_ctx=None, cli_scope=None)
