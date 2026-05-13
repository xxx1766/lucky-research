"""Pydantic models for figure-tool: FigureNote, FigureRef, PaletteSpec, FigureSize.

Source of truth on disk:
  * <slug>.note.md per generated figure (YAML frontmatter parses into FigureNote)
  * inputs/figure-refs/<slug>/note.md (parses into FigureRef)
  * src/research_assistant/figures/styles/palette/<name>.yml (parses into PaletteSpec)
"""
from __future__ import annotations

from datetime import date
from typing import Literal

from pydantic import BaseModel, Field, field_validator


FigureKind = Literal["structural", "data", "mixed"]
FigureScope = Literal["paper", "experiment"]
FigureBackend = Literal["raw-svg", "d2-scaffolded", "matplotlib"]
SizePreset = Literal[
    "single-column", "double-column-half", "double-column-full", "custom"
]


class FigureSize(BaseModel):
    width_in: float = Field(gt=0)
    height_in: float = Field(gt=0)
    preset: SizePreset


class FigureNote(BaseModel):
    """Frontmatter of <slug>.note.md next to every generated figure."""

    slug: str
    kind: FigureKind
    scope: FigureScope
    anchor: str   # papers/<v>/<d> or experiments/<exp>/v1.2
    intent: str
    size: FigureSize
    palette: str  # palette name (matches a PaletteSpec.name)
    refs: list[str] = Field(default_factory=list)
    backend: FigureBackend
    created: date

    @field_validator("kind")
    @classmethod
    def kind_excludes_mixed(cls, v: str) -> str:
        # Generated figures are either structural or data; "mixed" reserved for refs.
        if v == "mixed":
            raise ValueError("FigureNote.kind must be 'structural' or 'data'; 'mixed' is for FigureRef only")
        return v


class FigureRef(BaseModel):
    """Frontmatter of inputs/figure-refs/<slug>/note.md."""

    slug: str
    source: str
    kind: FigureKind   # structural | data | mixed
    tags: list[str] = Field(default_factory=list)
    palette: list[str] = Field(default_factory=list)   # hex colors
    why_i_like_it: str = ""


class PaletteSpec(BaseModel):
    """Palette loaded from styles/palette/<name>.yml."""

    name: str
    slots: dict[str, str]
    sequence: list[str]
    colorblind_safe: bool = False
    suggested_for: list[str] = Field(default_factory=list)
