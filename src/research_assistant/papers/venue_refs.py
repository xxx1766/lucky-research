"""Venue-stage reference-paper orchestration.

The user submits a few reference papers from the target venue. For each, an LLM
extracts a `VenueRefAnalysis` (prose conventions, citation style, hedging
vocab, etc.); we persist the analysis to `outputs/papers/<venue>/_venue-refs/
<slug>.md` and aggregate the lot into the `## Writing conventions` block of
`_venue.md`.

The LLM does the analysis and aggregation; this module is plumbing. Both
`analyze` and `aggregate` are injected callables — tests pass mocks, the
`paper-architect` skill passes the Claude-driven prompts.
"""

from __future__ import annotations

import datetime as _dt
import re
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import yaml

from research_assistant.common.io import PAPERS_DIR, PAPERS_INPUT_DIR

from .venue_conventions import (
    VenueRefAnalysis,
    analysis_to_markdown,
    load_venue_ref_analysis,
)
from .venue_merge import (
    SENTINEL_BEGIN,
    SENTINEL_END,
    upsert_writing_conventions,
)

__all__ = [
    "VenueRefEntry",
    "VenueRefsSummary",
    "distill_venue_conventions",
    "ingest_venue_ref",
    "list_venue_refs",
    "slugify_paper_ref",
    "venue_ref_path",
    "venue_refs_dir",
    "venue_refs_summary",
]

_ARXIV_ID_RE = re.compile(r"^\s*(?:https?://[^\s]*arxiv\.org/[^\s]*?)?(\d{4}\.\d{4,5}(?:v\d+)?)\s*$")
_NON_ALNUM = re.compile(r"[^a-z0-9]+")
_STOPWORDS = {
    "the", "a", "an", "of", "for", "with", "and", "or", "to", "in", "on", "by",
    "using", "via", "from", "into",
}


# ---------- path helpers ----------

def _guard_under(root: Path, candidate: Path, what: str) -> Path:
    """Raise ``ValueError`` if ``candidate`` resolves outside ``root``."""
    # Use absolute() not resolve() — resolve() requires the path to exist, but
    # callers commonly ask for a path before creating it.
    rr = root.absolute()
    cc = candidate.absolute()
    try:
        cc.relative_to(rr)
    except ValueError as exc:
        raise ValueError(f"{what} escapes {root.name}: {candidate}") from exc
    return cc


def venue_refs_dir(venue_slug: str) -> Path:
    """`outputs/papers/<venue>/_venue-refs/`, guarded under `PAPERS_DIR`."""
    if not venue_slug or "/" in venue_slug or venue_slug.startswith("."):
        raise ValueError(f"invalid venue slug: {venue_slug!r}")
    candidate = PAPERS_DIR / venue_slug / "_venue-refs"
    return _guard_under(PAPERS_DIR, candidate, "venue-refs dir")


def venue_ref_path(venue_slug: str, paper_slug: str) -> Path:
    """Per-paper markdown path, guarded under `venue_refs_dir`."""
    if not paper_slug or "/" in paper_slug or paper_slug.startswith("."):
        raise ValueError(f"invalid paper slug: {paper_slug!r}")
    root = venue_refs_dir(venue_slug)
    return _guard_under(root, root / f"{paper_slug}.md", "venue-ref path")


# ---------- slug ----------

def slugify_paper_ref(
    title: str | None,
    year: int | None,
    arxiv_id: str | None,
    authors: list[str] | None = None,
) -> str:
    """Build a kebab slug: `<lastname>-<year>-<short-title>`.

    Falls back through: lastname → year → short-title → arxiv id. At least one
    component must be present.
    """
    parts: list[str] = []
    if authors:
        last = _last_name(authors[0])
        if last:
            parts.append(last)
    if year:
        parts.append(str(year))
    short = _short_title(title or "")
    if short:
        parts.append(short)
    slug = "-".join(p for p in parts if p)
    if not slug and arxiv_id:
        slug = _clean_slug(arxiv_id)
    if not slug:
        raise ValueError("cannot build slug — need at least one of title/authors/year/arxiv_id")
    return slug


def _last_name(author: str) -> str:
    author = author.strip()
    if not author:
        return ""
    # "Last, First M." or "First M. Last"
    if "," in author:
        last = author.split(",")[0]
    else:
        last = author.split()[-1]
    return _clean_slug(last)


def _short_title(title: str) -> str:
    words = [w.lower() for w in re.findall(r"[A-Za-z0-9]+", title)]
    keep = [w for w in words if w not in _STOPWORDS][:4]
    return "-".join(keep)


def _clean_slug(value: str) -> str:
    return _NON_ALNUM.sub("-", value.lower()).strip("-")


# ---------- list / summary ----------

@dataclass(frozen=True)
class VenueRefEntry:
    slug: str
    title: str
    year: int | None
    authors: list[str]
    added_at: str
    path: Path


@dataclass(frozen=True)
class VenueRefsSummary:
    count: int
    distilled: bool
    last_added: str | None


def list_venue_refs(venue_slug: str) -> list[VenueRefEntry]:
    """Enumerate `_venue-refs/*.md`; parse frontmatter; sort by `added_at` desc."""
    refs_dir = venue_refs_dir(venue_slug)
    if not refs_dir.is_dir():
        return []
    entries: list[VenueRefEntry] = []
    for path in sorted(refs_dir.glob("*.md")):
        meta = _read_frontmatter(path)
        if not meta:
            continue
        entries.append(
            VenueRefEntry(
                slug=str(meta.get("slug") or path.stem),
                title=str(meta.get("title") or ""),
                year=_coerce_int(meta.get("year")),
                authors=list(meta.get("authors") or []),
                added_at=str(meta.get("added_at") or ""),
                path=path,
            )
        )
    entries.sort(key=lambda e: e.added_at, reverse=True)
    return entries


def venue_refs_summary(venue_slug: str) -> VenueRefsSummary | None:
    """`{count, distilled, last_added}` for the venue-only progress footer.

    Returns `None` if the venue directory itself is absent.
    """
    venue_dir = PAPERS_DIR / venue_slug
    if not venue_dir.is_dir():
        return None
    try:
        entries = list_venue_refs(venue_slug)
    except ValueError:
        return None
    venue_md = venue_dir / "_venue.md"
    distilled = False
    if venue_md.is_file():
        text = venue_md.read_text(encoding="utf-8", errors="replace")
        distilled = SENTINEL_BEGIN in text and SENTINEL_END in text
    last_added = entries[0].added_at if entries else None
    return VenueRefsSummary(count=len(entries), distilled=distilled, last_added=last_added)


# ---------- ingest / distill ----------

def ingest_venue_ref(
    venue_slug: str,
    source: str,
    *,
    extract_pdf_text: Callable[[Path], str] | None = None,
    fetch_arxiv: Callable[[str, Path], Path] | None = None,
    parse_metadata: Callable[[Path], dict] | None = None,
    analyze: Callable[[str, dict], VenueRefAnalysis] | None = None,
) -> Path:
    """Resolve PDF/arXiv source → metadata → text → analyze → write `_venue-refs/<slug>.md`.

    Idempotent: if a slug-matching file already exists, return that path without
    calling `analyze` (or any of the other callables). Delete the file to force
    re-analysis.
    """
    venue_dir = PAPERS_DIR / venue_slug
    if not venue_dir.is_dir():
        raise FileNotFoundError(
            f"venue not initialized: {venue_dir} — run `/paper venue {venue_slug}` first"
        )

    arxiv_id, pdf_path = _resolve_source(source, fetch_arxiv=fetch_arxiv)
    if parse_metadata is None:
        raise ValueError("ingest_venue_ref: `parse_metadata` callable required")
    meta = parse_metadata(pdf_path) or {}
    title = meta.get("title") or ""
    authors = list(meta.get("authors") or [])
    year = _coerce_int(meta.get("year"))

    slug = slugify_paper_ref(title=title, year=year, arxiv_id=arxiv_id, authors=authors)
    out_path = venue_ref_path(venue_slug, slug)
    if out_path.is_file():
        return out_path

    if extract_pdf_text is None:
        raise ValueError("ingest_venue_ref: `extract_pdf_text` callable required")
    if analyze is None:
        raise ValueError("ingest_venue_ref: `analyze` callable required")
    text = extract_pdf_text(pdf_path)
    meta_for_analyze: dict[str, Any] = {
        "slug": slug,
        "title": title,
        "authors": authors,
        "year": year,
        "venue": venue_slug,
        "pdf_path": _relative_to_repo(pdf_path),
        "pdf_abs_path": str(Path(pdf_path).resolve()),
        "arxiv_id": arxiv_id,
        "added_at": _today_iso(),
    }
    analysis = analyze(text, meta_for_analyze)
    analysis = _ensure_identity_fields(analysis, meta_for_analyze)

    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(analysis_to_markdown(analysis), encoding="utf-8")
    return out_path


def distill_venue_conventions(
    venue_slug: str,
    *,
    aggregate: Callable[[list[VenueRefAnalysis]], str] | None = None,
) -> Path:
    """Read all `_venue-refs/*.md` → `aggregate` → upsert `_venue.md`. Returns `_venue.md`."""
    if aggregate is None:
        raise ValueError("distill_venue_conventions: `aggregate` callable required")
    venue_dir = PAPERS_DIR / venue_slug
    venue_md = venue_dir / "_venue.md"
    if not venue_md.is_file():
        raise FileNotFoundError(
            f"_venue.md not found: {venue_md} — run `/paper venue {venue_slug}` first"
        )
    refs_dir = venue_refs_dir(venue_slug)
    analyses: list[VenueRefAnalysis] = []
    if refs_dir.is_dir():
        for path in sorted(refs_dir.glob("*.md")):
            try:
                analyses.append(load_venue_ref_analysis(path))
            except (ValueError, OSError):
                # Skip malformed files rather than fail the whole distill.
                continue
    body = aggregate(analyses)
    upsert_writing_conventions(venue_md, body)
    return venue_md


# ---------- internals ----------

def _resolve_source(
    source: str,
    *,
    fetch_arxiv: Callable[[str, Path], Path] | None,
) -> tuple[str | None, Path]:
    """Return (arxiv_id_or_None, local_pdf_path) for an arxiv id/URL or local PDF path."""
    m = _ARXIV_ID_RE.match(source)
    if m:
        if fetch_arxiv is None:
            raise ValueError("source looks like an arXiv id but `fetch_arxiv` not provided")
        arxiv_id = m.group(1)
        clean_id = re.sub(r"v\d+$", "", arxiv_id)
        pdf_path = Path(fetch_arxiv(clean_id, PAPERS_INPUT_DIR))
        return clean_id, pdf_path

    pdf_path = Path(source).expanduser()
    if not pdf_path.is_absolute():
        # Try relative to repo CWD; otherwise treat as relative to PAPERS_INPUT_DIR.
        for base in (Path.cwd(), PAPERS_INPUT_DIR.parent.parent, PAPERS_INPUT_DIR):
            cand = (base / pdf_path).resolve()
            if cand.is_file():
                pdf_path = cand
                break
    if not pdf_path.is_file():
        raise FileNotFoundError(f"PDF source not found: {source}")
    return None, pdf_path


def _ensure_identity_fields(
    analysis: VenueRefAnalysis, meta: dict[str, Any]
) -> VenueRefAnalysis:
    """Overwrite identity fields on the analysis from our authoritative meta dict.

    The LLM may have hallucinated or omitted slug/title/added_at; we own those.
    """
    data = analysis.model_dump()
    for key in ("slug", "title", "authors", "year", "venue", "pdf_path", "arxiv_id", "added_at"):
        if meta.get(key) not in (None, "", []):
            data[key] = meta[key]
    return VenueRefAnalysis.model_validate(data)


def _read_frontmatter(path: Path) -> dict | None:
    try:
        text = path.read_text(encoding="utf-8")
    except OSError:
        return None
    if not text.startswith("---"):
        return None
    rest = text[3:].lstrip("\r\n")
    end = rest.find("\n---")
    if end == -1:
        return None
    try:
        data = yaml.safe_load(rest[:end]) or {}
    except yaml.YAMLError:
        return None
    return data if isinstance(data, dict) else None


def _coerce_int(value: Any) -> int | None:
    if value is None or value == "":
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def _relative_to_repo(path: Path) -> str:
    try:
        return str(path.resolve().relative_to(PAPERS_DIR.parent.parent))
    except ValueError:
        return str(path)


def _today_iso() -> str:
    return _dt.date.today().isoformat()
