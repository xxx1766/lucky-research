"""Idempotent LaTeX preamble injection for the algorithm package.

The pseudocode package choice is **venue-driven**: the venue's `_venue.md` may
declare `pseudocode-package: algorithm2e` in its YAML frontmatter to opt into
the algorithm2e ecosystem. Default is `algorithm + algpseudocode`, which
matches the majority of ML conference templates (NeurIPS / ICML / ICLR / CVPR).
"""
from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path

from research_assistant.pseudocode.schema import PseudocodePackage

DEFAULT_PACKAGE: PseudocodePackage = "algpseudocode"

# Lines we inject. Order matters: `algorithm` declares the float; the second package
# provides the body syntax. Idempotency is checked by exact substring match.
_PACKAGE_LINES: dict[PseudocodePackage, tuple[str, ...]] = {
    "algpseudocode": (
        r"\usepackage{algorithm}",
        r"\usepackage{algpseudocode}",
    ),
    "algorithm2e": (
        r"\usepackage[ruled,vlined,linesnumbered]{algorithm2e}",
    ),
}

_VENUE_FRONTMATTER = re.compile(r"^---\r?\n(.*?)\r?\n---", re.DOTALL)
_VENUE_PKG_LINE = re.compile(
    r"^\s*pseudocode-package\s*:\s*(?P<value>[A-Za-z0-9_-]+)\s*$",
    re.MULTILINE,
)


@dataclass(frozen=True)
class PreambleResult:
    package: PseudocodePackage
    added_lines: tuple[str, ...]   # subset of _PACKAGE_LINES[package] that were missing
    main_tex: Path                  # path that was (potentially) modified


def read_venue_package(venue_md_path: Path) -> PseudocodePackage:
    """Inspect `_venue.md` frontmatter; return the venue's pseudocode package or default."""
    if not venue_md_path.is_file():
        return DEFAULT_PACKAGE
    text = venue_md_path.read_text(encoding="utf-8", errors="replace")
    fm = _VENUE_FRONTMATTER.match(text)
    haystack = fm.group(1) if fm else text
    m = _VENUE_PKG_LINE.search(haystack)
    if not m:
        return DEFAULT_PACKAGE
    value = m.group("value").strip()
    if value not in ("algpseudocode", "algorithm2e"):
        return DEFAULT_PACKAGE
    return value  # type: ignore[return-value]


def _insertion_point(main_tex: str) -> int:
    """Find a sensible byte offset to insert `\\usepackage{...}` lines.

    Strategy: insert right after the LAST existing `\\usepackage{...}` line.
    If no such line exists, insert just before `\\begin{document}`.
    If neither anchor is found, append at end-of-file.
    """
    last_pkg = None
    for m in re.finditer(r"^\\usepackage(?:\[[^\]]*\])?\{[^}]*\}\s*$", main_tex, re.MULTILINE):
        last_pkg = m
    if last_pkg is not None:
        return last_pkg.end()
    begin_doc = re.search(r"^\\begin\{document\}", main_tex, re.MULTILINE)
    if begin_doc is not None:
        return begin_doc.start()
    return len(main_tex)


def ensure_preamble(
    main_tex_path: Path,
    *,
    venue_md_path: Path | None = None,
    package: PseudocodePackage | None = None,
) -> PreambleResult:
    """Make sure `main.tex` carries the algorithm-package \\usepackage lines.

    Idempotent. Reads `_venue.md` to pick the package family (unless `package=` is
    supplied explicitly). Returns which lines were appended (empty tuple = no-op).
    """
    if not main_tex_path.is_file():
        raise FileNotFoundError(f"main.tex not found at {main_tex_path}")

    if package is None:
        package = read_venue_package(venue_md_path) if venue_md_path else DEFAULT_PACKAGE

    text = main_tex_path.read_text(encoding="utf-8")
    needed = _PACKAGE_LINES[package]
    missing = tuple(line for line in needed if line not in text)
    if not missing:
        return PreambleResult(package=package, added_lines=(), main_tex=main_tex_path)

    insert_at = _insertion_point(text)
    leading_nl = "" if text[:insert_at].endswith("\n") else "\n"
    block = leading_nl + "\n".join(missing) + "\n"
    new_text = text[:insert_at] + block + text[insert_at:]
    main_tex_path.write_text(new_text, encoding="utf-8")
    return PreambleResult(package=package, added_lines=missing, main_tex=main_tex_path)
