"""Past-work corpus helpers — schema + I/O + indexing contract + repo binding.

Past work lives at ``inputs/past-work/<slug>.md`` as the source of truth: each
file has YAML frontmatter matching :class:`PastWorkEntry` plus a free markdown
body. The ``past-work-historian`` agent mirrors them into AgentDB namespace
``project/past-work/<slug>`` so it can semantically recall relevant prior work
during /paper direction discussions.

A past-work entry can optionally bind to a GitHub repo. The companion folder
``inputs/past-work/<slug>/`` is created lazily and holds:

* ``repo/``  — shallow clone of the bound GitHub repo (``/past-work clone``).
* ``paper/`` — archived ``outputs/papers/<venue>/<direction>/`` tree
  (``/paper archive`` lands here).
* ``notes/`` — user-curated extras (slides, screenshots, datasets they want
  next to the code without polluting the repo).

Slug convention matches ``research_assistant.papers.slugify_direction`` —
kebab-case English, non-alphanumerics collapsed to hyphens.
"""
from __future__ import annotations

import re
import shutil
from datetime import date
from pathlib import Path
from typing import Literal

import yaml
from pydantic import BaseModel, Field

from research_assistant.common.git import (
    git_clone_shallow,
    git_ls_remote_sha,
    git_pull_ff_only,
    git_rev_parse_head,
    guard_under,
)
from research_assistant.common.io import PAST_WORK_DIR

_SLUG_CLEAN = re.compile(r"[^a-z0-9]+")
_FM_RE = re.compile(r"^---\r?\n(.*?)\r?\n---\r?\n?(.*)$", re.DOTALL)


# ---------- models ----------

class PastWorkRepo(BaseModel):
    """Optional GitHub binding for a past-work entry.

    Mirrors :class:`research_assistant.experiments.ExperimentRepo` so the same
    mental model carries across both modules.
    """
    url: str
    branch: str = "main"
    last_known_sha: str | None = None
    clone_status: Literal["tracked", "cloned", "missing"] = "tracked"
    cloned_at: str | None = None  # ISO date — populated on clone


class PastWorkEntry(BaseModel):
    slug: str
    title: str
    year: int | None = None
    venue: str | None = None
    status: str | None = None  # published | unpublished | abandoned | in-progress
    tags: list[str] = Field(default_factory=list)
    links: list[str] = Field(default_factory=list)
    repo: PastWorkRepo | None = None
    abstract: str | None = None
    what_i_learned: list[str] = Field(default_factory=list)
    body: str = ""


# ---------- slug + path helpers ----------

def slugify(title: str) -> str:
    """Build a kebab-case slug from a free-form title."""
    cleaned = _SLUG_CLEAN.sub("-", title.lower()).strip("-")
    if not cleaned:
        raise ValueError(f"empty past-work slug for title={title!r}")
    return cleaned


def next_available_slug(base: str) -> str:
    """Collision-safe variant. ``base`` -> ``base``, ``base-2``, ``base-3`` ...

    Checks the **companion folder** ``inputs/past-work/<slug>/`` only — the
    ``<slug>.md`` may already exist as a user-pre-created stub that the caller
    intends to merge into (this is how ``/paper archive`` lands metadata on top
    of any prose the user already wrote).

    Callers that need to avoid clobbering an existing ``.md`` (e.g.
    ``/past-work add``) should additionally check :func:`entry_path` themselves.
    """
    if not base:
        raise ValueError("empty base slug")

    def free(name: str) -> bool:
        return not (PAST_WORK_DIR / name).exists()

    if free(base):
        return base
    n = 2
    while not free(f"{base}-{n}"):
        n += 1
    return f"{base}-{n}"


def entry_path(slug: str) -> Path:
    """Resolve ``inputs/past-work/<slug>.md``. Path-traversal guarded."""
    if not slug:
        raise ValueError("empty past-work slug")
    candidate = PAST_WORK_DIR / f"{slug}.md"
    guard_under(PAST_WORK_DIR, candidate, "past-work slug")
    return candidate


def companion_dir(slug: str) -> Path:
    """Resolve ``inputs/past-work/<slug>/``. Path-traversal guarded.

    The companion dir holds ``repo/``, ``paper/``, and ``notes/`` — created
    lazily on first use, never present for prose-only entries.
    """
    if not slug:
        raise ValueError("empty past-work slug")
    candidate = PAST_WORK_DIR / slug
    guard_under(PAST_WORK_DIR, candidate, "past-work slug")
    return candidate


def repo_dir(slug: str) -> Path:
    """Resolve ``inputs/past-work/<slug>/repo/``. Path-traversal guarded."""
    return companion_dir(slug) / "repo"


def paper_dir(slug: str) -> Path:
    """Resolve ``inputs/past-work/<slug>/paper/`` (archived-paper tree)."""
    return companion_dir(slug) / "paper"


def notes_dir(slug: str) -> Path:
    """Resolve ``inputs/past-work/<slug>/notes/``."""
    return companion_dir(slug) / "notes"


def list_entries() -> list[Path]:
    """Return all past-work markdown files (excluding underscore-prefixed scratches)."""
    if not PAST_WORK_DIR.is_dir():
        return []
    return sorted(
        p for p in PAST_WORK_DIR.glob("*.md") if not p.name.startswith("_")
    )


# ---------- frontmatter I/O ----------

def _read_frontmatter(path: Path) -> tuple[dict, str]:
    """Read a markdown file; return ``(frontmatter_dict, body)``."""
    if not path.is_file():
        return {}, ""
    text = path.read_text(encoding="utf-8")
    m = _FM_RE.match(text)
    if not m:
        return {}, text
    fm = yaml.safe_load(m.group(1)) or {}
    return fm, m.group(2)


def _write_frontmatter(path: Path, fm: dict, body: str) -> None:
    yaml_text = yaml.safe_dump(fm, sort_keys=False, allow_unicode=True).rstrip("\n")
    leading = "" if body.startswith("\n") else "\n"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(f"---\n{yaml_text}\n---{leading}{body}", encoding="utf-8")


def read_repo_block(slug: str) -> PastWorkRepo | None:
    """Return the ``repo:`` block from the entry frontmatter, or ``None``."""
    fm, _ = _read_frontmatter(entry_path(slug))
    raw = fm.get("repo")
    if not raw or not isinstance(raw, dict) or not raw.get("url"):
        return None
    return PastWorkRepo(**{k: raw.get(k) for k in PastWorkRepo.model_fields if k in raw})


def write_repo_block(slug: str, repo: PastWorkRepo | None) -> None:
    """Write or strip the ``repo:`` frontmatter block on ``inputs/past-work/<slug>.md``."""
    path = entry_path(slug)
    fm, body = _read_frontmatter(path)
    if repo is None:
        fm.pop("repo", None)
    else:
        fm["repo"] = {
            k: v for k, v in repo.model_dump().items() if v is not None
        }
    _write_frontmatter(path, fm, body)


# ---------- repo bind / clone / sync / pull / unbind ----------

class RepoBindError(RuntimeError):
    """``/past-work`` repo-binding failed."""


def bind_repo(slug: str, url: str, *, branch: str = "main") -> PastWorkRepo:
    """Write the ``repo:`` block to ``inputs/past-work/<slug>.md``.

    Does NOT clone. ``/past-work clone <slug>`` does the actual ``git clone``
    in a separate step (matches ``/experiment init`` + ``/experiment clone``).

    Existing ``repo:`` blocks are overwritten (idempotent: re-binding with the
    same URL is a no-op; binding a different URL replaces the old metadata but
    does NOT touch any already-existing clone — caller should run unbind first
    if they want a clean slate).
    """
    if not entry_path(slug).is_file():
        raise RepoBindError(
            f"no past-work entry at {entry_path(slug)} — run `/past-work add` first"
        )
    if not url.strip():
        raise ValueError("empty repo url")
    existing = read_repo_block(slug)
    clone_present = repo_dir(slug).is_dir()
    repo = PastWorkRepo(
        url=url,
        branch=branch,
        last_known_sha=existing.last_known_sha if existing and existing.url == url else None,
        clone_status="cloned" if clone_present and (not existing or existing.url == url) else "tracked",
        cloned_at=existing.cloned_at if existing and existing.url == url else None,
    )
    write_repo_block(slug, repo)
    return repo


def clone_repo(slug: str, *, force: bool = False) -> Path:
    """Shallow-clone the bound repo into ``inputs/past-work/<slug>/repo/``.

    Idempotent: refuses if the clone already exists unless ``force=True`` (then
    removes the existing clone first). Updates ``last_known_sha``, ``cloned_at``,
    and ``clone_status: cloned`` in the entry frontmatter.
    """
    repo = read_repo_block(slug)
    if repo is None:
        raise RepoBindError(
            f"no repo bound for {slug!r} — run `/past-work bind <slug> <url>` first"
        )
    dest = repo_dir(slug)
    if dest.exists():
        if not force:
            raise FileExistsError(
                f"clone destination already exists: {dest} (pass force=True to recreate)"
            )
        shutil.rmtree(dest)
    git_clone_shallow(dest, repo.url, repo.branch)
    sha = git_rev_parse_head(dest)
    repo = repo.model_copy(update={
        "last_known_sha": sha,
        "clone_status": "cloned",
        "cloned_at": date.today().isoformat(),
    })
    write_repo_block(slug, repo)
    return dest


def sync_repo(slug: str) -> dict:
    """``git ls-remote`` against the bound URL — refresh ``last_known_sha``.

    Network-only; doesn't pull. Returns the dict from
    :func:`research_assistant.common.git.git_ls_remote_sha` plus a ``drift``
    bool comparing remote vs the entry's ``last_known_sha``.
    """
    repo = read_repo_block(slug)
    if repo is None:
        raise RepoBindError(f"no repo bound for {slug!r}")
    result = git_ls_remote_sha(repo.url, repo.branch)
    remote = result["remote_sha"]
    drift = (remote != repo.last_known_sha) if (remote and repo.last_known_sha) else None
    if remote:
        write_repo_block(slug, repo.model_copy(update={"last_known_sha": remote}))
    return {**result, "drift": drift, "local_sha": repo.last_known_sha}


def pull_repo(slug: str) -> tuple[bool, str]:
    """``git pull --ff-only`` inside the clone; refresh ``last_known_sha``.

    Returns ``(ok, message)``. Updates the entry frontmatter on success.
    """
    repo = read_repo_block(slug)
    if repo is None:
        raise RepoBindError(f"no repo bound for {slug!r}")
    dest = repo_dir(slug)
    if not dest.is_dir():
        raise RepoBindError(
            f"no local clone at {dest} — run `/past-work clone {slug}` first"
        )
    ok, msg = git_pull_ff_only(dest)
    if ok:
        sha = git_rev_parse_head(dest)
        if sha:
            write_repo_block(slug, repo.model_copy(update={"last_known_sha": sha}))
    return ok, msg


def unbind_repo(slug: str, *, keep_clone: bool = False) -> None:
    """Remove the ``repo:`` block. Optionally delete the clone (default: yes).

    ``keep_clone=True`` leaves ``inputs/past-work/<slug>/repo/`` on disk for the
    user to inspect or rsync elsewhere before deleting manually.
    """
    if read_repo_block(slug) is None:
        raise RepoBindError(f"no repo bound for {slug!r}")
    write_repo_block(slug, None)
    if not keep_clone:
        dest = repo_dir(slug)
        if dest.is_dir():
            shutil.rmtree(dest)


# ---------- listing for /past-work list ----------

def list_entries_with_repo() -> list[tuple[Path, PastWorkRepo | None, bool]]:
    """Return ``[(entry_path, repo_block, has_paper_subdir), ...]`` for every
    past-work entry.

    ``has_paper_subdir`` flags entries whose companion folder contains a
    ``paper/`` subdir — these are archived papers (created by /paper archive),
    distinct from external-project entries which only ever have ``repo/``.
    """
    out: list[tuple[Path, PastWorkRepo | None, bool]] = []
    for p in list_entries():
        slug = p.stem
        try:
            repo = read_repo_block(slug)
        except Exception:
            repo = None
        has_paper = paper_dir(slug).is_dir()
        out.append((p, repo, has_paper))
    return out


# ---------- parser stubs (deferred — see boss_profile.parse_profile) ----------

def parse_entry(path: Path) -> PastWorkEntry:
    """Parse a past-work markdown file (YAML frontmatter + body) into a PastWorkEntry.

    Not implemented yet — real body lands with the first real /past-work add or sync.
    """
    raise NotImplementedError("YAML frontmatter parsing pending real /past-work bodies")


def to_agentdb_payload(entry: PastWorkEntry) -> dict:
    """Format a PastWorkEntry for ``mcp__claude-flow__memory_store``."""
    raise NotImplementedError("AgentDB indexing payload pending real /past-work sync")
