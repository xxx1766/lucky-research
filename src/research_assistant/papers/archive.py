"""``/paper archive`` — move a finished direction under ``inputs/past-work/``.

A paper's full ``<venue>/<direction>/`` tree (main.tex, sections/, refs.bib,
main.pdf, status.md, related-papers/, figures/, algorithms/, experiments/,
focused-problem.md, outline.md, expert.md) is moved to:

    inputs/past-work/<slug>/paper/

and a companion ``inputs/past-work/<slug>.md`` past-work entry is auto-created
(or merged with an existing stub). The two together let the
``past-work-historian`` agent surface this paper during future
``/idea-check`` and ``/paper direction`` recalls.

Venue-level siblings (``_venue.md``, ``_template/``, ``_venue-refs/``) stay
under ``outputs/papers/<venue>/`` since they're shared across all directions
in that venue.

Refuses on symlink directions: a paper bound to an experiment repo via
``/paper bind`` lives inside that repo; archiving the symlink would break it.
The user must run ``/paper unbind`` first.
"""
from __future__ import annotations

import re
import shutil
from dataclasses import dataclass
from datetime import date
from pathlib import Path

import yaml

from research_assistant.common.io import PAST_WORK_DIR
from research_assistant.mentor.past_work import (
    PastWorkRepo,
    companion_dir,
    entry_path,
    next_available_slug,
    paper_dir,
    slugify,
)
from research_assistant.papers import direction_path

_FM_RE = re.compile(r"^---\r?\n(.*?)\r?\n---\r?\n?(.*)$", re.DOTALL)
_TITLE_RE = re.compile(r"\\title\s*\{([^{}]*)\}")
_ABSTRACT_RE = re.compile(
    r"\\begin\{abstract\}(.*?)\\end\{abstract\}",
    re.DOTALL,
)


class ArchiveError(RuntimeError):
    """``/paper archive`` refused or failed."""


@dataclass(frozen=True)
class ArchiveResult:
    slug: str
    venue: str
    direction: str
    paper_dest: Path             # inputs/past-work/<slug>/paper/
    entry_path: Path             # inputs/past-work/<slug>.md
    entry_created: bool          # True if the .md was newly created; False if merged
    status: str                  # "published" | "abandoned"


# ---------- title / abstract extraction ----------

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


# ---------- past-work entry composition ----------

def _archive_body(
    *,
    title: str,
    venue: str,
    direction: str,
    archived_on: date,
    abstract: str | None,
    abandoned: bool,
) -> str:
    """Compose the body of the auto-created past-work .md.

    Kept close to ``docs/past-work-template.md`` so the historian can parse it
    later with the same heuristics.
    """
    abstract_section = (abstract.strip() if abstract else "<one-paragraph summary — fill in>")
    lead = (
        "Abandoned" if abandoned else "Archived"
    ) + f" from ``outputs/papers/{venue}/{direction}/`` on {archived_on.isoformat()}."
    return (
        f"\n# {title}\n\n"
        "## Abstract\n\n"
        f"{abstract_section}\n\n"
        "## What I learned\n\n"
        "- <one-line lesson 1>\n"
        "- <one-line lesson 2>\n\n"
        "## Methods used\n\n"
        "<datasets, models, tools — fill in from the archived paper>\n\n"
        "## Outcome / impact\n\n"
        f"{lead}\n\n"
        "Paper PDF: `./paper/main.pdf` (if rendered)\n\n"
        "## Notes for future-me\n\n"
        "- The full archived tree is at "
        "`inputs/past-work/<slug>/paper/`.\n"
    )


def _compose_frontmatter(
    *,
    slug: str,
    title: str,
    venue: str,
    direction: str,
    year: int,
    status: str,
    repo: PastWorkRepo | None,
    extra_links: list[str],
) -> dict:
    fm: dict = {
        "slug": slug,
        "title": title,
        "year": year,
        "venue": venue,
        "status": status,
        "tags": [],
        "links": [
            "paper:./paper/main.pdf",
            f"archived-from:outputs/papers/{venue}/{direction}",
            *extra_links,
        ],
    }
    if repo is not None:
        fm["repo"] = {
            k: v for k, v in repo.model_dump().items() if v is not None
        }
    return fm


def _merge_frontmatter(existing: dict, new: dict) -> dict:
    """Merge frontmatter dicts: existing user-written values win except for
    fields that are clearly empty/placeholders in the existing entry.

    Keys we always overwrite (because archive knows them definitively):
    ``status``, ``links`` (we append-and-dedupe rather than replace).
    """
    out = dict(existing)
    for key in ("slug", "title", "year", "venue"):
        if not out.get(key):
            out[key] = new.get(key)
    out["status"] = new.get("status", out.get("status"))
    existing_links = list(out.get("links") or [])
    merged_links: list[str] = list(dict.fromkeys([*existing_links, *new.get("links", [])]))
    out["links"] = merged_links
    if not out.get("tags") and new.get("tags") is not None:
        out["tags"] = new["tags"]
    if "repo" not in out and "repo" in new:
        out["repo"] = new["repo"]
    return out


def _write_past_work_md(
    md_path: Path, *, fm: dict, body: str, merge: bool,
) -> bool:
    """Write or merge the past-work entry. Returns True if newly created."""
    md_path.parent.mkdir(parents=True, exist_ok=True)
    if md_path.is_file() and merge:
        existing_text = md_path.read_text(encoding="utf-8")
        m = _FM_RE.match(existing_text)
        if m:
            try:
                existing_fm = yaml.safe_load(m.group(1)) or {}
            except yaml.YAMLError:
                existing_fm = {}
            existing_body = m.group(2)
        else:
            existing_fm = {}
            existing_body = existing_text
        merged_fm = _merge_frontmatter(existing_fm, fm)
        # Preserve the existing prose — archive runs late and the user may have
        # already started drafting a real entry; we only fill empty frontmatter
        # fields and append our own archive note as a trailing section.
        if existing_body.strip():
            combined_body = existing_body.rstrip() + "\n\n" + body.lstrip()
        else:
            combined_body = body
        _atomic_write_markdown(md_path, merged_fm, combined_body)
        return False
    _atomic_write_markdown(md_path, fm, body)
    return True


def _atomic_write_markdown(path: Path, fm: dict, body: str) -> None:
    yaml_text = yaml.safe_dump(fm, sort_keys=False, allow_unicode=True).rstrip("\n")
    leading = "" if body.startswith("\n") else "\n"
    path.write_text(f"---\n{yaml_text}\n---{leading}{body}", encoding="utf-8")


# ---------- status.md append ----------

def _append_archived_marker(paper_dest: Path, archived_on: date, abandoned: bool) -> None:
    """Append ``archived: <YYYY-MM-DD>`` to the moved ``status.md``.

    Creates the file if absent so the archive snapshot is self-describing even
    for papers that never ran ``/paper status``.
    """
    status_path = paper_dest / "status.md"
    marker = (
        f"\narchived: {archived_on.isoformat()}\n"
        f"archive-status: {'abandoned' if abandoned else 'published'}\n"
    )
    if status_path.is_file():
        existing = status_path.read_text(encoding="utf-8")
        if "archived:" in existing:
            return  # already marked — idempotent
        if not existing.endswith("\n"):
            existing += "\n"
        status_path.write_text(existing + marker, encoding="utf-8")
    else:
        status_path.write_text(
            f"# archive snapshot\n{marker}", encoding="utf-8",
        )


# ---------- public API ----------

def archive_direction(
    venue: str,
    direction: str,
    *,
    abandoned: bool = False,
    today: date | None = None,
) -> ArchiveResult:
    """Move ``outputs/papers/<venue>/<direction>/`` to
    ``inputs/past-work/<slug>/paper/`` and write/merge ``<slug>.md``.

    Returns the past-work :class:`ArchiveResult` (slug + paths + status).

    Refuses if:
    * ``<venue>/<direction>/`` is a symlink (paper is bound to an experiment
      repo — user must ``/paper unbind`` first).
    * The direction folder doesn't exist on disk.
    """
    today = today or date.today()
    src = direction_path(venue, direction)
    if src.is_symlink():
        raise ArchiveError(
            f"{src} is a symlink (bound to an experiment). Run `/paper unbind` first — "
            "archiving the symlink would break the link into the experiment repo."
        )
    if not src.exists():
        raise ArchiveError(f"no such direction on disk: {src}")
    if not src.is_dir():
        raise ArchiveError(f"{src} is not a directory")

    title = _extract_title(src) or f"{venue} / {direction}"
    abstract = _extract_abstract(src)
    experiment_slug = _read_experiment_binding(src)

    base_slug = slugify(f"{venue}-{direction}")
    slug = next_available_slug(base_slug)

    dest_root = companion_dir(slug)
    dest_root.mkdir(parents=True, exist_ok=True)
    dest_paper = paper_dir(slug)
    if dest_paper.exists():
        # Should be impossible because next_available_slug picks an empty slug,
        # but defend anyway — never silently clobber.
        raise ArchiveError(f"unexpected existing archive at {dest_paper}")
    shutil.move(str(src), str(dest_paper))
    _append_archived_marker(dest_paper, today, abandoned)

    status = "abandoned" if abandoned else "published"
    extra_links: list[str] = []
    if experiment_slug:
        extra_links.append(f"experiment:{experiment_slug}")
    fm = _compose_frontmatter(
        slug=slug,
        title=title,
        venue=venue,
        direction=direction,
        year=today.year,
        status=status,
        repo=None,  # User can /past-work bind <slug> <url> later
        extra_links=extra_links,
    )
    body = _archive_body(
        title=title,
        venue=venue,
        direction=direction,
        archived_on=today,
        abstract=abstract,
        abandoned=abandoned,
    )
    md_path = entry_path(slug)
    entry_created = _write_past_work_md(
        md_path, fm=fm, body=body, merge=True,
    )
    return ArchiveResult(
        slug=slug,
        venue=venue,
        direction=direction,
        paper_dest=dest_paper,
        entry_path=md_path,
        entry_created=entry_created,
        status=status,
    )


def unarchive_direction(slug: str) -> tuple[str, str]:
    """Reverse :func:`archive_direction`.

    Moves ``inputs/past-work/<slug>/paper/`` back to
    ``outputs/papers/<venue>/<direction>/``. Reads ``(venue, direction)`` from
    the moved ``expert.md`` frontmatter; falls back to parsing the slug
    (``<venue>-<direction>``) if expert.md is missing.

    The past-work ``<slug>.md`` is **left alone** — the user may want to keep
    it (with a "see archived paper at ..." pointer) or delete it manually.
    Returns ``(venue, direction)`` of the restored paper.
    """
    src_paper = paper_dir(slug)
    if not src_paper.is_dir():
        raise ArchiveError(f"no archived paper at {src_paper}")

    expert_text = ""
    expert = src_paper / "expert.md"
    if expert.is_file():
        expert_text = expert.read_text(encoding="utf-8", errors="replace")
    venue: str | None = None
    direction: str | None = None
    m = _FM_RE.match(expert_text)
    if m:
        try:
            fm = yaml.safe_load(m.group(1)) or {}
        except yaml.YAMLError:
            fm = {}
        venue = fm.get("venue") if isinstance(fm.get("venue"), str) else None
        direction = fm.get("direction") if isinstance(fm.get("direction"), str) else None
    if not venue or not direction:
        # Best-effort fallback: read the .md frontmatter
        md_path = entry_path(slug)
        if md_path.is_file():
            text = md_path.read_text(encoding="utf-8", errors="replace")
            mm = _FM_RE.match(text)
            if mm:
                try:
                    fm = yaml.safe_load(mm.group(1)) or {}
                except yaml.YAMLError:
                    fm = {}
                venue = venue or (fm.get("venue") if isinstance(fm.get("venue"), str) else None)
                # Heuristic: archive frontmatter has links like
                # "archived-from:outputs/papers/<venue>/<direction>"
                for link in fm.get("links") or []:
                    if isinstance(link, str) and link.startswith("archived-from:outputs/papers/"):
                        rest = link.split("archived-from:outputs/papers/", 1)[1]
                        parts = rest.split("/", 1)
                        if len(parts) == 2:
                            venue = venue or parts[0]
                            direction = direction or parts[1]
                            break
    if not venue or not direction:
        raise ArchiveError(
            f"could not resolve (venue, direction) for {slug!r} — "
            "expert.md / past-work entry frontmatter missing"
        )

    dest = direction_path(venue, direction)
    if dest.exists():
        raise ArchiveError(
            f"unarchive destination already exists: {dest} — "
            "delete or rename it first"
        )
    dest.parent.mkdir(parents=True, exist_ok=True)
    shutil.move(str(src_paper), str(dest))

    # If companion dir is now empty (no repo/ or notes/), clean it up.
    comp = companion_dir(slug)
    try:
        if comp.is_dir() and not any(comp.iterdir()):
            comp.rmdir()
    except OSError:
        pass

    return venue, direction


@dataclass(frozen=True)
class ArchivedPaper:
    slug: str
    venue: str | None
    direction: str | None
    title: str | None
    status: str | None
    archived_on: str | None
    has_pdf: bool


def list_archived() -> list[ArchivedPaper]:
    """Walk ``inputs/past-work/*/paper/`` and report each archived paper.

    Distinct from :func:`research_assistant.mentor.past_work.list_entries`,
    which lists *every* past-work entry (including external-project entries
    that have no ``paper/`` subdir).
    """
    if not PAST_WORK_DIR.is_dir():
        return []
    out: list[ArchivedPaper] = []
    for paper_subdir in sorted(PAST_WORK_DIR.glob("*/paper")):
        slug = paper_subdir.parent.name
        if slug.startswith("_") or slug.startswith("."):
            continue
        venue: str | None = None
        direction: str | None = None
        title: str | None = None
        archived_on: str | None = None
        status: str | None = None
        expert = paper_subdir / "expert.md"
        if expert.is_file():
            text = expert.read_text(encoding="utf-8", errors="replace")
            m = _FM_RE.match(text)
            if m:
                try:
                    fm = yaml.safe_load(m.group(1)) or {}
                except yaml.YAMLError:
                    fm = {}
                venue = fm.get("venue") if isinstance(fm.get("venue"), str) else venue
                direction = fm.get("direction") if isinstance(fm.get("direction"), str) else direction
                title = fm.get("title") if isinstance(fm.get("title"), str) else title
        # Read the past-work .md to enrich title/status/archived-on.
        md = entry_path(slug)
        if md.is_file():
            text = md.read_text(encoding="utf-8", errors="replace")
            m = _FM_RE.match(text)
            if m:
                try:
                    fm = yaml.safe_load(m.group(1)) or {}
                except yaml.YAMLError:
                    fm = {}
                title = title or (fm.get("title") if isinstance(fm.get("title"), str) else None)
                venue = venue or (fm.get("venue") if isinstance(fm.get("venue"), str) else None)
                status = fm.get("status") if isinstance(fm.get("status"), str) else status
        # archive marker from status.md
        status_path = paper_subdir / "status.md"
        if status_path.is_file():
            for line in status_path.read_text(encoding="utf-8", errors="replace").splitlines():
                if line.startswith("archived:"):
                    archived_on = line.split(":", 1)[1].strip()
                    break
        has_pdf = (paper_subdir / "main.pdf").is_file()
        out.append(
            ArchivedPaper(
                slug=slug,
                venue=venue,
                direction=direction,
                title=title,
                status=status,
                archived_on=archived_on,
                has_pdf=has_pdf,
            )
        )
    return out
