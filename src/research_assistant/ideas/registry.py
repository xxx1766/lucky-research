"""Idea persistence — manifest, registry, AgentDB mirror.

The on-disk manifest at ``outputs/idea-checks/<slug>/idea.md`` is the source of
truth. The AgentDB entry at namespace ``ideas`` key ``<slug>`` mirrors it for
semantic search; if AgentDB is wiped, :func:`reindex_from_disk` rebuilds it.

A global index at ``outputs/idea-checks/_index.md`` lists every captured idea
so ``/idea-check list`` can scan the vault without walking subdirectories.

Frontmatter format is plain YAML, matching the conventions of
``inputs/past-work/<slug>.md`` and ``outputs/experiments/<slug>/manifest.md``.
"""
from __future__ import annotations

import re
from datetime import date
from pathlib import Path
from typing import Literal

import yaml
from pydantic import BaseModel, Field

from research_assistant.common.io import IDEA_CHECKS_DIR

IdeaStatus = Literal[
    "captured",
    "scouted",
    "evaluated",
    "venued",
    "knowledge-indexed",
    "handed-off",
]

STATUS_ORDER: tuple[IdeaStatus, ...] = (
    "captured",
    "scouted",
    "evaluated",
    "venued",
    "knowledge-indexed",
    "handed-off",
)

_SLUG_RE = re.compile(r"^[a-z0-9][a-z0-9-]*$")
_FRONTMATTER_RE = re.compile(r"^---\s*\n(.*?)\n---\s*\n?(.*)$", re.DOTALL)


def _validate_slug(slug: str) -> str:
    if not slug or not _SLUG_RE.match(slug):
        raise ValueError(f"invalid idea slug: {slug!r}")
    return slug


class IdeaManifest(BaseModel):
    """The persisted shape of one idea."""

    slug: str
    created: date
    updated: date
    statement: str
    area_tags: list[str] = Field(default_factory=list)
    status: IdeaStatus = "captured"
    venue: str | None = None
    verdict: str | None = None
    body: str = ""

    def with_status(self, new_status: IdeaStatus) -> "IdeaManifest":
        """Return a copy with status advanced (never regresses)."""
        if STATUS_ORDER.index(new_status) < STATUS_ORDER.index(self.status):
            return self
        return self.model_copy(update={"status": new_status, "updated": date.today()})


def idea_dir(slug: str) -> Path:
    """Resolve ``outputs/idea-checks/<slug>/``. Slug-validated."""
    return IDEA_CHECKS_DIR / _validate_slug(slug)


def manifest_path(slug: str) -> Path:
    return idea_dir(slug) / "idea.md"


def index_path() -> Path:
    return IDEA_CHECKS_DIR / "_index.md"


def _render_manifest_md(m: IdeaManifest) -> str:
    fm = {
        "slug": m.slug,
        "created": m.created.isoformat(),
        "updated": m.updated.isoformat(),
        "status": m.status,
        "area_tags": list(m.area_tags),
        "statement": m.statement,
    }
    if m.venue:
        fm["venue"] = m.venue
    if m.verdict:
        fm["verdict"] = m.verdict
    body = m.body.strip()
    head = yaml.safe_dump(fm, sort_keys=False, allow_unicode=True).strip()
    parts = [f"---\n{head}\n---", "", f"# {m.statement}", ""]
    if body:
        parts.append(body)
    return "\n".join(parts).rstrip() + "\n"


def _parse_manifest_md(text: str) -> IdeaManifest:
    m = _FRONTMATTER_RE.match(text)
    if not m:
        raise ValueError("manifest missing YAML frontmatter")
    fm = yaml.safe_load(m.group(1)) or {}
    body = m.group(2).strip()
    if body.startswith("# "):
        body = body.split("\n", 1)[1] if "\n" in body else ""
    return IdeaManifest(
        slug=fm["slug"],
        created=date.fromisoformat(str(fm["created"])),
        updated=date.fromisoformat(str(fm["updated"])),
        statement=str(fm.get("statement", "")),
        area_tags=list(fm.get("area_tags") or []),
        status=fm.get("status", "captured"),
        venue=fm.get("venue"),
        verdict=fm.get("verdict"),
        body=body.strip(),
    )


def save_idea(manifest: IdeaManifest) -> Path:
    """Write the manifest to disk AND refresh ``_index.md``.

    AgentDB mirroring is the caller's job — the skill prompt invokes
    ``mcp__claude-flow__memory_store`` with :func:`to_agentdb_payload`.
    """
    _validate_slug(manifest.slug)
    d = idea_dir(manifest.slug)
    d.mkdir(parents=True, exist_ok=True)
    path = manifest_path(manifest.slug)
    path.write_text(_render_manifest_md(manifest), encoding="utf-8")
    _rewrite_index()
    return path


def load_idea(slug: str) -> IdeaManifest:
    path = manifest_path(slug)
    if not path.is_file():
        raise FileNotFoundError(f"no manifest for idea {slug!r}")
    return _parse_manifest_md(path.read_text(encoding="utf-8"))


def update_idea(slug: str, **fields) -> IdeaManifest:
    """Partial update — bumps ``updated``, rewrites file + index, returns the new manifest.

    ``status`` is monotonically forward via :meth:`IdeaManifest.with_status`.
    """
    current = load_idea(slug)
    new_status = fields.pop("status", None)
    updated = current.model_copy(update={**fields, "updated": date.today()})
    if new_status:
        updated = updated.with_status(new_status)
    save_idea(updated)
    return updated


def list_ideas() -> list[IdeaManifest]:
    """Walk ``outputs/idea-checks/*/idea.md``, sorted by ``updated`` desc."""
    if not IDEA_CHECKS_DIR.is_dir():
        return []
    out: list[IdeaManifest] = []
    for sub in sorted(IDEA_CHECKS_DIR.iterdir()):
        if not sub.is_dir() or sub.name.startswith("_"):
            continue
        path = sub / "idea.md"
        if not path.is_file():
            continue
        try:
            out.append(_parse_manifest_md(path.read_text(encoding="utf-8")))
        except (ValueError, KeyError):
            continue  # malformed; skip silently so the registry stays usable
    out.sort(key=lambda m: m.updated, reverse=True)
    return out


def render_index_md(manifests: list[IdeaManifest]) -> str:
    """Render the global index."""
    lines = ["# Ideas vault", ""]
    if not manifests:
        lines.append("_(no ideas captured yet — try `/idea-check <your idea>`)_")
        return "\n".join(lines) + "\n"
    lines.append("| Slug | Status | Updated | Venue | Verdict | Statement |")
    lines.append("|---|---|---|---|---|---|")
    for m in manifests:
        statement = m.statement.replace("|", "\\|")
        if len(statement) > 80:
            statement = statement[:77] + "…"
        lines.append(
            f"| `{m.slug}` | {m.status} | {m.updated.isoformat()} | "
            f"{m.venue or '—'} | {m.verdict or '—'} | {statement} |"
        )
    lines.append("")
    return "\n".join(lines) + "\n"


def _rewrite_index() -> None:
    IDEA_CHECKS_DIR.mkdir(parents=True, exist_ok=True)
    index_path().write_text(render_index_md(list_ideas()), encoding="utf-8")


def to_agentdb_payload(manifest: IdeaManifest) -> dict:
    """Payload for ``mcp__claude-flow__memory_store namespace=ideas, key=<slug>``."""
    return {
        "slug": manifest.slug,
        "created": manifest.created.isoformat(),
        "updated": manifest.updated.isoformat(),
        "statement": manifest.statement,
        "area_tags": list(manifest.area_tags),
        "status": manifest.status,
        "venue": manifest.venue,
        "verdict": manifest.verdict,
    }


def reindex_from_disk() -> list[IdeaManifest]:
    """Re-emit every manifest as an AgentDB payload (caller wires the store call).

    Used after ``ruvector.db`` is deleted: the on-disk manifest survives, and
    this helper returns the list of payloads the caller (skill prompt) can
    feed back into ``mcp__claude-flow__memory_store``.
    """
    return list_ideas()
