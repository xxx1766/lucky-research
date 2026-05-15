"""Literature ingestion: PDF parsing and arXiv fetch.

Used by the `lit-summarize` skill and `paper-architect`'s venue-refs sub-stage to
turn `inputs/papers/*.pdf` and arXiv URLs into plain text + lightweight metadata.
"""

from __future__ import annotations

import re
from pathlib import Path

_ARXIV_ID_RE = re.compile(r"\b(\d{4}\.\d{4,5}(v\d+)?)\b")
_PDF_CREATION_DATE_RE = re.compile(r"D:(\d{4})")


def extract_pdf_text(pdf_path: Path) -> str:
    """Return the plain text of `pdf_path` (concatenated pages, blank-line separated)."""
    import fitz  # PyMuPDF

    pdf_path = Path(pdf_path)
    if not pdf_path.is_file():
        raise FileNotFoundError(f"PDF not found: {pdf_path}")
    parts: list[str] = []
    with fitz.open(pdf_path) as doc:
        for page in doc:
            parts.append(page.get_text("text"))
    return "\n\n".join(parts)


def fetch_arxiv(arxiv_id: str, dest_dir: Path) -> Path:
    """Download an arXiv paper PDF into `dest_dir`, return the path.

    Accepts a raw id (`2401.12345`), versioned id (`2401.12345v2`), or a URL
    containing one. Filename is `<id>.pdf` (version stripped).
    """
    import arxiv

    aid = _normalize_arxiv_id(arxiv_id)
    dest_dir = Path(dest_dir)
    dest_dir.mkdir(parents=True, exist_ok=True)
    search = arxiv.Search(id_list=[aid])
    results = list(search.results())
    if not results:
        raise ValueError(f"arXiv id not found: {arxiv_id}")
    result = results[0]
    filename = f"{aid}.pdf"
    out = Path(result.download_pdf(dirpath=str(dest_dir), filename=filename))
    return out


def parse_metadata(pdf_path: Path) -> dict:
    """Return `{title, authors, year, abstract}` (best-effort) from a PDF."""
    import fitz

    pdf_path = Path(pdf_path)
    if not pdf_path.is_file():
        raise FileNotFoundError(f"PDF not found: {pdf_path}")

    with fitz.open(pdf_path) as doc:
        meta = doc.metadata or {}
        first_page = doc[0].get_text("text") if len(doc) else ""

    title = _clean(meta.get("title")) or _guess_title(first_page)
    authors = _split_authors(meta.get("author")) or _guess_authors(first_page)
    year = _year_from_date(meta.get("creationDate") or meta.get("modDate"))
    abstract = _extract_abstract(first_page)

    return {
        "title": title or "",
        "authors": authors,
        "year": year,
        "abstract": abstract,
    }


# ---------- helpers ----------

def _normalize_arxiv_id(value: str) -> str:
    """Pull a bare arXiv id out of a raw id, versioned id, or URL."""
    if not value:
        raise ValueError("empty arxiv id")
    m = _ARXIV_ID_RE.search(value)
    if not m:
        raise ValueError(f"could not parse arXiv id from: {value!r}")
    aid = m.group(1)
    # strip version suffix (v1, v2, ...)
    return re.sub(r"v\d+$", "", aid)


def _clean(value: str | None) -> str:
    return (value or "").strip()


def _split_authors(value: str | None) -> list[str]:
    if not value:
        return []
    sep = ";" if ";" in value else ","
    return [a.strip() for a in value.split(sep) if a.strip()]


def _year_from_date(value: str | None) -> int | None:
    if not value:
        return None
    m = _PDF_CREATION_DATE_RE.search(value)
    if not m:
        return None
    try:
        year = int(m.group(1))
    except ValueError:
        return None
    return year if 1900 <= year <= 2100 else None


def _guess_title(first_page: str) -> str:
    """First non-empty line of the first page, capped to one wrapped title line."""
    for line in first_page.splitlines():
        line = line.strip()
        if 6 < len(line) < 250 and not line.lower().startswith("arxiv:"):
            return line
    return ""


def _guess_authors(first_page: str) -> list[str]:
    """Heuristic: line after the title that contains commas/semicolons but no period."""
    lines = [ln.strip() for ln in first_page.splitlines()]
    saw_title = False
    for line in lines:
        if not line:
            continue
        if not saw_title:
            saw_title = True
            continue
        if any(ch in line for ch in (",", ";")) and "." not in line and len(line) < 300:
            return [a.strip() for a in re.split(r"[,;]", line) if a.strip()]
        if len(line) > 300:
            break
    return []


def _extract_abstract(first_page: str) -> str | None:
    """Find an 'Abstract' block on page 1; return text up to the next blank-line gap."""
    if not first_page:
        return None
    lower = first_page.lower()
    idx = lower.find("abstract")
    if idx == -1:
        return None
    body = first_page[idx + len("abstract"):].lstrip(" :.\n\t")
    # cut at "1 Introduction" / "1. Introduction" or a double-blank gap
    stop = re.search(r"\n\s*\n\s*\n|\n\s*1[.\s]+Introduction\b", body, re.IGNORECASE)
    if stop:
        body = body[: stop.start()]
    body = re.sub(r"\s+", " ", body).strip()
    return body or None
