"""Shared git primitives for modules that bind to GitHub repos.

`research_assistant.experiments` carries its own historical copies of similar
helpers (predating this module); leave those alone. New consumers
(``mentor.past_work``) route through here so we don't grow more copies.

All helpers shell out to the system ``git`` via ``subprocess.run`` with a fixed
argv (no shell) and a timeout. Network / git errors never raise — they surface
as ``None`` returns or ``{"error": "..."}`` dicts so callers can degrade
gracefully (a flaky network shouldn't crash ``/past-work list``).
"""
from __future__ import annotations

import subprocess
from pathlib import Path

_DEFAULT_TIMEOUT_S = 15
_CLONE_TIMEOUT_S = 120
_PULL_TIMEOUT_S = 60


def guard_under(root: Path, candidate: Path, what: str) -> Path:
    """Raise ``ValueError`` if ``candidate`` resolves outside ``root``."""
    rr = root.resolve()
    cc = candidate.resolve()
    if rr != cc and rr not in cc.parents:
        raise ValueError(f"{what} escapes {root.name}: {candidate}")
    return cc


def _run(cmd: list[str], *, cwd: Path | None = None, timeout: int) -> subprocess.CompletedProcess[str]:
    return subprocess.run(  # noqa: S603 — fixed argv, no shell
        cmd,
        cwd=str(cwd) if cwd is not None else None,
        capture_output=True,
        text=True,
        timeout=timeout,
        check=False,
    )


def git_ls_remote_sha(
    url: str, branch: str = "main", *, timeout: int = _DEFAULT_TIMEOUT_S,
) -> dict:
    """``git ls-remote <url> <branch>`` — never raises.

    Returns ``{"remote_sha": <sha-or-None>, "error": <str-or-None>}``.
    """
    base = {"remote_sha": None, "error": None}
    try:
        out = _run(["git", "ls-remote", url, branch], timeout=timeout)
    except (subprocess.TimeoutExpired, FileNotFoundError, OSError) as e:
        return {**base, "error": f"{type(e).__name__}: {e}"}
    if out.returncode != 0:
        return {**base, "error": out.stderr.strip() or f"git exited {out.returncode}"}
    stdout = out.stdout.strip()
    if not stdout:
        return {**base, "error": f"no ref matching branch={branch!r}"}
    return {**base, "remote_sha": stdout.splitlines()[0].split()[0]}


def git_clone_shallow(
    dest: Path, url: str, branch: str = "main", *, timeout: int = _CLONE_TIMEOUT_S,
) -> Path:
    """``git clone --branch <branch> --depth 1 <url> <dest>``.

    Raises ``FileExistsError`` if ``dest`` already exists, ``RuntimeError`` on
    git failure. Creates ``dest.parent`` as needed.
    """
    if dest.exists():
        raise FileExistsError(f"clone destination already exists: {dest}")
    dest.parent.mkdir(parents=True, exist_ok=True)
    out = _run(
        ["git", "clone", "--branch", branch, "--depth", "1", url, str(dest)],
        timeout=timeout,
    )
    if out.returncode != 0:
        raise RuntimeError(
            f"git clone failed (exit {out.returncode}): {out.stderr.strip()}"
        )
    return dest


def git_pull_ff_only(repo_dir: Path, *, timeout: int = _PULL_TIMEOUT_S) -> tuple[bool, str]:
    """``git -C <repo_dir> pull --ff-only`` — returns ``(ok, message)``."""
    if not repo_dir.is_dir():
        return False, f"not a directory: {repo_dir}"
    try:
        out = _run(["git", "-C", str(repo_dir), "pull", "--ff-only"], timeout=timeout)
    except (subprocess.TimeoutExpired, FileNotFoundError, OSError) as e:
        return False, f"{type(e).__name__}: {e}"
    if out.returncode != 0:
        return False, out.stderr.strip() or f"git exited {out.returncode}"
    return True, out.stdout.strip() or "up to date"


def git_rev_parse_head(repo_dir: Path, *, timeout: int = _DEFAULT_TIMEOUT_S) -> str | None:
    """``git -C <repo_dir> rev-parse HEAD`` — returns SHA or ``None`` on error."""
    if not repo_dir.is_dir():
        return None
    try:
        out = _run(["git", "-C", str(repo_dir), "rev-parse", "HEAD"], timeout=timeout)
    except (subprocess.TimeoutExpired, FileNotFoundError, OSError):
        return None
    if out.returncode != 0:
        return None
    return out.stdout.strip() or None
