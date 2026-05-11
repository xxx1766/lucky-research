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
