"""Git-backed ``/paper sync`` — diff-aware commit + push for a bound direction.

Extracted from :mod:`research_assistant.papers.binding` to keep both files
under the 500-line limit. ``sync`` is the only public entry point; everything
else is a private helper.

Names are re-exported from :mod:`research_assistant.papers.binding` for tests
and external callers that have always accessed them via ``binding.<name>``.

The lazy imports inside :func:`sync` break the otherwise-circular dep with
binding.py (binding.py imports ``sync`` + helpers from this module at load
time; this module needs ``is_bound`` / ``SyncResult`` / the exception classes
that live in binding.py).
"""
from __future__ import annotations

import subprocess
from pathlib import Path

from research_assistant.experiments import repo_clone_path

_GIT_TIMEOUT_S = 15
_GIT_PUSH_TIMEOUT_S = 60

# Auto-commit-message vocabulary
_VERB_RENDER = "render"
_VERB_WRITE = "write"
_VERB_REVISE = "revise"
_VERB_PRUNE = "prune"


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
):
    """git add <paper-paths> + commit + push, paths-scoped.

    Behavior per Q3:
    * Stages only paths under `paper/<v>/<d>/` (Q3d).
    * Fetches first; refuses to push if remote is ahead (Q3b — DivergedError).
    * Auto-generates commit message unless `message` is supplied (Q3c).
    """
    # Lazy imports break the cycle with binding.py. We also reach back into
    # `binding` for helpers like `_ahead_behind` so test monkeypatches on
    # ``binding._ahead_behind`` propagate.
    from . import binding as _b
    from .binding import (
        BindError,
        DivergedError,
        NotBoundError,
        SyncResult,
        is_bound,
    )

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
    ahead, behind = _b._ahead_behind(repo)
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
