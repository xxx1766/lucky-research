"""Filesystem conventions for `inputs/` and `outputs/` directories.

Every helper module routes through here so the input/output layout is the single
source of truth.
"""

from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[3]
INPUTS_DIR = REPO_ROOT / "inputs"
OUTPUTS_DIR = REPO_ROOT / "outputs"

PAPERS_INPUT_DIR = INPUTS_DIR / "papers"
SUMMARIES_DIR = OUTPUTS_DIR / "summaries"
DRAFTS_DIR = OUTPUTS_DIR / "drafts"
REFERENCES_DIR = OUTPUTS_DIR / "references"
FIGURES_DIR = OUTPUTS_DIR / "figures"
PAPERS_DIR = OUTPUTS_DIR / "papers"


def ensure_dirs() -> None:
    """Idempotently create the inputs/outputs subdirs the package expects."""
    for d in (
        PAPERS_INPUT_DIR,
        SUMMARIES_DIR,
        DRAFTS_DIR,
        REFERENCES_DIR,
        FIGURES_DIR,
        PAPERS_DIR,
    ):
        d.mkdir(parents=True, exist_ok=True)
