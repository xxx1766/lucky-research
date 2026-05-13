"""Optional D2 scaffold — writes .d2 source, shells `d2`, returns the produced SVG.

If the `d2` binary is missing or the render fails, returns None so the caller
can fall back to raw-SVG generation.
"""
from __future__ import annotations

import shutil
import subprocess
import tempfile
from pathlib import Path

_RENDER_TIMEOUT_S = 30


def d2_available() -> bool:
    return _which_d2() is not None


def _which_d2() -> str | None:
    return shutil.which("d2")


def scaffold_to_svg(
    d2_source: str, out_path: Path, *, theme_id: int = 200
) -> Path | None:
    """Render `d2_source` to `out_path` (SVG). Returns out_path or None on failure.

    The `.d2` source is deliberately NOT persisted — once the SVG is in place,
    it becomes the single source of truth (the user / Claude iterates on the
    SVG from here). Caller is responsible for setting `backend: d2-scaffolded`
    in the figure's note.md.
    """
    binary = _which_d2()
    if not binary:
        return None
    with tempfile.NamedTemporaryFile("w", suffix=".d2", delete=False) as tmp:
        tmp.write(d2_source)
        tmp_path = Path(tmp.name)
    try:
        result = subprocess.run(
            [binary, "-t", str(theme_id), str(tmp_path), str(out_path)],
            capture_output=True,
            text=True,
            timeout=_RENDER_TIMEOUT_S,
        )
        if result.returncode != 0:
            return None
        return out_path
    finally:
        try:
            tmp_path.unlink()
        except OSError:
            pass
