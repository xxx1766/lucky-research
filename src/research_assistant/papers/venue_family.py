"""Resolve a venue slug to its venue *family* (systems / nlp / cv / ml / db / ir).

The family layer sits above the per-cycle ``_venue.md`` (administrative
facts, deadlines, scoring rubric) and below the per-section heuristics —
it's where conventions that hold across an entire research community live.
A systems paper at OSDI '27 and the same lab's systems paper at SOSP '28
share methodology voice, results-section beats, and related-work clustering
style; that shared layer is what this resolver exposes to
``paper-architect``'s Stage 6.

Resolution order:

1. **Explicit override** — first ``Family: <name>`` line in the venue's
   ``_venue.md`` (case-insensitive, optional bullet/emphasis markers). Lets
   users pin a niche venue to the closest family without editing this map.
2. **Built-in prefix map** — match the head of ``<venue_slug>`` (the part
   before the first ``-`` or ``_``) case-insensitively against the
   registry. Covers the venues already in this group's working set.
3. **Fallback** — ``"default"`` so callers can degrade gracefully (no
   family-block prelude, just the default section heuristics).

Adding a venue is a one-line entry in :data:`_VENUE_FAMILY`. A new family
needs a matching ``## family: <name>`` block in
``.claude/skills/paper-architect/references/section-heuristics.md``;
otherwise the resolver returns the family name but ``/paper write`` has
nothing extra to layer on top of the default.
"""
from __future__ import annotations

import re

from research_assistant.papers import venue_path

_VENUE_FAMILY: dict[str, str] = {
    # systems — operating systems, distributed systems, networking, arch.
    # NOTE: bare "USENIX" deliberately omitted — `USENIX-Security-*` is not
    # a systems venue, and the genuinely systems-y USENIX co-locations
    # (OSDI, ATC, FAST, NSDI) are listed explicitly. Users targeting a
    # systems-flavored USENIX venue not in this map can add a
    # `Family: systems` line to their `_venue.md` (the explicit override is
    # honored before this prefix lookup).
    "OSDI": "systems", "SOSP": "systems", "NSDI": "systems",
    "EUROSYS": "systems", "ATC": "systems",
    "FAST": "systems", "ASPLOS": "systems", "MICRO": "systems",
    "ISCA": "systems", "HPCA": "systems", "MLSYS": "systems",
    "SIGCOMM": "systems", "SOCC": "systems",

    # nlp — language, dialogue, IR-adjacent NLP.
    "ACL": "nlp", "EMNLP": "nlp", "NAACL": "nlp", "TACL": "nlp",
    "COLING": "nlp", "EACL": "nlp", "AACL": "nlp",

    # cv — vision, multi-modal vision.
    "CVPR": "cv", "ICCV": "cv", "ECCV": "cv", "BMVC": "cv",
    "WACV": "cv", "3DV": "cv",

    # ml — general machine learning, learning theory.
    "ICML": "ml", "NEURIPS": "ml", "NIPS": "ml", "ICLR": "ml",
    "UAI": "ml", "AISTATS": "ml", "COLT": "ml",

    # db — databases, query processing.
    "VLDB": "db", "SIGMOD": "db", "ICDE": "db", "PODS": "db",
    "EDBT": "db",

    # ir — information retrieval, web, search.
    "SIGIR": "ir", "WWW": "ir", "WSDM": "ir", "CIKM": "ir",
    "RECSYS": "ir",
}

_VALID_FAMILIES: frozenset[str] = frozenset(_VENUE_FAMILY.values()) | {"default"}

# `Family:` line in _venue.md — tolerates bullets and emphasis markers so a
# user can write any of:
#   Family: systems
#   - Family: nlp
#   **Family**: cv
_FAMILY_LINE = re.compile(
    r"^\s*(?:[-*]\s+)?(?:[*_]+)?\s*family\s*(?:[*_]+)?\s*:\s*([A-Za-z]+)\s*$",
    re.IGNORECASE,
)


def family_for_venue(venue_slug: str) -> str:
    """Return the venue family for ``venue_slug``.

    See module docstring for the resolution order.
    """
    if not venue_slug:
        return "default"
    # 1) explicit override in _venue.md (first ~50 lines is enough for any
    # sensible placement; reading the whole file is wasteful and lets the
    # user's body text false-match on the regex).
    md = venue_path(venue_slug) / "_venue.md"
    if md.is_file():
        try:
            text = md.read_text(errors="replace")
        except OSError:
            text = ""
        for line in text.splitlines()[:50]:
            m = _FAMILY_LINE.match(line)
            if m:
                candidate = m.group(1).lower()
                if candidate in _VALID_FAMILIES:
                    return candidate
    # 2) built-in prefix map — take the head before the first ``-`` / ``_``,
    # match case-insensitively.
    head = re.split(r"[-_]", venue_slug, maxsplit=1)[0].upper()
    return _VENUE_FAMILY.get(head, "default")
