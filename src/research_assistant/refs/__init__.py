"""Reference management: BibTeX merge + pandoc-driven format conversion.

Used by the `ref-manager` skill.
"""
from __future__ import annotations

import re
import shutil
import subprocess
from pathlib import Path

import bibtexparser
from bibtexparser.bibdatabase import BibDatabase
from bibtexparser.bparser import BibTexParser
from bibtexparser.bwriter import BibTexWriter

_PANDOC_FORMAT_BY_SUFFIX: dict[str, str] = {
    ".md": "markdown",
    ".markdown": "markdown",
    ".tex": "latex",
    ".latex": "latex",
    ".docx": "docx",
}
_SUPPORTED_PANDOC_FORMATS = frozenset({"markdown", "latex", "docx"})

# Engines tried in order. tectonic is preferred (matches /paper render spec).
_LATEX_ENGINES_DEFAULT: tuple[str, ...] = ("tectonic", "latexmk", "xelatex", "pdflatex")
_LATEX_TIMEOUT_SEC = 180
_LOG_TAIL_LINES = 40

# Matches \cite, \citep, \citet, \citeauthor, \cite*, \citep[pre][post], etc.
_CITE_RE = re.compile(r"\\cite[a-zA-Z]*\*?\s*(?:\[[^\]]*\]\s*){0,2}\{([^}]+)\}")


# ---------------------------------------------------------------------------
# BibTeX merge
# ---------------------------------------------------------------------------


def merge_bibtex(sources: list[Path], dest: Path) -> int:
    """Merge `sources` into `dest`, dedupe by DOI → (title + first-author) → entry key.

    First writer wins. Output is sorted by entry key for deterministic diffs.
    Returns the number of unique entries written.
    """
    seen_fingerprints: set[str] = set()
    merged_entries: list[dict] = []

    for source in sources:
        src_path = Path(source)
        if not src_path.is_file():
            raise FileNotFoundError(f"bibtex source not found: {src_path}")
        try:
            with src_path.open(encoding="utf-8") as f:
                db = bibtexparser.load(f, parser=BibTexParser(common_strings=True))
        except Exception as e:
            raise ValueError(f"failed to parse {src_path}: {e}") from e

        for entry in db.entries:
            fp = _entry_fingerprint(entry)
            if fp in seen_fingerprints:
                continue
            seen_fingerprints.add(fp)
            merged_entries.append(entry)

    merged_entries.sort(key=lambda e: e.get("ID", ""))

    out_db = BibDatabase()
    out_db.entries = merged_entries

    writer = BibTexWriter()
    writer.indent = "  "
    writer.order_entries_by = ("ID",)

    dest_path = Path(dest)
    dest_path.parent.mkdir(parents=True, exist_ok=True)
    with dest_path.open("w", encoding="utf-8") as f:
        bibtexparser.dump(out_db, f, writer=writer)

    return len(merged_entries)


def _entry_fingerprint(entry: dict) -> str:
    """Build dedup key in priority order: DOI > title+author > entry key."""
    # Strip BibTeX braces before normalizing — CrossRef emits `doi = {10.1145/x}`
    # while doi.org content-negotiation emits the bare value; without this the
    # two forms produce different fingerprints and dedup silently misses them.
    doi = (entry.get("doi") or "").replace("{", "").replace("}", "").strip().lower()
    if doi:
        for prefix in ("https://doi.org/", "http://doi.org/", "doi.org/", "doi:"):
            if doi.startswith(prefix):
                doi = doi[len(prefix):]
                break
        return f"doi:{doi}"

    title = _normalize_whitespace((entry.get("title") or "").lower())
    author = _first_author_lastname((entry.get("author") or "").lower())
    if title:
        return f"ta:{title}|{author}"

    return f"id:{(entry.get('ID') or '').lower()}"


def _normalize_whitespace(s: str) -> str:
    return " ".join(s.replace("{", "").replace("}", "").split())


def _first_author_lastname(author_field: str) -> str:
    """Pull the surname of the first author from a BibTeX `author` field."""
    if not author_field:
        return ""
    first = author_field.split(" and ", 1)[0].strip()
    if "," in first:
        return first.split(",", 1)[0].strip()
    parts = first.split()
    return parts[-1] if parts else ""


# ---------------------------------------------------------------------------
# Pandoc conversion
# ---------------------------------------------------------------------------


def convert_document(
    src: Path,
    dest: Path,
    from_fmt: str | None = None,
    to_fmt: str | None = None,
) -> Path:
    """Shell out to pandoc to convert `src` → `dest`.

    `from_fmt` / `to_fmt` default to inference from file extensions
    (`.md` → `markdown`, `.tex` → `latex`, `.docx` → `docx`).
    """
    src_path = Path(src)
    dest_path = Path(dest)
    if not src_path.is_file():
        raise FileNotFoundError(f"source not found: {src_path}")

    resolved_from = from_fmt or _PANDOC_FORMAT_BY_SUFFIX.get(src_path.suffix.lower())
    resolved_to = to_fmt or _PANDOC_FORMAT_BY_SUFFIX.get(dest_path.suffix.lower())
    if resolved_from not in _SUPPORTED_PANDOC_FORMATS:
        raise ValueError(
            f"unsupported source format: {resolved_from!r} (from {src_path.suffix!r})"
        )
    if resolved_to not in _SUPPORTED_PANDOC_FORMATS:
        raise ValueError(
            f"unsupported target format: {resolved_to!r} (from {dest_path.suffix!r})"
        )

    dest_path.parent.mkdir(parents=True, exist_ok=True)

    import pypandoc  # imported lazily so the import error is helpful

    try:
        pypandoc.convert_file(
            str(src_path),
            to=resolved_to,
            format=resolved_from,
            outputfile=str(dest_path),
            extra_args=[],
        )
    except OSError as e:
        raise RuntimeError(
            "pandoc binary not found on PATH — install pandoc or call "
            "pypandoc.download_pandoc()"
        ) from e
    return dest_path


# ---------------------------------------------------------------------------
# LaTeX cite-key scan
# ---------------------------------------------------------------------------


def scan_tex_cite_keys(direction_dir: Path) -> list[str]:
    r"""Walk `main.tex` + `sections/**/*.tex`; return all `\cite{...}` keys deduped.

    Handles `\citep`, `\citet`, `\cite*`, optional `[pre][post]` args, and
    comma-separated keys (`\cite{a, b, c}`). Comment lines (`% ...`) are
    stripped before matching. Preserves first-seen order for determinism.
    """
    direction_path = Path(direction_dir)
    if not direction_path.is_dir():
        return []

    tex_files: list[Path] = []
    main = direction_path / "main.tex"
    if main.is_file():
        tex_files.append(main)
    sections_dir = direction_path / "sections"
    if sections_dir.is_dir():
        tex_files.extend(sorted(sections_dir.rglob("*.tex")))

    seen: set[str] = set()
    keys: list[str] = []
    for tex in tex_files:
        try:
            text = tex.read_text(encoding="utf-8")
        except OSError:
            continue
        for line in text.splitlines():
            stripped = _strip_tex_comment(line)
            for match in _CITE_RE.finditer(stripped):
                for raw in match.group(1).split(","):
                    key = raw.strip()
                    if not key or key in seen:
                        continue
                    seen.add(key)
                    keys.append(key)
    return keys


def _strip_tex_comment(line: str) -> str:
    """Return `line` truncated before the first un-escaped `%`."""
    out: list[str] = []
    i = 0
    n = len(line)
    while i < n:
        c = line[i]
        if c == "\\" and i + 1 < n:
            out.append(c)
            out.append(line[i + 1])
            i += 2
            continue
        if c == "%":
            break
        out.append(c)
        i += 1
    return "".join(out)


def bib_entry_keys(refs_bib: Path) -> set[str]:
    r"""Return the set of entry keys (``@type{KEY, …}``) defined in `refs_bib`.

    Returns an empty set when the file is missing or unparseable — a malformed
    bib should surface as "everything is unresolved", not crash the caller.
    """
    refs_path = Path(refs_bib)
    if not refs_path.is_file():
        return set()
    try:
        with refs_path.open(encoding="utf-8") as f:
            db = bibtexparser.load(f, parser=BibTexParser(common_strings=True))
    except Exception:
        return set()
    return {e["ID"] for e in db.entries if e.get("ID")}


def unresolved_cite_keys(direction_dir: Path) -> list[str]:
    r"""List `\cite{}` keys used in the prose with no matching `refs.bib` entry.

    These are *citation debts*: the draft cites a key that ``/cite`` has not yet
    resolved into ``refs.bib``. Preserves first-seen order (from
    :func:`scan_tex_cite_keys`) for deterministic reporting.
    """
    cited = scan_tex_cite_keys(direction_dir)
    have = bib_entry_keys(Path(direction_dir) / "refs.bib")
    return [k for k in cited if k not in have]


# ---------------------------------------------------------------------------
# LaTeX render
# ---------------------------------------------------------------------------


def render_latex(
    direction_dir: Path,
    *,
    engines: tuple[str, ...] = _LATEX_ENGINES_DEFAULT,
    timeout_sec: int = _LATEX_TIMEOUT_SEC,
) -> Path:
    """Render `<direction_dir>/main.tex` to `main.pdf`.

    Tries engines in order, falling back when a binary is missing. Returns the
    path to the produced PDF. Raises `RuntimeError` with the tail of `main.log`
    on engine failure, or with the engine list if none are available.
    """
    direction_path = Path(direction_dir)
    main_tex = direction_path / "main.tex"
    if not main_tex.is_file():
        raise FileNotFoundError(f"no main.tex in {direction_path}")

    pdf_path = direction_path / "main.pdf"
    tried: list[str] = []
    for engine in engines:
        if shutil.which(engine) is None:
            continue
        tried.append(engine)
        try:
            _run_latex_engine(engine, main_tex, direction_path, timeout_sec)
        except subprocess.CalledProcessError as e:
            log_tail = _read_log_tail(direction_path / "main.log", _LOG_TAIL_LINES) \
                or (e.stdout or "") + (e.stderr or "")
            raise RuntimeError(
                f"{engine} failed (exit {e.returncode}):\n{log_tail}"
            ) from e
        except subprocess.TimeoutExpired as e:
            raise RuntimeError(
                f"{engine} timed out after {timeout_sec}s"
            ) from e
        return pdf_path

    raise RuntimeError(
        f"no LaTeX engine on PATH (tried: {', '.join(engines)})"
    )


def _run_latex_engine(
    engine: str, main_tex: Path, cwd: Path, timeout_sec: int
) -> None:
    """Run `engine` against `main_tex`. Raises CalledProcessError on failure."""
    name = main_tex.name
    stem = main_tex.stem
    if engine == "tectonic":
        cmds = [["tectonic", "--keep-logs", name]]
    elif engine == "latexmk":
        cmds = [["latexmk", "-pdf", "-interaction=nonstopmode", "-halt-on-error", name]]
    else:
        # Classic 3-pass for xelatex/pdflatex, with bibtex if refs.bib exists.
        base = [engine, "-interaction=nonstopmode", "-halt-on-error", name]
        cmds = [base]
        if (cwd / "refs.bib").is_file():
            cmds.append(["bibtex", stem])
            cmds.append(base)
        cmds.append(base)

    for cmd in cmds:
        subprocess.run(
            cmd,
            cwd=cwd,
            capture_output=True,
            text=True,
            timeout=timeout_sec,
            check=True,
        )


def _read_log_tail(log_path: Path, lines: int) -> str:
    if not log_path.is_file():
        return ""
    try:
        text = log_path.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return ""
    return "\n".join(text.splitlines()[-lines:])
