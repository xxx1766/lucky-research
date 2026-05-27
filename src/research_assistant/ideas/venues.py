"""Venue recommendation registry + suggestion for `/idea-check venues`.

The curated registry is the baseline. If the user has already drafted
``outputs/papers/<venue>/_venue.md`` for any registry entry, that venue is
up-weighted in suggestions (the user has already done the homework for it).

Deadline months are nominal — `_venue.md` overrides the actual cycle the user
intends to target.
"""
from __future__ import annotations

from datetime import date

from pydantic import BaseModel, Field

from research_assistant.common.io import PAPERS_DIR


class Venue(BaseModel):
    """One row in the curated registry."""

    slug: str
    name: str
    area_tags: list[str]
    deadline_month: int = Field(ge=1, le=12)
    page_limit: int
    url: str | None = None
    notes: str = ""


VENUE_REGISTRY: list[Venue] = [
    # ----- Machine learning -----
    Venue(slug="neurips", name="NeurIPS", area_tags=["ml"],
          deadline_month=5, page_limit=9),
    Venue(slug="icml", name="ICML", area_tags=["ml"],
          deadline_month=1, page_limit=8),
    Venue(slug="iclr", name="ICLR", area_tags=["ml"],
          deadline_month=10, page_limit=9),
    Venue(slug="colm", name="COLM", area_tags=["ml", "nlp"],
          deadline_month=3, page_limit=9),
    Venue(slug="aistats", name="AISTATS", area_tags=["ml", "theory"],
          deadline_month=10, page_limit=8),
    # ----- NLP -----
    Venue(slug="acl", name="ACL", area_tags=["nlp", "ml"],
          deadline_month=2, page_limit=8),
    Venue(slug="emnlp", name="EMNLP", area_tags=["nlp"],
          deadline_month=6, page_limit=8),
    Venue(slug="naacl", name="NAACL", area_tags=["nlp"],
          deadline_month=12, page_limit=8),
    Venue(slug="eacl", name="EACL", area_tags=["nlp"],
          deadline_month=10, page_limit=8),
    # ----- Vision -----
    Venue(slug="cvpr", name="CVPR", area_tags=["cv"],
          deadline_month=11, page_limit=8),
    Venue(slug="iccv", name="ICCV", area_tags=["cv"],
          deadline_month=3, page_limit=8),
    Venue(slug="eccv", name="ECCV", area_tags=["cv"],
          deadline_month=3, page_limit=14),
    # ----- Systems -----
    Venue(slug="osdi", name="OSDI", area_tags=["sys"],
          deadline_month=12, page_limit=12),
    Venue(slug="sosp", name="SOSP", area_tags=["sys"],
          deadline_month=4, page_limit=12),
    Venue(slug="nsdi", name="NSDI", area_tags=["sys"],
          deadline_month=9, page_limit=12),
    Venue(slug="atc", name="USENIX ATC", area_tags=["sys"],
          deadline_month=1, page_limit=12),
    Venue(slug="eurosys", name="EuroSys", area_tags=["sys"],
          deadline_month=10, page_limit=14),
    Venue(slug="mlsys", name="MLSys", area_tags=["sys", "ml"],
          deadline_month=10, page_limit=10),
    Venue(slug="socc", name="SoCC", area_tags=["sys"],
          deadline_month=7, page_limit=14,
          notes="ACM Symposium on Cloud Computing — cloud / cluster / orchestration friendly; "
                "retrofit + measurement papers welcomed."),
    Venue(slug="asplos", name="ASPLOS", area_tags=["sys"],
          deadline_month=8, page_limit=14,
          notes="Architectural Support for Programming Languages and Operating Systems — "
                "cross-cuts arch / OS / PL / runtime; well-suited to runtime + GPU + "
                "systems-software co-design."),
    # ----- IR / Web / KDD -----
    Venue(slug="kdd", name="KDD", area_tags=["ml", "ir"],
          deadline_month=2, page_limit=9),
    Venue(slug="www", name="TheWebConf", area_tags=["ir", "ml"],
          deadline_month=10, page_limit=10),
    Venue(slug="sigir", name="SIGIR", area_tags=["ir"],
          deadline_month=1, page_limit=10),
    # ----- DB -----
    Venue(slug="vldb", name="VLDB", area_tags=["db"],
          deadline_month=3, page_limit=12),
    Venue(slug="sigmod", name="SIGMOD", area_tags=["db"],
          deadline_month=1, page_limit=12),
    # ----- Security -----
    Venue(slug="ccs", name="CCS", area_tags=["sec"],
          deadline_month=1, page_limit=12),
    Venue(slug="usenix-sec", name="USENIX Security", area_tags=["sec"],
          deadline_month=2, page_limit=13),
    Venue(slug="ndss", name="NDSS", area_tags=["sec"],
          deadline_month=7, page_limit=13),
    # ----- Theory -----
    Venue(slug="focs", name="FOCS", area_tags=["theory"],
          deadline_month=4, page_limit=12),
    Venue(slug="stoc", name="STOC", area_tags=["theory"],
          deadline_month=11, page_limit=10),
    # ----- HCI -----
    Venue(slug="chi", name="CHI", area_tags=["hci"],
          deadline_month=9, page_limit=12),
]


class VenueMatch(BaseModel):
    """One suggested venue + score + reason."""

    venue: Venue
    fit_score: int
    next_deadline: date | None = None
    is_user_curated: bool = False
    why_fit: str = ""


def _next_deadline_for_month(month: int, today: date) -> date:
    """Pick the next future occurrence of ``month`` (year-1 if already past)."""
    year = today.year if month >= today.month else today.year + 1
    return date(year, month, 1)


def _user_curated_venue_slugs() -> set[str]:
    """Walk ``outputs/papers/<venue>/_venue.md`` and return matching registry slugs."""
    if not PAPERS_DIR.is_dir():
        return set()
    curated: set[str] = set()
    registry_lookup = {v.slug.lower(): v.slug for v in VENUE_REGISTRY}
    registry_lookup.update({v.name.lower(): v.slug for v in VENUE_REGISTRY})
    for venue_dir in PAPERS_DIR.iterdir():
        if not venue_dir.is_dir():
            continue
        if not (venue_dir / "_venue.md").is_file():
            continue
        # Match either the venue dir name (e.g. "OSDI-2027" → "osdi") or its
        # leading alphabetic prefix.
        name_lower = venue_dir.name.lower()
        if name_lower in registry_lookup:
            curated.add(registry_lookup[name_lower])
            continue
        prefix = "".join(c for c in name_lower if c.isalpha())
        if prefix and prefix in registry_lookup:
            curated.add(registry_lookup[prefix])
    return curated


def suggest_venues(
    area_tags: list[str],
    today: date | None = None,
    top_k: int = 5,
) -> list[VenueMatch]:
    """Rank venues by area-tag overlap, with a boost for user-curated venues.

    The ``why_fit`` line names the matching tags. Deadlines are nominal and
    surfaced for prioritization, not as authoritative dates.
    """
    today = today or date.today()
    tag_set = {t.lower().strip() for t in area_tags if t and t.strip()}
    curated = _user_curated_venue_slugs()
    matches: list[VenueMatch] = []
    for v in VENUE_REGISTRY:
        overlap = sorted(set(v.area_tags) & tag_set)
        if not overlap:
            continue
        extras = len(set(v.area_tags) - tag_set)
        is_curated = v.slug in curated
        # Reward each matched tag, penalize unmatched extras (less-focused venues),
        # boost curated venues so user-touched ones float to the top.
        fit_score = len(overlap) * 3 - extras + (5 if is_curated else 0)
        why = f"matches {', '.join(overlap)}"
        if is_curated:
            why += "; you have a _venue.md for it"
        matches.append(
            VenueMatch(
                venue=v,
                fit_score=fit_score,
                next_deadline=_next_deadline_for_month(v.deadline_month, today),
                is_user_curated=is_curated,
                why_fit=why,
            )
        )
    matches.sort(key=lambda m: (-m.fit_score, m.next_deadline or date.max, m.venue.slug))
    return matches[:top_k]


def render_venues_md(matches: list[VenueMatch], area_tags: list[str]) -> str:
    """Render the matches to ``outputs/idea-checks/<slug>/venues.md``."""
    lines: list[str] = ["# Target venues", ""]
    lines.append(f"Area tags: `{', '.join(area_tags) or '(none)'}`")
    lines.append("")
    if not matches:
        lines.append("_No registry venues match these tags. Add a `_venue.md` under")
        lines.append("`outputs/papers/<venue>/` to curate one yourself, or broaden the tags._")
        return "\n".join(lines) + "\n"
    lines.append("| Rank | Venue | Next deadline | Page limit | Fit | Why |")
    lines.append("|---|---|---|---|---|---|")
    for i, m in enumerate(matches, start=1):
        deadline = m.next_deadline.isoformat() if m.next_deadline else "—"
        star = " ⭐" if m.is_user_curated else ""
        lines.append(
            f"| {i} | **{m.venue.name}**{star} | {deadline} | "
            f"{m.venue.page_limit} pp | {m.fit_score} | {m.why_fit} |"
        )
    lines.append("")
    lines.append("⭐ = you already have a `_venue.md` for this venue.")
    return "\n".join(lines) + "\n"
