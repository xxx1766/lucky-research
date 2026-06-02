"""Walk the repo and classify every file for ``/migrate export``.

The walker produces a :class:`ScanResult` partitioning every encountered file
into one of four buckets:

* ``must`` — files to include in the archive (inputs/, outputs/ minus excluded
  artifacts, DBs, .claude/settings.local.json, .claude-flow/config.yaml).
* ``excluded_registered`` — files matched by some experiment's
  ``external-artifacts.md`` — skipped on export; their re-fetch commands are
  embedded into the archive ``MANIFEST.json`` instead.
* ``excluded_unregistered`` — files larger than the size threshold that live
  inside an experiment with no matching entry. ``/migrate export`` surfaces
  these interactively so the user can register them before archiving;
  ``--non-interactive`` mode fails with this list rather than silently
  including them.
* ``skipped`` — runtime / cache / build / editor noise, plus ``.env*``.

A single :func:`scan_repo` walk reads every experiment's
``external-artifacts.md`` once; subsequent path checks just look up the
pre-computed exclusion set.
"""
from __future__ import annotations

import fnmatch
from dataclasses import dataclass, field
from pathlib import Path

from research_assistant.common.io import EXPERIMENTS_DIR, INPUTS_DIR, OUTPUTS_DIR, REPO_ROOT
from research_assistant.migrate.manifest import (
    ArtifactRecord,
    ExcludedArtifact,
    external_artifacts_path,
    read_external_artifacts,
)

# Files larger than this in an experiment dir, with no manifest entry, trigger
# the interactive "is this externally fetchable?" prompt at export time.
DEFAULT_UNREGISTERED_THRESHOLD = 1 * 1024 * 1024 * 1024  # 1 GB

# Skip-list components. Order: directory names that always shortcut the walk,
# file basenames that are never included, glob patterns for ``.something``-style
# noise we should never traverse into.
_SKIP_DIR_NAMES = frozenset({
    "__pycache__",
    ".venv",
    "venv",
    ".pytest_cache",
    ".ruff_cache",
    ".mypy_cache",
    ".tox",
    "build",
    "dist",
    ".vscode",
    ".idea",
    ".git",  # we never archive a checked-out git dir wholesale; bound experiment
             # repos can be re-cloned via /experiment clone.
    "node_modules",
    "htmlcov",
})

_SKIP_FILE_BASENAMES = frozenset({
    ".DS_Store",
    ".coverage",
})

_SKIP_FILE_SUFFIXES = (".pyc", ".pyo", ".swp")

# .env / .env.local / .env.production etc. — never archive (project security rule).
_ENV_FILE_PATTERN = ".env*"

# Subpaths of .claude-flow/ that are intentionally NOT migrated (logs / sessions
# / metrics / runtime state). The remainder (chiefly config.yaml) goes in.
_CLAUDE_FLOW_SKIP_DIRS = frozenset({
    "logs", "sessions", "metrics", "data", "learning", "security",
})
_CLAUDE_FLOW_SKIP_FILES = frozenset({"daemon.pid"})

# DB files (and their WAL sidecars) — exported / merged specially.
DB_FILE_NAMES = frozenset({
    "ruvector.db",
    "ruvector.db-shm",
    "ruvector.db-wal",
})

SWARM_DB_REL = "memory.db"  # under .swarm/

# DB sidecar suffixes — dropped from the archive (they are WAL state, not
# portable; SQLite recreates them on open after a checkpoint).
DB_SIDECAR_SUFFIXES = ("-shm", "-wal")


@dataclass(frozen=True)
class FileItem:
    """One file the walk encountered, with its repo-relative path and size."""

    abs_path: Path
    rel_path: str  # POSIX style, relative to REPO_ROOT
    size: int


@dataclass(frozen=True)
class UnregisteredItem:
    """A >threshold file inside an experiment with no matching artifact record."""

    abs_path: Path
    rel_path: str
    size: int
    experiment_slug: str
    in_experiment_rel: str  # path relative to the experiment dir


@dataclass(frozen=True)
class RegisteredMatch:
    """A file matched by some experiment's ``external-artifacts.md`` entry."""

    abs_path: Path
    rel_path: str
    size: int
    experiment_slug: str
    record: ArtifactRecord


@dataclass
class ScanResult:
    must: list[FileItem] = field(default_factory=list)
    excluded_registered: list[RegisteredMatch] = field(default_factory=list)
    excluded_unregistered: list[UnregisteredItem] = field(default_factory=list)
    skipped: list[FileItem] = field(default_factory=list)
    # Per-experiment record set, indexed by slug. Used to build the
    # ``excluded_artifacts`` list in the archive MANIFEST.json without re-reading
    # the manifest files later.
    artifacts_by_experiment: dict[str, list[ArtifactRecord]] = field(default_factory=dict)

    def excluded_artifacts(self) -> list[ExcludedArtifact]:
        """Flatten ``artifacts_by_experiment`` for archive ``MANIFEST.json``.

        Every registered artifact record becomes one :class:`ExcludedArtifact`
        with its ``dest_path`` resolved to repo-relative form (so import on a
        new machine knows exactly where to drop re-fetched files).
        """
        out: list[ExcludedArtifact] = []
        for slug, records in self.artifacts_by_experiment.items():
            for r in records:
                dest = f"outputs/experiments/{slug}/{r.path}"
                out.append(ExcludedArtifact(
                    experiment=slug,
                    name=r.name,
                    dest_path=dest,
                    glob=r.glob,
                    type=r.type,
                    repo=r.repo,
                    revision=r.revision,
                    size_estimate=r.size_estimate,
                    fetch_cmd=r.fetch_cmd,
                ))
        return out


# ---------- helpers ----------

def _rel(p: Path, root: Path) -> str:
    """POSIX-style path of ``p`` relative to ``root``."""
    return p.relative_to(root).as_posix()


def _is_env_file(name: str) -> bool:
    return fnmatch.fnmatch(name, _ENV_FILE_PATTERN)


def _should_skip_dir(name: str) -> bool:
    """Whether to prune the walk at this directory leaf name.

    Path-aware skips (``.claude-flow/logs``) are handled in the dedicated
    ``.claude-flow`` walker, not here.
    """
    return name in _SKIP_DIR_NAMES


def _load_artifacts_for_experiment(slug: str) -> list[ArtifactRecord]:
    """Read ``external-artifacts.md`` for an experiment, empty list if absent.

    Lets a malformed file raise (so the user sees the config error at scan time
    rather than silently archiving 80GB of base-model shards).
    """
    path = external_artifacts_path(slug)
    return read_external_artifacts(path).artifacts


def _list_experiment_slugs() -> list[str]:
    if not EXPERIMENTS_DIR.is_dir():
        return []
    return sorted(
        c.name for c in EXPERIMENTS_DIR.iterdir()
        if c.is_dir() and not c.name.startswith("_") and not c.name.startswith(".")
    )


def _match_artifact(
    in_experiment_rel: str, records: list[ArtifactRecord]
) -> ArtifactRecord | None:
    """Return the first record whose ``path/glob`` matches the experiment-relative path."""
    for r in records:
        base = r.path
        if not (in_experiment_rel == base or in_experiment_rel.startswith(base + "/")):
            continue
        # Match the glob against the file basename, the path under ``base``, OR
        # the full experiment-relative path — gives the user maximum flexibility
        # in how they write the glob.
        rel_under_base = in_experiment_rel[len(base) + 1:] if in_experiment_rel != base else ""
        basename = Path(in_experiment_rel).name
        for candidate in (basename, rel_under_base, in_experiment_rel):
            if fnmatch.fnmatch(candidate, r.glob):
                return r
        # Default glob `*` is forgiving — any file under the path matches.
        if r.glob == "*":
            return r
    return None


def _experiment_for_path(rel_posix: str) -> tuple[str, str] | None:
    """If ``rel_posix`` lies inside ``outputs/experiments/<slug>/``, return
    ``(slug, path-relative-to-experiment-dir)``; else ``None``.

    ``_`` / ``.``-prefixed slugs (the registry + scratch dirs) are skipped.
    """
    prefix = "outputs/experiments/"
    if not rel_posix.startswith(prefix):
        return None
    rest = rel_posix[len(prefix):]
    if "/" not in rest:
        return None  # a file directly under experiments/, not inside an experiment
    slug, _, in_exp = rest.partition("/")
    if not slug or slug.startswith("_") or slug.startswith("."):
        return None
    return slug, in_exp


# ---------- main entry ----------

def scan_repo(
    repo_root: Path | None = None,
    *,
    unregistered_threshold: int = DEFAULT_UNREGISTERED_THRESHOLD,
    include_inputs: bool = True,
    include_outputs: bool = True,
    include_dbs: bool = True,
    include_claude_config: bool = True,
) -> ScanResult:
    """Walk the repo, classify every encountered file. Pure — no side effects."""
    root = (repo_root or REPO_ROOT).resolve()
    result = ScanResult()

    # Pre-load every experiment's artifacts once.
    slugs = _list_experiment_slugs() if include_outputs else []
    for slug in slugs:
        try:
            records = _load_artifacts_for_experiment(slug)
        except ValueError:
            # Malformed external-artifacts.md — surface as a scan failure to
            # the caller; export should refuse to run with a bad manifest.
            raise
        result.artifacts_by_experiment[slug] = records

    # ---- inputs/ ----
    if include_inputs and INPUTS_DIR.exists():
        _walk_simple_tree(INPUTS_DIR, root, result)

    # ---- outputs/ (per-experiment classification baked in) ----
    if include_outputs and OUTPUTS_DIR.exists():
        for dirpath, dirnames, filenames in _walked(OUTPUTS_DIR):
            dirnames[:] = [d for d in dirnames if not _should_skip_dir(d)]
            for fname in filenames:
                fpath = dirpath / fname
                if not fpath.is_file():
                    continue
                rel = _rel(fpath, root)
                if _is_env_file(fname) or fname in _SKIP_FILE_BASENAMES or fname.endswith(_SKIP_FILE_SUFFIXES):
                    result.skipped.append(_file_item(fpath, rel))
                    continue
                size = _safe_size(fpath)
                exp = _experiment_for_path(rel)
                if exp:
                    slug, in_exp = exp
                    records = result.artifacts_by_experiment.get(slug, [])
                    match = _match_artifact(in_exp, records)
                    if match:
                        result.excluded_registered.append(
                            RegisteredMatch(fpath, rel, size, slug, match)
                        )
                        continue
                    if size >= unregistered_threshold:
                        result.excluded_unregistered.append(
                            UnregisteredItem(fpath, rel, size, slug, in_exp)
                        )
                        continue
                result.must.append(FileItem(fpath, rel, size))

    # ---- ruvector.db family ----
    if include_dbs:
        for name in DB_FILE_NAMES:
            p = root / name
            if p.is_file():
                result.must.append(_file_item(p, name))
        # .swarm/memory.db family
        swarm_dir = root / ".swarm"
        if swarm_dir.is_dir():
            for child in swarm_dir.iterdir():
                if child.is_file() and (child.name == SWARM_DB_REL or any(
                    child.name == f"{SWARM_DB_REL}{suf}" for suf in DB_SIDECAR_SUFFIXES
                )):
                    result.must.append(_file_item(child, f".swarm/{child.name}"))

    # ---- .claude / .claude-flow ----
    if include_claude_config:
        local_settings = root / ".claude" / "settings.local.json"
        if local_settings.is_file():
            result.must.append(_file_item(local_settings, ".claude/settings.local.json"))
        cf_root = root / ".claude-flow"
        if cf_root.is_dir():
            for child in cf_root.iterdir():
                if child.is_dir():
                    if child.name in _CLAUDE_FLOW_SKIP_DIRS:
                        continue
                    # Walk any non-skipped subdir of .claude-flow (defensively
                    # include anything novel — better to archive than to lose
                    # config the user added later).
                    for sub_dir, sub_subs, sub_files in _walked(child):
                        sub_subs[:] = [d for d in sub_subs if d not in _CLAUDE_FLOW_SKIP_DIRS]
                        for fn in sub_files:
                            p = sub_dir / fn
                            if not p.is_file():
                                continue
                            if fn in _CLAUDE_FLOW_SKIP_FILES or _is_env_file(fn):
                                result.skipped.append(_file_item(p, _rel(p, root)))
                                continue
                            result.must.append(_file_item(p, _rel(p, root)))
                elif child.is_file():
                    if child.name in _CLAUDE_FLOW_SKIP_FILES or _is_env_file(child.name):
                        result.skipped.append(_file_item(child, _rel(child, root)))
                        continue
                    result.must.append(_file_item(child, _rel(child, root)))

    return result


def _walked(top: Path):
    """``os.walk`` over a Path, yielding ``(Path, list[dirnames], list[filenames])``.

    Wrapped so callers can mutate ``dirnames`` to prune the walk the standard
    ``os.walk`` way without importing ``os`` everywhere.
    """
    import os
    for dirpath, dirnames, filenames in os.walk(top):
        yield Path(dirpath), dirnames, filenames


def _walk_simple_tree(top: Path, root: Path, result: ScanResult) -> None:
    """Catch-all walker for inputs/ — everything goes to ``must`` unless
    matched by the skip rules. No experiment-aware classification."""
    for dirpath, dirnames, filenames in _walked(top):
        dirnames[:] = [d for d in dirnames if not _should_skip_dir(d)]
        for fname in filenames:
            fpath = dirpath / fname
            if not fpath.is_file():
                continue
            rel = _rel(fpath, root)
            if _is_env_file(fname) or fname in _SKIP_FILE_BASENAMES or fname.endswith(_SKIP_FILE_SUFFIXES):
                result.skipped.append(_file_item(fpath, rel))
                continue
            result.must.append(_file_item(fpath, rel))


def _file_item(fpath: Path, rel: str, *, size: int | None = None) -> FileItem:
    return FileItem(fpath, rel, size if size is not None else _safe_size(fpath))


from research_assistant.common.io import safe_size as _safe_size  # noqa: E402, F401
