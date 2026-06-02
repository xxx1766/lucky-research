"""Quick-capture helpers for ``/mentor add-past-work``.

Split out of :mod:`research_assistant.mentor.past_work` to keep that module
under the project's 500-line rule. The two public entry points are
:func:`quick_capture_defaults` (smart defaults for an in-flow capture) and
:func:`compose_past_work_entry` (template-driven writer). Both are
re-exported from :mod:`research_assistant.mentor.past_work` so existing
callers don't change.
"""
from __future__ import annotations

from datetime import date
from pathlib import Path

from research_assistant.mentor.past_work import (
    _write_frontmatter,
    entry_path,
    next_available_slug,
    slugify,
)


def quick_capture_defaults(title: str, *, today: date | None = None) -> dict:
    """Smart defaults for a fast in-flow past-work capture.

    Used by ``/mentor add-past-work`` so the user can drop a single
    title in the middle of a check-in and get back a ready-to-write entry
    dict — no follow-up Q&A unless they want to enrich it. Caller can
    override any field before passing into :func:`compose_past_work_entry`.

    Defaults reflect the typical "I just remembered this old project; log
    it before I forget" intent:

    * ``slug`` — collision-safe slug from the title.
    * ``year`` — calendar year of ``today`` (UTC).
    * ``venue`` — ``"internal"`` (matches ``in-progress``).
    * ``status`` — ``"in-progress"`` (the user is *recalling* it, not
      published; if it was published they'd say so explicitly).
    * ``tags``, ``links``, ``what_i_learned`` — empty lists.
    * ``abstract`` / ``methods_used`` / ``outcome`` / ``notes_for_future``
      — ``None`` so :func:`compose_past_work_entry` writes a ``_TODO_``
      placeholder the user can fill in later.
    """
    reference = today or date.today()
    return {
        "slug": next_available_slug(slugify(title)),
        "title": title,
        "year": reference.year,
        "venue": "internal",
        "status": "in-progress",
        "tags": [],
        "links": [],
        "abstract": None,
        "what_i_learned": [],
        "methods_used": None,
        "outcome": None,
        "notes_for_future": None,
    }


def _emit_body_section(
    heading: str, content: str | None | list[str], *, placeholder: str
) -> str:
    """Render one Markdown section of a past-work entry body.

    Lists become bullet lines; strings become a single paragraph; ``None``
    or empty becomes ``_TODO_: <placeholder>`` so the user sees what's
    missing when they open the file.
    """
    if isinstance(content, list):
        rendered = (
            "\n".join(f"- {item}" for item in content if item)
            or f"- _TODO_: {placeholder}"
        )
    elif content:
        rendered = content.strip()
    else:
        rendered = f"_TODO_: {placeholder}"
    return f"## {heading}\n\n{rendered}\n"


def compose_past_work_entry(
    *,
    slug: str,
    title: str,
    year: int | None = None,
    venue: str | None = None,
    status: str | None = None,
    tags: list[str] | None = None,
    links: list[str] | None = None,
    abstract: str | None = None,
    what_i_learned: list[str] | None = None,
    methods_used: str | None = None,
    outcome: str | None = None,
    notes_for_future: str | None = None,
    force: bool = False,
) -> Path:
    """Write ``inputs/past-work/<slug>.md`` from structured fields.

    Used by ``/mentor add-past-work`` (and any other in-flow capture
    site) so the skill prompt doesn't have to do template substitution
    itself. The on-disk shape matches ``docs/past-work-template.md`` so
    existing readers (``past-work-historian`` agent, ``parse_entry``) work
    unchanged.

    Refuses to overwrite an existing entry unless ``force=True`` — the
    raised :class:`FileExistsError` points the caller at
    :func:`next_available_slug` for a collision-free alternative. The
    user-facing ``/mentor add-past-work`` flow uses
    :func:`quick_capture_defaults` (which already calls
    ``next_available_slug``) so the error path is mostly defensive.
    """
    path = entry_path(slug)
    if path.exists() and not force:
        raise FileExistsError(
            f"past-work entry already exists at {path}; "
            "pick a different slug or pass force=True"
        )
    fm: dict = {"slug": slug, "title": title}
    if year is not None:
        fm["year"] = year
    if venue is not None:
        fm["venue"] = venue
    if status is not None:
        fm["status"] = status
    fm["tags"] = list(tags or [])
    fm["links"] = list(links or [])
    body = (
        f"# {title}\n\n"
        + _emit_body_section(
            "Abstract", abstract,
            placeholder="one-paragraph summary of what the project was about",
        )
        + "\n"
        + _emit_body_section(
            "What I learned", what_i_learned,
            placeholder="one-line lesson",
        )
        + "\n"
        + _emit_body_section(
            "Methods used", methods_used,
            placeholder="datasets, models, tools, training recipe",
        )
        + "\n"
        + _emit_body_section(
            "Outcome / impact", outcome,
            placeholder="published? cited? abandoned and why? blocked X downstream?",
        )
        + "\n"
        + _emit_body_section(
            "Notes for future-me", notes_for_future,
            placeholder="if I revisit, start from commit ...",
        )
    )
    _write_frontmatter(path, fm, "\n" + body)
    return path
