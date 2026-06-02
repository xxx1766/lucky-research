"""Title / abstract / latex-strip helpers for ``/paper archive``.

Extracted from :mod:`research_assistant.papers.archive` to keep both files
under the 500-line limit. All helpers are pure (string in, string/None out)
and operate on a paper directory root.
"""
from __future__ import annotations

import re
from pathlib import Path

import yaml

_FM_RE = re.compile(r"^---\r?\n(.*?)\r?\n---\r?\n?(.*)$", re.DOTALL)
_TITLE_RE = re.compile(r"\\title\s*\{([^{}]*)\}")
_ABSTRACT_RE = re.compile(
    r"\\begin\{abstract\}(.*?)\\end\{abstract\}",
    re.DOTALL,
)


def _extract_title(paper_dir_root: Path) -> str | None:
    """Best-effort title pull, in order: expert.md frontmatter ``title:`` ->
    main.tex ``\\title{...}`` -> None. ``\\title`` matching only handles the
    simple non-nested-braces case; weird LaTeX gymnastics fall through to None
    and the caller picks a venue/direction fallback."""
    expert = paper_dir_root / "expert.md"
    if expert.is_file():
        text = expert.read_text(encoding="utf-8", errors="replace")
        m = _FM_RE.match(text)
        if m:
            try:
                fm = yaml.safe_load(m.group(1)) or {}
            except yaml.YAMLError:
                fm = {}
            title = fm.get("title")
            if isinstance(title, str) and title.strip():
                return title.strip()
    main_tex = paper_dir_root / "main.tex"
    if main_tex.is_file():
        text = main_tex.read_text(encoding="utf-8", errors="replace")
        m = _TITLE_RE.search(text)
        if m and m.group(1).strip():
            return m.group(1).strip()
    return None


def _extract_abstract(paper_dir_root: Path) -> str | None:
    """Pull the abstract from main.tex or sections/abstract.tex if present."""
    for candidate in (
        paper_dir_root / "main.tex",
        paper_dir_root / "sections" / "abstract.tex",
    ):
        if not candidate.is_file():
            continue
        text = candidate.read_text(encoding="utf-8", errors="replace")
        m = _ABSTRACT_RE.search(text)
        if m and m.group(1).strip():
            return _strip_latex_minimal(m.group(1).strip())
    return None


def _strip_latex_minimal(text: str) -> str:
    """Light-touch: drop ``%`` line comments and collapse runs of whitespace.

    We're not trying to be ``detex`` — the user reads this text inside a
    past-work entry, so a few stray macros are fine. Aggressive stripping risks
    mangling the meaning.
    """
    lines: list[str] = []
    for raw in text.splitlines():
        stripped = re.sub(r"(?<!\\)%.*$", "", raw)
        lines.append(stripped)
    joined = " ".join(lines)
    return re.sub(r"\s+", " ", joined).strip()


def _read_experiment_binding(paper_dir_root: Path) -> str | None:
    """Return the ``experiment:`` slug from ``expert.md`` frontmatter, or None.

    Mirrors :func:`research_assistant.papers.binding.read_binding_from_expert_md`
    but reads directly from a path (we may be inspecting the moved tree).
    """
    expert = paper_dir_root / "expert.md"
    if not expert.is_file():
        return None
    text = expert.read_text(encoding="utf-8", errors="replace")
    m = _FM_RE.match(text)
    if not m:
        return None
    try:
        fm = yaml.safe_load(m.group(1)) or {}
    except yaml.YAMLError:
        return None
    val = fm.get("experiment")
    return val if isinstance(val, str) and val else None
