"""Pydantic models for pseudocode-tool: PseudocodeNote.

Source of truth on disk:
  * <slug>.note.md per generated algorithm (YAML frontmatter parses into PseudocodeNote)
"""
from __future__ import annotations

from datetime import date
from typing import Literal

from pydantic import BaseModel, Field


PseudocodeKind = Literal["unified", "train", "inference", "preprocess"]
PseudocodeScope = Literal["paper", "experiment"]
PseudocodePackage = Literal["algpseudocode", "algorithm2e"]


class PseudocodeNote(BaseModel):
    """Frontmatter of <slug>.note.md next to every generated algorithm."""

    slug: str
    kind: PseudocodeKind
    scope: PseudocodeScope
    anchor: str            # papers/<v>/<d> or experiments/<exp>/<vN.M>
    intent: str
    package: PseudocodePackage
    inputs: list[str] = Field(default_factory=list)
    outputs: list[str] = Field(default_factory=list)
    complexity_time: str | None = None    # raw LaTeX-math, e.g. "O(B L d^2)"
    complexity_space: str | None = None
    notation_used: list[str] = Field(default_factory=list)
    refs: list[str] = Field(default_factory=list)
    created: date
