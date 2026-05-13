"""Filesystem conventions for `inputs/` and `outputs/` directories.

Every helper module routes through here so the input/output layout is the single
source of truth.
"""

from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[3]
INPUTS_DIR = REPO_ROOT / "inputs"
OUTPUTS_DIR = REPO_ROOT / "outputs"

PAPERS_INPUT_DIR = INPUTS_DIR / "papers"
PAST_WORK_DIR = INPUTS_DIR / "past-work"
BOSS_PROFILE_DIR = INPUTS_DIR / "boss-profile"
BOSS_MEETINGS_DIR = BOSS_PROFILE_DIR / "meetings"
BOSS_REPORTS_DIR = BOSS_PROFILE_DIR / "reports"
BOSS_REHEARSALS_DIR = BOSS_PROFILE_DIR / "rehearsals"
FLEET_INPUT_PATH = INPUTS_DIR / "fleet.md"
FIGURE_REFS_DIR = INPUTS_DIR / "figure-refs"
FIGURE_REFS_STAGING_DIR = FIGURE_REFS_DIR / "staging"
SUMMARIES_DIR = OUTPUTS_DIR / "summaries"
DRAFTS_DIR = OUTPUTS_DIR / "drafts"
REFERENCES_DIR = OUTPUTS_DIR / "references"
FIGURES_DIR = OUTPUTS_DIR / "figures"
PAPERS_DIR = OUTPUTS_DIR / "papers"
EXPERIMENTS_DIR = OUTPUTS_DIR / "experiments"


def ensure_dirs() -> None:
    """Idempotently create the inputs/outputs subdirs the package expects."""
    for d in (
        PAPERS_INPUT_DIR,
        PAST_WORK_DIR,
        BOSS_PROFILE_DIR,
        BOSS_MEETINGS_DIR,
        BOSS_REPORTS_DIR,
        BOSS_REHEARSALS_DIR,
        FIGURE_REFS_DIR,
        FIGURE_REFS_STAGING_DIR,
        SUMMARIES_DIR,
        DRAFTS_DIR,
        REFERENCES_DIR,
        FIGURES_DIR,
        PAPERS_DIR,
        EXPERIMENTS_DIR,
    ):
        d.mkdir(parents=True, exist_ok=True)
