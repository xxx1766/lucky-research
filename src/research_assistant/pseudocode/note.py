"""Read/write per-algorithm <slug>.note.md (YAML frontmatter + free body)."""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import yaml

from research_assistant.common.frontmatter import parse as parse_fm
from research_assistant.pseudocode.schema import PseudocodeNote


@dataclass
class LoadedNote:
    note: PseudocodeNote
    body: str


def write_note(path: Path, note: PseudocodeNote, *, body: str = "") -> None:
    """Write a <slug>.note.md. Overwrites if present."""
    payload = note.model_dump(mode="json")
    yaml_text = yaml.safe_dump(payload, sort_keys=False, allow_unicode=True).rstrip("\n")
    text = f"---\n{yaml_text}\n---\n"
    if body:
        text += f"\n{body.rstrip()}\n"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def read_note(path: Path) -> LoadedNote:
    """Parse a <slug>.note.md into a typed LoadedNote."""
    fm, body = parse_fm(path)
    note = PseudocodeNote.model_validate(fm)
    return LoadedNote(note=note, body=body.lstrip("\r\n").rstrip())
