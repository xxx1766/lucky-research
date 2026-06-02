"""Git / filesystem operations against the experiment's bound repo.

All git invocations are time-bounded; network failures return error sentinels
rather than raising so ``/experiment status`` survives a flaky connection.
``mirror_results`` reads ``_LARGE_RESULT_BYTES`` from the parent package so
tests can monkeypatch it via ``experiments._LARGE_RESULT_BYTES``.
"""
from __future__ import annotations

import shutil
import subprocess
from pathlib import Path

import research_assistant.experiments as _exp  # late attribute access for _LARGE_RESULT_BYTES

from .paths import _guard_under, repo_clone_path, result_path

_GIT_TIMEOUT_S = 15
_CLONE_TIMEOUT_S = 120


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
    try:
        out = subprocess.run(  # noqa: S603 — no shell, fixed argv
            ["git", "ls-remote", url, branch],
            capture_output=True, text=True,
            timeout=_GIT_TIMEOUT_S, check=False,
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
    dest_dir.parent.mkdir(parents=True, exist_ok=True)
    if src.is_file():
        size = src.stat().st_size
        if size > _exp._LARGE_RESULT_BYTES and not force:
            raise ValueError(
                f"result file is {size / 1024 / 1024:.1f} MB (> 100 MB); "
                "pass force=True to mirror anyway"
            )
        dest_dir.mkdir(parents=True, exist_ok=True)
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
