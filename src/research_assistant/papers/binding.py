"""Bind / unbind / restore / sync helpers for `/paper`.

Storage model (see the approved plan):

* The experiment repo (cloned at `outputs/experiments/<slug>/repo/`) is the
  source of truth for paper artifacts. Inside it papers live at
  `<exp-repo>/paper/<venue>/<direction>/`.
* Local authoring still happens at `outputs/papers/<venue>/<direction>/` —
  that path is a **symlink** into the experiment repo so the existing
  /paper / /figure / /pseudocode write paths remain unchanged.
* Venue-level files (`_venue.md`, `_template/`) are **copied** (not
  symlinked) from the experiment repo into `outputs/papers/<venue>/` on
  bind — avoids the "which experiment owns the venue?" ambiguity.

Mirrors conventions from `research_assistant.experiments`:
* `_guard_under` for path-traversal protection
* `subprocess.run(check=False, timeout=...)` for git invocations
* timeouts via module-level constants
"""
from __future__ import annotations

import re
import shutil
from dataclasses import dataclass
from pathlib import Path

import yaml

from research_assistant.common.io import EXPERIMENTS_DIR
from research_assistant.experiments import repo_clone_path
from research_assistant.papers import direction_path, venue_path

__all__ = [
    "AlreadyBoundError",
    "BindError",
    "BindingResult",
    "ConflictError",
    "DivergedError",
    "NotBoundError",
    "SyncResult",
    "bind",
    "is_bound",
    "read_binding_from_expert_md",
    "restore",
    "sync",
    "unbind",
]

# Patterns + per-direction gitignore lines
_FM_RE = re.compile(r"^---\r?\n(.*?)\r?\n---\r?\n?(.*)$", re.DOTALL)
_GITIGNORE_LINES: tuple[str, ...] = ("algorithms/*.pdf", "status.md")

# Sync helpers (verb constants, git wrappers, sync() itself) live in `_sync.py`
# to keep this file under the 500-line limit. Re-exported here so callers can
# keep using ``binding.sync`` / ``binding._infer_verb`` / ``binding._VERB_*``
# unchanged.
from research_assistant.papers._sync import (  # noqa: E402, F401
    _GIT_PUSH_TIMEOUT_S,
    _GIT_TIMEOUT_S,
    _VERB_PRUNE,
    _VERB_RENDER,
    _VERB_REVISE,
    _VERB_WRITE,
    _ahead_behind,
    _auto_commit_message,
    _git_numstat,
    _infer_verb,
    _run_git,
    sync,
)


# ---------- exceptions ----------

class BindError(RuntimeError):
    """Base class for /paper bind errors."""


class AlreadyBoundError(BindError):
    """outputs/papers/<v>/<d>/ is already a symlink to a different experiment."""


class ConflictError(BindError):
    """<exp-repo>/paper/<v>/<d>/ is already populated."""


class NotBoundError(BindError):
    """unbind / sync called on a path that is NOT a symlink into an experiment repo."""


class DivergedError(BindError):
    """sync refused because the remote is ahead — user must `git pull --rebase`."""


# ---------- dataclasses ----------

@dataclass(frozen=True)
class BindingResult:
    venue: str
    direction: str
    experiment_slug: str
    exp_repo_path: Path           # outputs/experiments/<slug>/repo
    paper_dir: Path               # <exp-repo>/paper/<v>/<d>
    symlink_path: Path            # outputs/papers/<v>/<d>
    venue_files_copied: list[str] # ["_venue.md", "_template"]
    migrated_bytes: int


@dataclass(frozen=True)
class SyncResult:
    committed: bool
    pushed: bool
    commit_sha: str | None
    commit_message: str
    diverged: bool
    ahead_by: int
    behind_by: int


# ---------- path helpers ----------

def _guard_under(root: Path, candidate: Path, what: str) -> Path:
    """Raise ``ValueError`` if ``candidate`` resolves outside ``root``."""
    rr = root.resolve()
    cc = candidate.resolve()
    if rr != cc and rr not in cc.parents:
        raise ValueError(f"{what} escapes {root.name}: {candidate}")
    return cc


def _paper_dir_in_repo(exp_slug: str, venue: str, direction: str) -> Path:
    """Resolve the canonical paper location INSIDE the experiment repo clone."""
    repo = repo_clone_path(exp_slug)
    base = repo / "paper" / venue / direction
    return _guard_under(repo, base, "paper dir")


def _venue_dir_in_repo(exp_slug: str, venue: str) -> Path:
    repo = repo_clone_path(exp_slug)
    base = repo / "paper" / venue
    return _guard_under(repo, base, "paper venue dir")


def _local_symlink_target(symlink_path: Path) -> Path | None:
    """If `symlink_path` is a symlink, return its absolute target. Else None.

    Tolerates both relative and absolute symlink targets.
    """
    if not symlink_path.is_symlink():
        return None
    raw = Path(__import__("os").readlink(symlink_path))
    if raw.is_absolute():
        return raw
    return (symlink_path.parent / raw).resolve()


def _bytes_in_tree(p: Path) -> int:
    if not p.exists():
        return 0
    if p.is_file():
        return p.stat().st_size
    total = 0
    for child in p.rglob("*"):
        if child.is_file():
            try:
                total += child.stat().st_size
            except OSError:
                pass
    return total


# ---------- expert.md frontmatter ----------

def _read_frontmatter(path: Path) -> tuple[dict, str]:
    """Read a markdown file and return (frontmatter_dict, body). Empty frontmatter
    if no YAML block."""
    if not path.is_file():
        return {}, ""
    text = path.read_text(encoding="utf-8")
    m = _FM_RE.match(text)
    if not m:
        return {}, text
    fm = yaml.safe_load(m.group(1)) or {}
    return fm, m.group(2)


def _write_frontmatter(path: Path, fm: dict, body: str) -> None:
    yaml_text = yaml.safe_dump(fm, sort_keys=False, allow_unicode=True).rstrip("\n")
    leading = "" if body.startswith("\n") else "\n"
    path.write_text(f"---\n{yaml_text}\n---{leading}{body}", encoding="utf-8")


def read_binding_from_expert_md(venue: str, direction: str) -> str | None:
    """Return the bound primary `experiment:` slug from expert.md, or None.

    Looks at the canonical authoring path (`outputs/papers/<v>/<d>/expert.md`),
    which transparently follows the symlink into the experiment repo when bound.
    """
    expert = direction_path(venue, direction) / "expert.md"
    if not expert.is_file():
        return None
    fm, _ = _read_frontmatter(expert)
    val = fm.get("experiment")
    return val if isinstance(val, str) and val else None


def read_all_bindings_from_expert_md(venue: str, direction: str) -> list[str]:
    """Return every experiment slug bound to this direction, dedup'd.

    Unions the singular ``experiment:`` field with the optional plural
    ``experiments:`` list (set by ``/paper bind --additional`` and the
    paper-architect Stage 0 binding prompt). Order: primary first, then
    additionals in their original order; duplicates collapsed.

    Returns ``[]`` if expert.md is missing or has no bindings.
    """
    expert = direction_path(venue, direction) / "expert.md"
    if not expert.is_file():
        return []
    fm, _ = _read_frontmatter(expert)
    out: list[str] = []
    seen: set[str] = set()
    primary = fm.get("experiment")
    if isinstance(primary, str) and primary:
        out.append(primary)
        seen.add(primary)
    additional = fm.get("experiments")
    if isinstance(additional, list):
        for slug in additional:
            if isinstance(slug, str) and slug and slug not in seen:
                out.append(slug)
                seen.add(slug)
    return out


def _set_expert_md_binding(
    expert_path: Path, *, primary: str, additional: list[str] | None = None,
) -> None:
    fm, body = _read_frontmatter(expert_path)
    fm["experiment"] = primary
    if additional:
        fm["experiments"] = list(dict.fromkeys(additional))  # dedupe, preserve order
    expert_path.parent.mkdir(parents=True, exist_ok=True)
    _write_frontmatter(expert_path, fm, body)


# ---------- bind ----------

def bind(
    *,
    venue: str,
    direction: str,
    experiment_slug: str,
    force: bool = False,
) -> BindingResult:
    """Move outputs/papers/<v>/<d>/ into the experiment repo; symlink back.

    Idempotent if called twice with the same `(venue, direction, experiment_slug)`.
    """
    repo = repo_clone_path(experiment_slug)
    if not repo.is_dir():
        raise BindError(
            f"experiment {experiment_slug!r} is not cloned at {repo}. "
            "Run /experiment init (or clone the bound GitHub repo) first."
        )

    src = direction_path(venue, direction)
    dest = _paper_dir_in_repo(experiment_slug, venue, direction)

    # Idempotency: already a symlink to the right place?
    existing_target = _local_symlink_target(src)
    if existing_target is not None:
        if existing_target.resolve() == dest.resolve():
            # Already bound to this experiment — re-run is a no-op (still
            # refresh venue-file copies + .gitignore so they reflect any drift).
            venue_files = _copy_venue_files(experiment_slug, venue, overwrite=False)
            _ensure_direction_gitignore(dest)
            return BindingResult(
                venue=venue,
                direction=direction,
                experiment_slug=experiment_slug,
                exp_repo_path=repo,
                paper_dir=dest,
                symlink_path=src,
                venue_files_copied=venue_files,
                migrated_bytes=0,
            )
        if not force:
            raise AlreadyBoundError(
                f"{src} is already a symlink to {existing_target}; "
                "run /paper unbind first or pass force=True"
            )
        # force: drop the old symlink to fall through to the migration path.
        src.unlink()

    if dest.exists() and any(dest.iterdir()) and not force:
        raise ConflictError(
            f"{dest} is already populated. Pass force=True to overwrite, "
            "or pick a different (venue, direction)."
        )

    migrated_bytes = 0
    if src.exists() and not src.is_symlink():
        # Move the local-authored content into the experiment repo.
        migrated_bytes = _bytes_in_tree(src)
        dest.parent.mkdir(parents=True, exist_ok=True)
        if dest.exists():
            shutil.rmtree(dest)
        shutil.move(str(src), str(dest))
    else:
        # No local content — create an empty paper dir inside the experiment repo
        # so the symlink resolves to something real.
        dest.mkdir(parents=True, exist_ok=True)

    # Symlink local path → experiment repo
    src.parent.mkdir(parents=True, exist_ok=True)
    src.symlink_to(dest, target_is_directory=True)

    venue_files = _copy_venue_files(experiment_slug, venue, overwrite=False)
    _ensure_direction_gitignore(dest)
    _set_expert_md_binding(dest / "expert.md", primary=experiment_slug)

    return BindingResult(
        venue=venue,
        direction=direction,
        experiment_slug=experiment_slug,
        exp_repo_path=repo,
        paper_dir=dest,
        symlink_path=src,
        venue_files_copied=venue_files,
        migrated_bytes=migrated_bytes,
    )


def _copy_venue_files(
    experiment_slug: str, venue: str, *, overwrite: bool = False,
) -> list[str]:
    """Copy `_venue.md` + `_template/` from `<exp-repo>/paper/<venue>/` into
    `outputs/papers/<venue>/`. Returns the list of names that were copied.

    Per Q2c (C-2): venue-level files are real files locally, NOT symlinks.
    Copy direction is repo → local because the experiment-repo copies are the
    durable source.
    """
    src_venue = _venue_dir_in_repo(experiment_slug, venue)
    dst_venue = venue_path(venue)
    dst_venue.mkdir(parents=True, exist_ok=True)
    copied: list[str] = []
    for name in ("_venue.md", "_template", "_venue-refs"):
        src = src_venue / name
        if not src.exists():
            continue
        dst = dst_venue / name
        if dst.exists() and not overwrite:
            continue
        if src.is_dir():
            if dst.exists():
                shutil.rmtree(dst)
            shutil.copytree(src, dst)
        else:
            shutil.copy2(src, dst)
        copied.append(name)
    return copied


def _ensure_direction_gitignore(paper_dir: Path) -> None:
    """Write a minimal `.gitignore` for build artifacts (idempotent)."""
    gi = paper_dir / ".gitignore"
    if gi.exists():
        existing = gi.read_text(encoding="utf-8").splitlines()
        missing = [line for line in _GITIGNORE_LINES if line not in existing]
        if not missing:
            return
        out = existing + missing
    else:
        out = list(_GITIGNORE_LINES)
    paper_dir.mkdir(parents=True, exist_ok=True)
    gi.write_text("\n".join(out) + "\n", encoding="utf-8")


# ---------- unbind ----------

def unbind(*, venue: str, direction: str, keep_files: bool = False) -> None:
    """Remove the symlink at `outputs/papers/<v>/<d>/`.

    If `keep_files=True`, copy the experiment repo's contents back into a real
    directory at the symlink path before removing the link.
    """
    src = direction_path(venue, direction)
    target = _local_symlink_target(src)
    if target is None:
        raise NotBoundError(f"{src} is not a symlink; nothing to unbind.")

    src.unlink()
    if keep_files and target.is_dir():
        src.parent.mkdir(parents=True, exist_ok=True)
        shutil.copytree(target, src)


# ---------- is_bound ----------

def is_bound(venue: str, direction: str) -> str | None:
    """Return the bound experiment slug if `<v>/<d>` is a symlink into an
    experiment repo's `paper/` tree, else None.

    Symlink convention: `<exp-root>/repo/paper/<v>/<d>/` →
    experiment slug is the segment between `<EXPERIMENTS_DIR>/` and `/repo/`.
    """
    src = direction_path(venue, direction)
    target = _local_symlink_target(src)
    if target is None:
        return None
    try:
        rel = target.resolve().relative_to(EXPERIMENTS_DIR.resolve())
    except (ValueError, OSError):
        return None
    parts = rel.parts
    # Expected: <slug>/repo/paper/<venue>/<direction>
    if len(parts) < 5 or parts[1] != "repo" or parts[2] != "paper":
        return None
    if parts[3] != venue or parts[4] != direction:
        return None
    return parts[0]


# ---------- restore ----------

def restore(
    *,
    venue: str | None = None,
    direction: str | None = None,
    all_papers: bool = False,
) -> list[BindingResult]:
    """Walk `outputs/experiments/*/repo/paper/*/*/` and (re)create symlinks at
    `outputs/papers/<v>/<d>/`. Also copies venue files.

    `all_papers=True` restores every paper found across all experiments. A
    specific `(venue, direction)` restores just that one — walks experiments
    looking for a `paper/<venue>/<direction>/` match.
    """
    if not all_papers and (venue is None or direction is None):
        raise ValueError("either all_papers=True OR (venue and direction) required")

    out: list[BindingResult] = []
    if not EXPERIMENTS_DIR.is_dir():
        return out

    for exp_dir in sorted(EXPERIMENTS_DIR.iterdir()):
        if not exp_dir.is_dir() or exp_dir.name.startswith("_"):
            continue
        paper_root = exp_dir / "repo" / "paper"
        if not paper_root.is_dir():
            continue
        for venue_dir in sorted(paper_root.iterdir()):
            if not venue_dir.is_dir() or venue_dir.name.startswith("_"):
                continue
            v_name = venue_dir.name
            for direction_dir in sorted(venue_dir.iterdir()):
                if not direction_dir.is_dir() or direction_dir.name.startswith("_"):
                    continue
                d_name = direction_dir.name
                if not all_papers and (v_name != venue or d_name != direction):
                    continue
                exp_slug = exp_dir.name
                local = direction_path(v_name, d_name)
                # Skip if already correctly symlinked to this experiment.
                existing = _local_symlink_target(local)
                if existing is not None and existing.resolve() == direction_dir.resolve():
                    out.append(BindingResult(
                        venue=v_name,
                        direction=d_name,
                        experiment_slug=exp_slug,
                        exp_repo_path=exp_dir / "repo",
                        paper_dir=direction_dir,
                        symlink_path=local,
                        venue_files_copied=_copy_venue_files(exp_slug, v_name, overwrite=False),
                        migrated_bytes=0,
                    ))
                    continue
                # Skip if local path is a real directory with content — refuse
                # to clobber the user's authoring.
                if local.exists() and not local.is_symlink():
                    continue
                if local.is_symlink():
                    local.unlink()
                local.parent.mkdir(parents=True, exist_ok=True)
                local.symlink_to(direction_dir, target_is_directory=True)
                venue_files = _copy_venue_files(exp_slug, v_name, overwrite=False)
                _ensure_direction_gitignore(direction_dir)
                out.append(BindingResult(
                    venue=v_name,
                    direction=d_name,
                    experiment_slug=exp_slug,
                    exp_repo_path=exp_dir / "repo",
                    paper_dir=direction_dir,
                    symlink_path=local,
                    venue_files_copied=venue_files,
                    migrated_bytes=0,
                ))
    return out


# `sync` + git helpers are imported above from `_sync.py`.
