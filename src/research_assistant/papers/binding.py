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
import subprocess
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

# Patterns + timeouts (mirror research_assistant.experiments style)
_FM_RE = re.compile(r"^---\r?\n(.*?)\r?\n---\r?\n?(.*)$", re.DOTALL)
_GITIGNORE_LINES: tuple[str, ...] = ("algorithms/*.pdf", "status.md")
_GIT_TIMEOUT_S = 15
_GIT_PUSH_TIMEOUT_S = 60

# Auto-commit-message vocabulary
_VERB_RENDER = "render"
_VERB_WRITE = "write"
_VERB_REVISE = "revise"
_VERB_PRUNE = "prune"


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


# ---------- sync ----------

def _run_git(args: list[str], *, cwd: Path, timeout: int = _GIT_TIMEOUT_S) -> subprocess.CompletedProcess[str]:
    return subprocess.run(  # noqa: S603 — fixed argv, no shell
        ["git", *args],
        cwd=cwd,
        capture_output=True,
        text=True,
        timeout=timeout,
        check=False,
    )


def _git_numstat(repo: Path, paper_rel: str) -> list[tuple[int | None, int | None, str]]:
    """Return [(adds, dels, path), ...] for staged + unstaged + untracked
    inside `paper_rel`.

    `adds` / `dels` are None for binary files (git outputs `-\t-\tpath`) or
    pure-rename pairs we don't bother parsing.
    """
    # Staged + unstaged tracked changes:
    diff = _run_git(["diff", "HEAD", "--numstat", "--", paper_rel], cwd=repo)
    rows: list[tuple[int | None, int | None, str]] = []
    if diff.returncode == 0:
        for line in diff.stdout.splitlines():
            parts = line.split("\t")
            if len(parts) < 3:
                continue
            a = None if parts[0] == "-" else int(parts[0])
            d = None if parts[1] == "-" else int(parts[1])
            rows.append((a, d, parts[2]))
    # Untracked files (treated as full additions):
    ls = _run_git(
        ["ls-files", "--others", "--exclude-standard", "--", paper_rel], cwd=repo
    )
    if ls.returncode == 0:
        for path in ls.stdout.splitlines():
            path = path.strip()
            if not path:
                continue
            full = repo / path
            try:
                # Heuristic: count newlines in the file as "additions". Binary
                # files report 1 line.
                if full.is_file() and full.stat().st_size < 5_000_000:
                    text = full.read_text(encoding="utf-8", errors="replace")
                    rows.append((text.count("\n") + 1, 0, path))
                else:
                    rows.append((None, None, path))
            except OSError:
                rows.append((None, None, path))
    return rows


def _infer_verb(numstat: list[tuple[int | None, int | None, str]]) -> str:
    """Pick a verb based on diff numstat. See plan § "Verb inference"."""
    if not numstat:
        return _VERB_REVISE  # weird; nothing changed
    # render-only: every changed path is `<v>/<d>/main.pdf`
    pdf_only = all(path.endswith("/main.pdf") for _, _, path in numstat)
    if pdf_only:
        return _VERB_RENDER
    total_adds = sum(a or 0 for a, _, _ in numstat)
    total_dels = sum(d or 0 for _, d, _ in numstat)
    if total_adds > 0 and total_dels == 0:
        return _VERB_WRITE
    if total_dels > 0 and total_adds == 0:
        return _VERB_PRUNE
    return _VERB_REVISE


def _auto_commit_message(
    venue: str, direction: str,
    numstat: list[tuple[int | None, int | None, str]],
) -> str:
    """`paper(<v>/<d>): <verb> <file-list-up-to-3>`."""
    verb = _infer_verb(numstat)
    # File names relative to paper/<v>/<d>/ for readability
    prefix = f"paper/{venue}/{direction}/"
    short_names: list[str] = []
    extra = 0
    for _, _, path in numstat:
        rel = path[len(prefix):] if path.startswith(prefix) else path
        if len(short_names) < 3:
            short_names.append(rel)
        else:
            extra += 1
    summary = ", ".join(short_names)
    if extra:
        summary += f" (+{extra} more)"
    return f"paper({venue}/{direction}): {verb} {summary}".rstrip()


def _ahead_behind(repo: Path, branch: str = "HEAD") -> tuple[int, int]:
    """Return `(ahead, behind)` of `<branch>` vs its upstream. (0, 0) if no
    upstream tracked or git errors."""
    out = _run_git(
        ["rev-list", "--left-right", "--count", f"{branch}...@{{upstream}}"],
        cwd=repo,
    )
    if out.returncode != 0:
        return 0, 0
    parts = out.stdout.split()
    if len(parts) != 2:
        return 0, 0
    try:
        return int(parts[0]), int(parts[1])
    except ValueError:
        return 0, 0


def sync(
    *,
    venue: str,
    direction: str,
    message: str | None = None,
) -> SyncResult:
    """git add <paper-paths> + commit + push, paths-scoped.

    Behavior per Q3:
    * Stages only paths under `paper/<v>/<d>/` (Q3d).
    * Fetches first; refuses to push if remote is ahead (Q3b — DivergedError).
    * Auto-generates commit message unless `message` is supplied (Q3c).
    """
    exp_slug = is_bound(venue, direction)
    if exp_slug is None:
        raise NotBoundError(
            f"{venue}/{direction} is not bound to an experiment. "
            "Run `/paper bind <experiment-slug>` first."
        )
    repo = repo_clone_path(exp_slug)
    paper_rel = f"paper/{venue}/{direction}"

    # Diff to figure out what to commit (and to pick a verb).
    numstat = _git_numstat(repo, paper_rel)
    if not numstat:
        return SyncResult(
            committed=False, pushed=False, commit_sha=None,
            commit_message="(no changes)",
            diverged=False, ahead_by=0, behind_by=0,
        )

    commit_msg = message or _auto_commit_message(venue, direction, numstat)

    # Fetch (read-only; never auto-merge).
    _run_git(["fetch"], cwd=repo, timeout=_GIT_PUSH_TIMEOUT_S)
    ahead, behind = _ahead_behind(repo)
    if behind > 0:
        raise DivergedError(
            f"upstream is {behind} commit(s) ahead. "
            "Run `git pull --rebase` inside the experiment repo, then re-run /paper sync."
        )

    # Paths-scoped staging (Q3d).
    add_out = _run_git(["add", "--", paper_rel], cwd=repo)
    if add_out.returncode != 0:
        raise BindError(f"git add failed: {add_out.stderr.strip()}")

    commit_out = _run_git(["commit", "-m", commit_msg], cwd=repo)
    if commit_out.returncode != 0:
        # Could be "nothing to commit" if files were already at HEAD —
        # treat as a no-op commit.
        if "nothing to commit" in commit_out.stdout.lower():
            return SyncResult(
                committed=False, pushed=False, commit_sha=None,
                commit_message="(no changes after staging)",
                diverged=False, ahead_by=ahead, behind_by=behind,
            )
        raise BindError(f"git commit failed: {commit_out.stderr.strip() or commit_out.stdout.strip()}")

    sha_out = _run_git(["rev-parse", "HEAD"], cwd=repo)
    commit_sha = sha_out.stdout.strip() if sha_out.returncode == 0 else None

    push_out = _run_git(["push"], cwd=repo, timeout=_GIT_PUSH_TIMEOUT_S)
    pushed = push_out.returncode == 0

    return SyncResult(
        committed=True,
        pushed=pushed,
        commit_sha=commit_sha,
        commit_message=commit_msg,
        diverged=False,
        ahead_by=ahead + 1 if not pushed else 0,
        behind_by=0,
    )
