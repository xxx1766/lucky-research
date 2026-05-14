"""Read/write per-algorithm <slug>.note.md (YAML frontmatter + free body)."""
from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path

import yaml

from research_assistant.pseudocode.schema import PseudocodeNote

_FM_RE = re.compile(r"^---\r?\n(.*?)\r?\n---\r?\n?(.*)$", re.DOTALL)


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
    path.write_text(text, encoding="utf-8")


def read_note(path: Path) -> LoadedNote:
    """Parse a <slug>.note.md into a typed LoadedNote."""
    text = path.read_text(encoding="utf-8")
    m = _FM_RE.match(text)
    if not m:
        raise ValueError(f"{path} has no YAML frontmatter")
    fm = yaml.safe_load(m.group(1)) or {}
    note = PseudocodeNote.model_validate(fm)
    body = m.group(2).lstrip("\r\n").rstrip()
    return LoadedNote(note=note, body=body)
