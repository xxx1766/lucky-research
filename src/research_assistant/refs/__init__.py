"""Reference management: BibTeX merge + pandoc-driven format conversion.

Used by the `ref-manager` skill.
"""

from pathlib import Path


def merge_bibtex(sources: list[Path], dest: Path) -> int:
    """Merge `sources` into `dest`, dedupe by DOI/title. Return entries written. STUB."""
    raise NotImplementedError("refs.merge_bibtex — implement with bibtexparser")


def convert_document(src: Path, dest: Path, from_fmt: str | None = None, to_fmt: str | None = None) -> Path:
    """Shell out to pandoc to convert `src` → `dest`. STUB."""
    raise NotImplementedError("refs.convert_document — shell out to pandoc via pypandoc")


def render_latex(direction_dir: Path) -> Path:
    """Render `<direction_dir>/main.tex` to `main.pdf` via tectonic or latexmk. STUB.

    Returns the path to the produced PDF. Build errors should surface (e.g. tail of
    the log) rather than be swallowed. Missing `_template/` is the caller's check,
    not this function's.
    """
    raise NotImplementedError("refs.render_latex — shell out to tectonic / latexmk")


def scan_tex_cite_keys(direction_dir: Path) -> list[str]:
    r"""Walk `main.tex` + `sections/*.tex`; return all `\cite{...}` keys deduped. STUB."""
    raise NotImplementedError("refs.scan_tex_cite_keys — regex over LaTeX sources")
