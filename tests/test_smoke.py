"""Smoke test: package importable and IO helper resolves repo root correctly."""

from pathlib import Path

import research_assistant
from research_assistant.common import io as ra_io


def test_package_has_version() -> None:
    assert research_assistant.__version__


def test_repo_root_resolves_to_lucky_research() -> None:
    assert ra_io.REPO_ROOT.is_dir()
    assert (ra_io.REPO_ROOT / "CLAUDE.md").is_file()


def test_io_constants_are_under_repo_root() -> None:
    for path in (ra_io.PAPERS_DIR, ra_io.SUMMARIES_DIR, ra_io.DRAFTS_DIR,
                 ra_io.REFERENCES_DIR, ra_io.FIGURES_DIR):
        assert ra_io.REPO_ROOT in Path(path).parents
