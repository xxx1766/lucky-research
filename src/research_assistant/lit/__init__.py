"""Literature ingestion: PDF parsing and arXiv fetch.

Used by the `lit-summarize` skill to turn `inputs/papers/*.pdf` and arXiv URLs into
plain text + lightweight metadata that Claude can then summarize.
"""

from pathlib import Path


def extract_pdf_text(pdf_path: Path) -> str:
    """Return the plain text of `pdf_path`. STUB — uses PyMuPDF when implemented."""
    raise NotImplementedError("lit.extract_pdf_text — implement with PyMuPDF (fitz)")


def fetch_arxiv(arxiv_id: str, dest_dir: Path) -> Path:
    """Download an arXiv paper PDF into `dest_dir`, return the path. STUB."""
    raise NotImplementedError("lit.fetch_arxiv — implement with the `arxiv` package")


def parse_metadata(pdf_path: Path) -> dict:
    """Return {title, authors, year, abstract} when extractable. STUB."""
    raise NotImplementedError("lit.parse_metadata — implement (try PyMuPDF + heuristics)")
