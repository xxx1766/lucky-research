"""Evidence-first placeholder tokens for LaTeX drafts.

The ``paper-architect`` write stage follows an *evidence-first* discipline: a
draft never fabricates a citation, a number, or a result. When the support for
a claim is not yet available, the prose carries an explicit placeholder token
instead of an invented fact. Those gaps are tracked as **debts** that later
stages (``/cite``, ``/experiment``, ``/figure``, ``/paper verify``) close.

Canonical tokens (case-sensitive, square-bracketed):

* ``[REF_NEEDED: …]``       — a claim needs a citation we do not yet have.
* ``[FIGURE_NEEDED: …]``    — a figure is referenced but not yet rendered.
* ``[DATA_NEEDED: …]``      — a number/result needs an experiment version.
* ``[CLAIM_UNVERIFIED: …]`` — an assertion that has not been checked.

Each token maps to one debt class consumed by the progress board:

    REF_NEEDED        -> citation
    FIGURE_NEEDED     -> figure
    DATA_NEEDED       -> evidence
    CLAIM_UNVERIFIED  -> evidence

This module only *reads* — it scans ``.tex`` sources and reports what it finds.
It never rewrites prose.
"""
from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path

# token name -> debt class
DEBT_BY_TOKEN: dict[str, str] = {
    "REF_NEEDED": "citation",
    "FIGURE_NEEDED": "figure",
    "DATA_NEEDED": "evidence",
    "CLAIM_UNVERIFIED": "evidence",
}

# `[TOKEN]` or `[TOKEN: free-form hint]`.
# The underscore in every token name is LaTeX-special, so a token written into
# a `.tex` source must escape it (`DATA\_NEEDED`) to compile. Match both the
# bare and the backslash-escaped form so a rendered debt is still tracked; the
# captured token is normalised (backslashes stripped) before the debt lookup.
_TOKEN_ALT = "|".join(name.replace("_", r"\\?_") for name in DEBT_BY_TOKEN)
_TOKEN_RE = re.compile(
    r"\[(" + _TOKEN_ALT + r")(?::\s*(.*?))?\s*\]"
)


@dataclass(frozen=True)
class Placeholder:
    """One placeholder token found in a draft."""

    token: str          # e.g. "REF_NEEDED"
    debt: str           # one of: citation / figure / evidence
    file: str           # path relative to the direction dir (POSIX)
    line: int           # 1-based line number
    hint: str           # free-form text after the colon ("" if none)


@dataclass(frozen=True)
class DebtSummary:
    """Open-debt counts for one direction, by class.

    ``citation`` / ``figure`` / ``evidence`` are computed *live* from the source
    (placeholder tokens + unresolved ``\\cite{}``). ``prose`` / ``consistency``
    are *judgment* debts that only ``/paper verify`` can produce, read back from
    the latest persisted ``VerificationReport`` per section.
    """

    citation: int = 0
    figure: int = 0
    evidence: int = 0
    consistency: int = 0
    prose: int = 0

    @property
    def total(self) -> int:
        return self.citation + self.figure + self.evidence + self.consistency + self.prose

    def as_line(self) -> str:
        """One-line human summary for the progress board / footer."""
        if self.total == 0:
            return "none"
        parts = [
            f"{n} {name}"
            for name, n in (
                ("citation", self.citation),
                ("figure", self.figure),
                ("evidence", self.evidence),
                ("consistency", self.consistency),
                ("prose", self.prose),
            )
            if n
        ]
        return f"{self.total} open · " + " · ".join(parts)


def _strip_tex_comment(line: str) -> str:
    """Return ``line`` truncated before the first un-escaped ``%``.

    Mirrors ``refs.scan_tex_cite_keys`` so a placeholder that appears only in a
    Chinese-translation ``%`` comment (which shadows the English paragraph) is
    not double-counted against the real prose gap.
    """
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


def _tex_sources(direction_dir: Path) -> list[Path]:
    """`main.tex` + every `sections/**/*.tex`, in deterministic order."""
    direction_path = Path(direction_dir)
    sources: list[Path] = []
    main = direction_path / "main.tex"
    if main.is_file():
        sources.append(main)
    sections_dir = direction_path / "sections"
    if sections_dir.is_dir():
        sources.extend(sorted(sections_dir.rglob("*.tex")))
    return sources


def scan_placeholders(direction_dir: Path) -> list[Placeholder]:
    """Scan a direction's ``.tex`` sources for placeholder tokens.

    Comment-only occurrences (after an un-escaped ``%``) are ignored so the
    Chinese translation comment above a paragraph never double-counts. Results
    are ordered by (file, line) for deterministic output.
    """
    direction_path = Path(direction_dir)
    if not direction_path.is_dir():
        return []

    found: list[Placeholder] = []
    for tex in _tex_sources(direction_path):
        try:
            text = tex.read_text(encoding="utf-8")
        except OSError:
            continue
        rel = tex.relative_to(direction_path).as_posix()
        for lineno, raw_line in enumerate(text.splitlines(), start=1):
            stripped = _strip_tex_comment(raw_line)
            for m in _TOKEN_RE.finditer(stripped):
                token = m.group(1).replace("\\", "")  # normalise `DATA\_NEEDED`
                hint = (m.group(2) or "").strip()
                found.append(
                    Placeholder(
                        token=token,
                        debt=DEBT_BY_TOKEN[token],
                        file=rel,
                        line=lineno,
                        hint=hint,
                    )
                )
    return found


def debt_summary(direction_dir: Path) -> DebtSummary:
    """Aggregate open debts for a direction.

    Combines placeholder tokens with unresolved ``\\cite{}`` keys (a cite key
    in the prose with no matching ``refs.bib`` entry is a citation debt). The
    ``refs`` import is lazy to keep this leaf module free of an import-time
    dependency on the reference-management package.
    """
    direction_path = Path(direction_dir)
    citation = figure = evidence = 0
    for ph in scan_placeholders(direction_path):
        if ph.debt == "citation":
            citation += 1
        elif ph.debt == "figure":
            figure += 1
        elif ph.debt == "evidence":
            evidence += 1

    try:
        from research_assistant.refs import unresolved_cite_keys

        citation += len(unresolved_cite_keys(direction_path))
    except (ImportError, OSError):
        pass

    # prose / consistency are judgment debts — only /paper verify produces them,
    # read back from the latest persisted VerificationReport per section.
    prose = consistency = 0
    try:
        from research_assistant.papers.verification import verify_debt_counts

        prose, consistency = verify_debt_counts(direction_path)
    except (ImportError, OSError, ValueError):
        pass

    return DebtSummary(
        citation=citation,
        figure=figure,
        evidence=evidence,
        consistency=consistency,
        prose=prose,
    )
