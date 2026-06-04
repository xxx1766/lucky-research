"""Claim-strength audit — flag over-strong wording for `/paper verify` Pass 2.

Adapted from the *academic-polishing* skill of
`github.com/joshua-zyy/academic-paper-writer`. A small, deterministic scan that
surfaces high-risk strength words in the prose so the verify *argument* pass can
check each against its evidence.

A flagged word is **not** automatically a debt — "significantly (p<0.01)" is
perfectly fine. The scan only points the verifier at sentences that *claim
strength* so that an **unsupported** one becomes a ``consistency`` debt. This is
advisory, exactly like the intro banned-phrase scan: it never rewrites.

Each rule carries the evidence the word requires (per APW's claim-strength
table) and the suggested downgrade when that evidence is absent.
"""
from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path

from research_assistant.papers.placeholders import _strip_tex_comment, _tex_sources


@dataclass(frozen=True)
class StrengthRule:
    pattern: re.Pattern[str]
    category: str
    required: str       # evidence the word demands
    downgrade: str      # weaker phrasing to use when evidence is absent


def _rule(words: str, category: str, required: str, downgrade: str) -> StrengthRule:
    # `words` is an alternation body, matched whole-word, case-insensitively.
    # Hyphen/space variants (e.g. "state-of-the-art") are embedded literally.
    return StrengthRule(
        pattern=re.compile(rf"(?<![\w-])(?:{words})(?![\w-])", re.IGNORECASE),
        category=category,
        required=required,
        downgrade=downgrade,
    )


# Order matters only for stable reporting; each rule is independent.
STRENGTH_RULES: tuple[StrengthRule, ...] = (
    _rule(
        r"significantly|significant",
        "significance",
        "a significance test (p<0.05) or an effect size",
        "state the concrete numerical difference instead",
    ),
    _rule(
        r"robust|robustly|robustness",
        "robustness",
        "multiple seeds / cross-validation / an external test set",
        "scope it to 'consistent within the observed setting'",
    ),
    _rule(
        r"demonstrates?|demonstrated",
        "demonstration",
        "a fully reproduced result with no protocol gaps",
        "downgrade to 'suggests' / 'aligns with'",
    ),
    _rule(
        r"generali[sz]e|generali[sz]es|generali[sz]ation",
        "generalization",
        "an independent or multi-dataset test set",
        "restrict the claim to the evaluated dataset",
    ),
    _rule(
        r"state-of-the-art|state of the art|SOTA",
        "sota",
        "a complete baseline comparison on an independent test set",
        "qualify as 'within the compared scope'",
    ),
    _rule(
        r"proves?|proved|proven",
        "proof",
        "a formal proof or exhaustive empirical evidence",
        "downgrade to 'show' / 'provide evidence that'",
    ),
)


@dataclass(frozen=True)
class StrengthHit:
    """One high-risk strength word found in the prose."""

    word: str           # the matched surface text
    category: str       # significance / robustness / demonstration / …
    file: str           # path relative to the direction dir (POSIX)
    line: int           # 1-based line number
    required: str       # evidence the word demands
    downgrade: str      # suggested weaker phrasing


def scan_strength_words(direction_dir: Path) -> list[StrengthHit]:
    """Scan a direction's ``.tex`` prose for over-strong wording.

    Comment-only occurrences (after an un-escaped ``%``) are ignored so the
    Chinese-translation comment above a paragraph never inflates the count.
    Results are ordered by (file, line, rule) for deterministic output.
    """
    direction_path = Path(direction_dir)
    if not direction_path.is_dir():
        return []

    hits: list[StrengthHit] = []
    for tex in _tex_sources(direction_path):
        try:
            text = tex.read_text(encoding="utf-8")
        except OSError:
            continue
        rel = tex.relative_to(direction_path).as_posix()
        for lineno, raw_line in enumerate(text.splitlines(), start=1):
            stripped = _strip_tex_comment(raw_line)
            for rule in STRENGTH_RULES:
                for m in rule.pattern.finditer(stripped):
                    hits.append(
                        StrengthHit(
                            word=m.group(0),
                            category=rule.category,
                            file=rel,
                            line=lineno,
                            required=rule.required,
                            downgrade=rule.downgrade,
                        )
                    )
    hits.sort(key=lambda h: (h.file, h.line, h.category))
    return hits
