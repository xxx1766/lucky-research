"""Experiment-runner helpers — schema + I/O + repo-state + env capture.

Each experiment lives at ``outputs/experiments/<slug>/`` (gitignored). The bound
GitHub repo is the cross-machine truth for code/data; this package is the
control center that tracks repo state, records versioned execution attempts
(semver), and mirrors structured result files so downstream features (e.g.
``/paper``) can consume them offline.

Originally one ~1300-line module; split into focused sub-modules in 2026-06:

* :mod:`.paths` — slug + path math + semver helpers (no I/O beyond exists/glob).
* :mod:`.models` — Pydantic types + the ``ExperimentStatus`` dataclass.
* :mod:`.status` — disk-derived stage status + progress board.
* :mod:`.repo` — git / mirror-results filesystem ops.
* :mod:`.env_probe` — CUDA / GPU / library probes for ``capture_env``.
* :mod:`.registration` — ``register_version`` + fleet inference + figure link-back.
* :mod:`.parsers` — frontmatter parsers + ``to_agentdb_payload``.

Mirrors three patterns already in the codebase:

* ``research_assistant.papers`` for stage status + progress rendering.
* ``research_assistant.mentor.boss_profile`` for collision-suffix paths and
  path-traversal guards.
* ``research_assistant.mentor.past_work`` for Pydantic models + the
  frontmatter-parser defer pattern.

Slug convention matches :func:`research_assistant.mentor.past_work.slugify` —
kebab-case English, non-alphanumerics collapsed to hyphens.

Monkeypatchable hooks
---------------------

These names are exposed at the package root so tests can override them via
``monkeypatch.setattr(experiments, "<name>", ...)``. Sub-modules access them
lazily through ``import research_assistant.experiments as _exp`` and
``_exp.<name>`` at call time:

* ``EXPERIMENTS_DIR`` / ``FLEET_INPUT_PATH`` — base directories (see
  :mod:`.paths`, :mod:`.parsers`, :mod:`.registration`).
* ``_LARGE_RESULT_BYTES`` — the mirror size threshold (see :mod:`.repo`).
* ``capture_env`` / ``_probe_full_pip_freeze`` / ``current_commit_sha`` /
  ``mirror_results`` — hooks used by
  :func:`.registration.register_version`.
"""
from __future__ import annotations

# --- Bind monkeypatchable values BEFORE importing sub-modules.
# Sub-modules read these through ``research_assistant.experiments`` at call time
# (lazy attribute access) so test monkeypatches propagate.
from research_assistant.common.io import EXPERIMENTS_DIR, FLEET_INPUT_PATH

_LARGE_RESULT_BYTES = 100 * 1024 * 1024  # 100 MB


# --- Sub-module imports (each is small enough to read top-to-bottom).
from .env_probe import (  # noqa: E402, F401
    _probe_full_pip_freeze,  # re-export only for ``monkeypatch.setattr(experiments, "_probe_full_pip_freeze", ...)``
    capture_env,
)
from .models import (  # noqa: E402
    DataArtifact,
    Experiment,
    ExperimentRepo,
    FeasibilityReport,
    FeasibilitySuggestion,
    FleetSnapshot,
    GPUInfo,
    HostInfo,
    Machine,
    Version,
)
from .parsers import (  # noqa: E402
    list_experiments,
    parse_data_index,
    parse_design,
    parse_experiment,
    parse_feasibility,
    parse_fleet,
    parse_version,
    to_agentdb_payload,
)
from .paths import (  # noqa: E402
    bump_major,
    bump_minor,
    data_index_path,
    design_version_path,
    experiment_path,
    feasibility_path,
    fleet_input_path,
    format_semver,
    latest_design,
    latest_design_path,
    latest_feasibility,
    latest_version,
    legacy_design_path,
    list_designs,
    list_versions,
    manifest_path,
    next_available_slug,
    next_design_version,
    next_version,
    parse_semver,
    references_path,
    repo_clone_path,
    resolve_result_in_repo,
    result_path,
    slugify_experiment,
    status_path,
    version_path,
)
from .registration import (  # noqa: E402
    append_figures_to_version,
    infer_fleet_from_versions,
    register_version,
)
from .repo import (  # noqa: E402
    check_repo_updates,
    clone_repo,
    current_commit_sha,
    mirror_results,
)
from .status import (  # noqa: E402
    ExperimentStatus,
    next_suggested,
    render_progress_board,
    render_progress_footer,
    stage_status,
)

__all__ = [
    "DataArtifact",
    "EXPERIMENTS_DIR",
    "Experiment",
    "ExperimentRepo",
    "ExperimentStatus",
    "FLEET_INPUT_PATH",
    "FeasibilityReport",
    "FeasibilitySuggestion",
    "FleetSnapshot",
    "GPUInfo",
    "HostInfo",
    "Machine",
    "Version",
    "append_figures_to_version",
    "bump_major",
    "bump_minor",
    "capture_env",
    "check_repo_updates",
    "clone_repo",
    "current_commit_sha",
    "data_index_path",
    "design_version_path",
    "experiment_path",
    "feasibility_path",
    "fleet_input_path",
    "format_semver",
    "infer_fleet_from_versions",
    "latest_design",
    "latest_design_path",
    "latest_feasibility",
    "latest_version",
    "legacy_design_path",
    "list_designs",
    "list_experiments",
    "list_versions",
    "manifest_path",
    "mirror_results",
    "next_available_slug",
    "next_design_version",
    "next_suggested",
    "next_version",
    "parse_data_index",
    "parse_design",
    "parse_experiment",
    "parse_feasibility",
    "parse_fleet",
    "parse_semver",
    "parse_version",
    "references_path",
    "register_version",
    "render_progress_board",
    "render_progress_footer",
    "repo_clone_path",
    "resolve_result_in_repo",
    "result_path",
    "slugify_experiment",
    "stage_status",
    "status_path",
    "to_agentdb_payload",
    "version_path",
]
