"""Compile an algorithm-environment .tex snippet to a standalone PDF preview.

A `/pseudocode new <slug>` writes `algorithms/<slug>.tex` containing just the
`\\begin{algorithm} ... \\end{algorithm}` block (so paper-architect can
`\\input{}` it from a section). To produce a human-eyeball preview, we wrap the
snippet in a minimal `\\documentclass{article}` document at compile time and
shell out to tectonic → xelatex → pdflatex (first one available wins).

Adapted from gen-pseudocode-skill `scripts/compile_algo.py` (MIT).
"""
from __future__ import annotations

import re
import shutil
import subprocess
import tempfile
from dataclasses import dataclass
from pathlib import Path

from research_assistant.pseudocode.schema import PseudocodePackage

_DEFAULT_TIMEOUT_SEC = 90
_LOG_TAIL_CHARS = 800

# Compilation engines tried in order. tectonic is preferred (matches /paper render).
_ENGINES_DEFAULT: tuple[str, ...] = ("tectonic", "xelatex", "pdflatex")


def _tail(log: str) -> str:
    """Last `_LOG_TAIL_CHARS` of ``log`` with a leading truncation marker.

    The marker lets users know more context is upstream — many LaTeX errors
    quote the offending line ~1-2KB above the final "Fatal error" line, and a
    silent truncation reads as "the engine said nothing useful".
    """
    if len(log) <= _LOG_TAIL_CHARS:
        return log
    return (
        f"(... truncated {len(log) - _LOG_TAIL_CHARS} chars of LaTeX log; "
        f"showing last {_LOG_TAIL_CHARS} ...)\n"
        f"{log[-_LOG_TAIL_CHARS:]}"
    )

_PREAMBLE_BY_PACKAGE: dict[PseudocodePackage, str] = {
    "algpseudocode": (
        "\\usepackage{amsmath,amssymb,amsfonts}\n"
        "\\usepackage{algorithm}\n"
        "\\usepackage{algpseudocode}\n"
    ),
    "algorithm2e": (
        "\\usepackage{amsmath,amssymb,amsfonts}\n"
        "\\usepackage[ruled,vlined,linesnumbered]{algorithm2e}\n"
    ),
}

# Crude detector: snippet already contains `\documentclass`.
_IS_STANDALONE = re.compile(r"\\documentclass\b")


@dataclass(frozen=True)
class CompileResult:
    success: bool
    engine: str | None        # which engine actually produced the PDF (None on failure)
    pdf_path: Path | None
    log_tail: str             # last ~800 chars of stdout+stderr, with a truncation marker
                              # prepended when more context exists upstream


def _wrap_standalone(snippet: str, package: PseudocodePackage) -> str:
    preamble = _PREAMBLE_BY_PACKAGE[package]
    return (
        "\\documentclass[border=4pt]{article}\n"
        + preamble
        + "\\pagestyle{empty}\n"
        + "\\begin{document}\n"
        + snippet.strip()
        + "\n\\end{document}\n"
    )


def compile_snippet(
    snippet_path: Path,
    *,
    package: PseudocodePackage,
    out_pdf: Path | None = None,
    timeout_sec: int = _DEFAULT_TIMEOUT_SEC,
    engines: tuple[str, ...] = _ENGINES_DEFAULT,
) -> CompileResult:
    """Wrap an algorithm-only `.tex` snippet in a standalone document and compile it.

    On success, the resulting PDF is moved to `out_pdf` (default: same dir as
    snippet, name = `<snippet stem>.pdf`).
    """
    if not snippet_path.is_file():
        raise FileNotFoundError(f"snippet not found: {snippet_path}")
    snippet_text = snippet_path.read_text(encoding="utf-8")
    final_pdf = out_pdf or snippet_path.with_suffix(".pdf")

    if _IS_STANDALONE.search(snippet_text):
        # User shipped a full document; compile as-is (no wrapping).
        doc_text = snippet_text
    else:
        doc_text = _wrap_standalone(snippet_text, package=package)

    with tempfile.TemporaryDirectory(prefix="pseudocode-compile-") as tmp:
        tmpdir = Path(tmp)
        stem = snippet_path.stem
        wrapped = tmpdir / f"{stem}.tex"
        wrapped.write_text(doc_text, encoding="utf-8")

        last_log = ""
        for eng in engines:
            if shutil.which(eng) is None:
                continue
            cmd = _build_cmd(eng, wrapped, tmpdir)
            try:
                result = subprocess.run(
                    cmd,
                    capture_output=True,
                    text=True,
                    timeout=timeout_sec,
                    cwd=tmpdir,
                    check=False,
                )
            except subprocess.TimeoutExpired as e:
                last_log = f"[{eng}] timed out after {timeout_sec}s\n{e.stdout or ''}{e.stderr or ''}"
                continue
            last_log = (result.stdout or "") + (result.stderr or "")
            produced = tmpdir / f"{stem}.pdf"
            if result.returncode == 0 and produced.exists():
                final_pdf.parent.mkdir(parents=True, exist_ok=True)
                shutil.move(str(produced), str(final_pdf))
                return CompileResult(
                    success=True,
                    engine=eng,
                    pdf_path=final_pdf,
                    log_tail=_tail(last_log),
                )

    return CompileResult(
        success=False,
        engine=None,
        pdf_path=None,
        log_tail=_tail(last_log) if last_log else "no LaTeX engine on PATH (tried: " + ", ".join(engines) + ")",
    )


def _build_cmd(engine: str, tex_file: Path, workdir: Path) -> list[str]:
    if engine == "tectonic":
        return [engine, "--keep-logs", "--outdir", str(workdir), str(tex_file)]
    return [
        engine,
        "-interaction=nonstopmode",
        "-halt-on-error",
        f"-output-directory={workdir}",
        str(tex_file),
    ]
