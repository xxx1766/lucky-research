"""Git / filesystem operations against the experiment's bound repo.

All git invocations are time-bounded; network failures return error sentinels
rather than raising so ``/experiment status`` survives a flaky connection.
``mirror_results`` reads ``_LARGE_RESULT_BYTES`` from the parent package so
tests can monkeypatch it via ``experiments._LARGE_RESULT_BYTES``.
"""
from __future__ import annotations

import os
import shutil
import subprocess
from pathlib import Path

import research_assistant.experiments as _exp  # late attribute access for _LARGE_RESULT_BYTES

from .paths import _guard_under, repo_clone_path, result_path

_GIT_TIMEOUT_S = 15
_CLONE_TIMEOUT_S = 120
_SSH_PREFLIGHT_TIMEOUT_S = 2


def _is_ssh_url(url: str) -> bool:
    """True when ``url`` is an SSH-style git remote.

    Matches ``git@host:org/repo.git`` and ``ssh://...`` forms — both need a
    working ssh-agent for non-interactive ``git ls-remote``.
    """
    return url.startswith(("git@", "ssh://"))


def _preflight_ssh(url: str) -> str | None:
    """Return an actionable error message when ssh-agent isn't usable.

    ``None`` means "OK, proceed to git". Without this pre-flight, calling
    ``git ls-remote`` against an SSH URL when no agent is loaded blocks until
    ``_GIT_TIMEOUT_S`` then returns a generic ``TimeoutExpired`` — the user
    sees "network timeout" when the real fix is ``ssh-add ~/.ssh/id_rsa``.

    Heuristics intentionally conservative: when ``ssh-add`` isn't on PATH or
    reports an unfamiliar exit code, we return ``None`` and let git try
    (catches edge cases like non-default key paths configured in ``~/.ssh/config``
    that don't show up in ``ssh-add -l``).
    """
    if not _is_ssh_url(url):
        return None
    sock = os.environ.get("SSH_AUTH_SOCK", "")
    if not sock:
        return (
            "SSH_AUTH_SOCK is not set; SSH-cloned remotes need an ssh-agent. "
            "Run: eval $(ssh-agent) && ssh-add ~/.ssh/id_rsa"
        )
    try:
        out = subprocess.run(  # noqa: S603 — no shell, fixed argv
            ["ssh-add", "-l"],
            capture_output=True, text=True,
            timeout=_SSH_PREFLIGHT_TIMEOUT_S, check=False,
        )
    except (subprocess.TimeoutExpired, FileNotFoundError, OSError):
        return None
    if out.returncode == 1:
        return (
            "ssh-agent is running but has no keys loaded. "
            "Run: ssh-add ~/.ssh/id_rsa"
        )
    if out.returncode == 2:
        # `ssh-add -l` returns 2 when SSH_AUTH_SOCK is set but the agent
        # the socket points at isn't reachable (stopped / replaced / stale
        # tmux session). Without this branch the user gets a generic git
        # network timeout 15s later.
        return (
            "ssh-agent socket is set (SSH_AUTH_SOCK) but the agent isn't "
            "reachable. Run: eval $(ssh-agent) && ssh-add ~/.ssh/id_rsa"
        )
    return None


def _git_env() -> dict[str, str]:
    """Subprocess env where git is non-interactive for HTTPS credential prompts.

    Without ``GIT_TERMINAL_PROMPT=0``, an HTTPS URL whose credentials aren't
    cached can hang waiting for a username on stdin, exhausting the 15s
    timeout. Setting it forces git to fail fast with a clear
    "could not read Username" stderr message.
    """
    return {**os.environ, "GIT_TERMINAL_PROMPT": "0"}


def check_repo_updates(
    url: str, branch: str = "main", local_sha: str | None = None
) -> dict:
    """Run ``git ls-remote <url> <branch>`` and compare to ``local_sha``.

    Returns a dict with keys ``remote_sha``, ``local_sha``, ``drift``, ``ahead``,
    ``error``. **Never raises** — git / network failures surface as
    ``error`` populated and the other fields nulled, so ``/experiment status``
    can survive a flaky network.
    """
    base = {
        "remote_sha": None,
        "local_sha": local_sha,
        "drift": None,
        "ahead": None,
        "error": None,
    }
    preflight_error = _preflight_ssh(url)
    if preflight_error:
        return {**base, "error": preflight_error}
    try:
        out = subprocess.run(  # noqa: S603 — no shell, fixed argv
            ["git", "ls-remote", url, branch],
            capture_output=True, text=True,
            timeout=_GIT_TIMEOUT_S, check=False, env=_git_env(),
        )
    except (subprocess.TimeoutExpired, FileNotFoundError, OSError) as e:
        return {**base, "error": f"{type(e).__name__}: {e}"}
    if out.returncode != 0:
        return {**base, "error": out.stderr.strip() or f"git exited {out.returncode}"}
    stdout = out.stdout.strip()
    if not stdout:
        return {**base, "error": f"no ref matching branch={branch!r}"}
    remote_sha = stdout.splitlines()[0].split()[0]
    drift = (remote_sha != local_sha) if local_sha else None
    return {**base, "remote_sha": remote_sha, "drift": drift}


def current_commit_sha(slug: str) -> str | None:
    """Return ``git rev-parse HEAD`` for the local clone, or ``None``."""
    repo = repo_clone_path(slug)
    if not repo.is_dir():
        return None
    try:
        out = subprocess.run(  # noqa: S603 — no shell, fixed argv
            ["git", "-C", str(repo), "rev-parse", "HEAD"],
            capture_output=True, text=True,
            timeout=_GIT_TIMEOUT_S, check=False,
        )
    except (subprocess.TimeoutExpired, FileNotFoundError, OSError):
        return None
    if out.returncode != 0:
        return None
    return out.stdout.strip() or None


def clone_repo(slug: str, url: str, branch: str = "main") -> Path:
    """``git clone --branch <branch> --depth 1 <url>`` into the experiment dir.

    Raises ``FileExistsError`` if the destination already exists, ``RuntimeError``
    on a non-zero ``git clone`` exit.
    """
    dest = repo_clone_path(slug)
    if dest.exists():
        raise FileExistsError(f"clone destination already exists: {dest}")
    dest.parent.mkdir(parents=True, exist_ok=True)
    out = subprocess.run(  # noqa: S603 — no shell, fixed argv
        ["git", "clone", "--branch", branch, "--depth", "1", url, str(dest)],
        capture_output=True, text=True,
        timeout=_CLONE_TIMEOUT_S, check=False,
    )
    if out.returncode != 0:
        raise RuntimeError(
            f"git clone failed (exit {out.returncode}): {out.stderr.strip()}"
        )
    return dest


def mirror_results(
    slug: str,
    version: str,
    src: Path,
    *,
    boundary_root: Path | None = None,
    force: bool = False,
) -> Path:
    """Copy a result file or directory from the bound repo into local storage.

    Refuses to overwrite a non-empty destination unless ``force=True``. Warns
    on files over 100 MB (raises ``ValueError`` unless ``force=True``). If
    ``boundary_root`` is given, ``src`` must resolve inside it.
    """
    src = Path(src)
    if boundary_root is not None:
        _guard_under(boundary_root, src, "mirror source")
    if not src.exists():
        raise FileNotFoundError(f"mirror source does not exist: {src}")
    dest_dir = result_path(slug, version)
    dest_dir.mkdir(parents=True, exist_ok=True)
    if src.is_file():
        size = src.stat().st_size
        if size > _exp._LARGE_RESULT_BYTES and not force:
            raise ValueError(
                f"result file is {size / 1024 / 1024:.1f} MB (> 100 MB); "
                "pass force=True to mirror anyway"
            )
        dest_file = dest_dir / src.name
        if dest_file.exists() and not force:
            raise FileExistsError(f"mirror destination exists: {dest_file}")
        shutil.copy2(src, dest_file)
        return dest_file
    if src.is_dir():
        if dest_dir.exists() and any(dest_dir.iterdir()) and not force:
            raise FileExistsError(f"mirror destination is non-empty: {dest_dir}")
        if dest_dir.exists():
            shutil.rmtree(dest_dir)
        shutil.copytree(src, dest_dir)
        return dest_dir
    raise ValueError(f"mirror source is neither file nor directory: {src}")
