"""Reference-figure library — inputs/figure-refs/<slug>/ intake + AgentDB payload.

The Python helpers are filesystem-only. AgentDB upsert is performed by the
skill MD via `mcp__claude-flow__memory_store`, using the dict returned by
:func:`to_agentdb_payload`.
"""
from __future__ import annotations

import shutil
from pathlib import Path

import yaml

from research_assistant.common.frontmatter import parse as parse_fm
from research_assistant.common.io import FIGURE_REFS_DIR
from research_assistant.figures.schema import FigureRef

_STAGING_NAME = "staging"


def add_ref(image_path: Path, ref: FigureRef, *, force: bool = False) -> Path:
    """Materialise inputs/figure-refs/<slug>/ from the image + parsed metadata.

    Returns the entry directory. Raises FileExistsError on conflict unless
    force=True.
    """
    if not image_path.exists():
        raise FileNotFoundError(image_path)
    entry_dir = FIGURE_REFS_DIR / ref.slug
    if entry_dir.exists():
        if not force:
            raise FileExistsError(entry_dir)
        shutil.rmtree(entry_dir)
    entry_dir.mkdir(parents=True)
    target_image = entry_dir / f"image{image_path.suffix.lower()}"
    shutil.copy2(image_path, target_image)
    _write_note(entry_dir / "note.md", ref)
    return entry_dir


def read_ref(slug: str) -> FigureRef:
    """Parse inputs/figure-refs/<slug>/note.md back into a FigureRef."""
    note_path = FIGURE_REFS_DIR / slug / "note.md"
    fm, _body = parse_fm(note_path)
    return FigureRef.model_validate(fm)


def list_refs() -> list[str]:
    """Return all reference slugs (excluding the staging/ drop-zone)."""
    if not FIGURE_REFS_DIR.is_dir():
        return []
    return sorted(
        p.name
        for p in FIGURE_REFS_DIR.iterdir()
        if p.is_dir() and p.name != _STAGING_NAME
    )


def to_agentdb_payload(ref: FigureRef) -> dict:
    """Format a FigureRef for ``mcp__claude-flow__memory_store(**payload)``.

    The ``value`` field is the embeddable string that vector search runs over —
    matches the contract used by every other ``*_to_agentdb_payload`` helper
    in the codebase (experiments, migrate, mentor, ideas).
    """
    value = " | ".join([
        f"source: {ref.source}",
        f"kind: {ref.kind}",
        f"tags: {', '.join(ref.tags)}" if ref.tags else "tags: (none)",
        f"why_i_like_it: {ref.why_i_like_it}",
    ])
    return {
        "namespace": "project/figure-refs",
        "key": ref.slug,
        "value": value,
        "metadata": {
            "source": ref.source,
            "kind": ref.kind,
            "tags": ref.tags,
            "palette": ref.palette,
        },
    }


def _write_note(path: Path, ref: FigureRef) -> None:
    payload = ref.model_dump(mode="json")
    yaml_text = yaml.safe_dump(payload, sort_keys=False, allow_unicode=True).rstrip("\n")
    path.write_text(f"---\n{yaml_text}\n---\n", encoding="utf-8")
