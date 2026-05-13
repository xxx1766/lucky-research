"""Read/write per-figure <slug>.note.md (YAML frontmatter + free body)."""
from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path

import yaml

from research_assistant.figures.schema import FigureNote

_FM_RE = re.compile(r"^---\n(.*?)\n---\n?(.*)$", re.DOTALL)


@dataclass
class LoadedNote:
    note: FigureNote
    body: str


def write_note(path: Path, note: FigureNote, *, body: str = "") -> None:
    """Write a <slug>.note.md atomically. Overwrites if present."""
    payload = note.model_dump(mode="json")
    yaml_text = yaml.safe_dump(payload, sort_keys=False, allow_unicode=True).rstrip("\n")
    text = f"---\n{yaml_text}\n---\n"
    if body:
        text += f"\n{body.rstrip()}\n"
    path.write_text(text, encoding="utf-8")


def read_note(path: Path) -> LoadedNote:
    """Parse a <slug>.note.md into a typed LoadedNote."""
    text = path.read_text(encoding="utf-8")
    m = _FM_RE.match(text)
    if not m:
        raise ValueError(f"{path} has no YAML frontmatter")
    fm = yaml.safe_load(m.group(1)) or {}
    note = FigureNote.model_validate(fm)
    body = m.group(2).strip()
    return LoadedNote(note=note, body=body)
