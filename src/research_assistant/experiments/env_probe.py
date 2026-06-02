"""Cross-platform environment-capture probes for ``register_version``.

Each probe is independently fail-soft: returns ``None`` / ``[]`` / ``{}`` on
absence rather than raising, so ``capture_env`` always produces *some* dict
even on a vanilla machine without CUDA. Tests monkeypatch ``experiments.capture_env``
and ``experiments._probe_full_pip_freeze`` via the parent package; the actual
definitions live here but are re-exported from ``experiments/__init__.py``.
"""
from __future__ import annotations

import platform
import re
import socket
import subprocess
import sys

_ENV_PROBE_TIMEOUT_S = 5

_TRACKED_LIBS: tuple[str, ...] = (
    "torch", "transformers", "peft", "datasets", "accelerate",
    "deepspeed", "numpy", "scipy", "scikit-learn", "pandas",
)


def _safe_subprocess(cmd: list[str], timeout: int = _ENV_PROBE_TIMEOUT_S) -> str | None:
    try:
        out = subprocess.run(  # noqa: S603 — no shell, caller-supplied argv
            cmd, capture_output=True, text=True, timeout=timeout, check=False,
        )
    except (subprocess.TimeoutExpired, FileNotFoundError, OSError):
        return None
    if out.returncode != 0:
        return None
    return out.stdout


def _probe_cuda() -> str | None:
    out = _safe_subprocess(["nvcc", "--version"])
    if not out:
        return None
    m = re.search(r"release\s+(\d+\.\d+)", out)
    return m.group(1) if m else None


def _probe_gpu() -> list[dict]:
    out = _safe_subprocess([
        "nvidia-smi",
        "--query-gpu=name,driver_version",
        "--format=csv,noheader",
    ])
    if not out:
        return []
    by_name: dict[str, dict] = {}
    for line in out.strip().splitlines():
        parts = [s.strip() for s in line.split(",")]
        if len(parts) < 2:
            continue
        name, driver = parts[0], parts[1]
        if name in by_name:
            by_name[name]["count"] += 1
        else:
            by_name[name] = {"name": name, "count": 1, "driver": driver}
    return list(by_name.values())


def _probe_libraries() -> dict[str, str]:
    out = _safe_subprocess([sys.executable, "-m", "pip", "freeze"], timeout=15)
    if not out:
        return {}
    libs: dict[str, str] = {}
    for line in out.splitlines():
        if "==" in line:
            name, _, version = line.partition("==")
        elif " @ " in line:
            name, _, _ = line.partition(" @ ")
            version = "unknown"
        else:
            continue
        key = name.strip().lower()
        if key in _TRACKED_LIBS:
            libs[key] = version.strip()
    return libs


def _probe_full_pip_freeze() -> str | None:
    return _safe_subprocess([sys.executable, "-m", "pip", "freeze"], timeout=15)


def capture_env() -> dict:
    """Cross-platform env snapshot for reproducibility / rebuttal.

    Always populates ``hostname``, ``os``, ``arch``, ``python`` (no subprocess
    needed). Adds ``cuda``, ``gpu``, ``libraries`` if probes succeed; missing
    keys are simply omitted rather than crashing the capture.
    """
    env: dict = {
        "hostname": socket.gethostname(),
        "os": platform.platform(),
        "arch": platform.machine(),
        "python": platform.python_version(),
    }
    cuda = _probe_cuda()
    if cuda:
        env["cuda"] = cuda
    gpu = _probe_gpu()
    if gpu:
        env["gpu"] = gpu
    libs = _probe_libraries()
    if libs:
        env["libraries"] = libs
    return env
