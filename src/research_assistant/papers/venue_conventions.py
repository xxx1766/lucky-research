"""Typed schema + per-paper markdown (de)serialization for venue writing-style refs.

A `VenueRefAnalysis` captures the prose conventions distilled from one reference
paper. Persisted as `outputs/papers/<venue>/_venue-refs/<paper-slug>.md` —
YAML frontmatter is the round-trip source; the body below is a human-readable
rendering that may be regenerated.
"""

from __future__ import annotations

from pathlib import Path

import yaml
from pydantic import BaseModel, ConfigDict, Field


class SectionSpec(BaseModel):
    model_config = ConfigDict(extra="ignore")
    name: str
    order_index: int
    opening_pattern: str = ""
    tense: str = ""
    voice: str = ""
    canonical_sentence: str = ""


class CitationStyle(BaseModel):
    model_config = ConfigDict(extra="ignore")
    form: str = ""
    density_per_para: float | None = None
    integration_pattern: str = ""


class FigureRefStyle(BaseModel):
    model_config = ConfigDict(extra="ignore")
    figure_form: str = ""
    equation_form: str = ""


class ResultClaimStyle(BaseModel):
    model_config = ConfigDict(extra="ignore")
    hedging_vocab: list[str] = Field(default_factory=list)
    verbs: list[str] = Field(default_factory=list)
    quantification_pattern: str = ""


class FigureStyle(BaseModel):
    """Visual design conventions for figures (distinct from in-text reference form)."""

    model_config = ConfigDict(extra="ignore")
    typical_kinds: list[str] = Field(default_factory=list)
    column_span: str = ""           # "single" | "double" | "mixed"
    subfigures: bool = False
    caption_pattern: str = ""       # "short-title" | "title+interpretation" | "narrative"
    caption_tense: str = ""         # "past" | "present" | "mixed"
    palette: str = ""               # "monochrome" | "few-colors" | "categorical" | "sequential"
    placement: str = ""             # "top-of-page" | "inline" | "deferred"
    canonical_caption: str = ""


class TableStyle(BaseModel):
    """Visual design conventions for tables."""

    model_config = ConfigDict(extra="ignore")
    rule_style: str = ""            # "booktabs" | "grid" | "mixed"
    highlight_best: str = ""        # "bold" | "underline" | "shaded-cell" | "none"
    units_in: str = ""              # "column-header" | "row-header" | "inline"
    significance_markers: str = ""  # "stars" | "daggers" | "none"
    typical_columns: list[str] = Field(default_factory=list)
    canonical_caption: str = ""


class VenueRefAnalysis(BaseModel):
    model_config = ConfigDict(extra="ignore")

    # identity
    slug: str
    title: str
    authors: list[str] = Field(default_factory=list)
    year: int | None = None
    venue: str | None = None
    pdf_path: str | None = None
    arxiv_id: str | None = None
    added_at: str

    # macro structure
    sections: list[SectionSpec] = Field(default_factory=list)
    abstract_word_count: int | None = None
    abstract_structural_pattern: str = ""

    # micro style
    intro_hook: str = ""
    we_propose_verb: str = ""
    contribution_presentation: str = ""
    method_voice: str = ""
    method_tense: str = ""

    citations: CitationStyle = Field(default_factory=CitationStyle)
    figures: FigureRefStyle = Field(default_factory=FigureRefStyle)
    results: ResultClaimStyle = Field(default_factory=ResultClaimStyle)

    limitations_placement: str = ""
    limitations_language: str = ""

    we_usage_per_kpara: float | None = None
    passive_voice_share: float | None = None

    # visual conventions
    figure_style: FigureStyle = Field(default_factory=FigureStyle)
    table_style: TableStyle = Field(default_factory=TableStyle)

    # quotables
    notable_transitions: list[str] = Field(default_factory=list)
    sentence_templates: dict[str, list[str]] = Field(default_factory=dict)
    antipatterns_avoided: list[str] = Field(default_factory=list)


def analysis_to_markdown(analysis: VenueRefAnalysis) -> str:
    """Serialize an analysis to YAML frontmatter + a human-readable body."""
    data = analysis.model_dump(mode="json")
    frontmatter = yaml.safe_dump(data, sort_keys=False, allow_unicode=True).rstrip()
    body = _render_body(analysis)
    return f"---\n{frontmatter}\n---\n\n{body}\n"


def analysis_from_markdown(text: str) -> VenueRefAnalysis:
    """Inverse of `analysis_to_markdown`: parses frontmatter only (body is informational)."""
    frontmatter = _split_frontmatter(text)
    if frontmatter is None:
        raise ValueError("missing YAML frontmatter in venue-ref markdown")
    data = yaml.safe_load(frontmatter) or {}
    if not isinstance(data, dict):
        raise ValueError("venue-ref frontmatter must be a YAML mapping")
    return VenueRefAnalysis.model_validate(data)


def load_venue_ref_analysis(path: Path) -> VenueRefAnalysis:
    """Read + parse a `_venue-refs/<slug>.md` file."""
    return analysis_from_markdown(Path(path).read_text(encoding="utf-8"))


# ---------- helpers ----------

def _has_figure_content(fs: FigureStyle) -> bool:
    return bool(
        fs.typical_kinds
        or fs.column_span
        or fs.subfigures
        or fs.caption_pattern
        or fs.caption_tense
        or fs.palette
        or fs.placement
        or fs.canonical_caption
    )


def _has_table_content(ts: TableStyle) -> bool:
    return bool(
        ts.rule_style
        or ts.highlight_best
        or ts.units_in
        or ts.significance_markers
        or ts.typical_columns
        or ts.canonical_caption
    )


def _split_frontmatter(text: str) -> str | None:
    """Return the YAML text of the leading frontmatter block, or ``None``.

    Thin wrapper over :func:`research_assistant.common.frontmatter._split` —
    kept for back-compat with this module's callers.
    """
    from research_assistant.common.frontmatter import _split

    split = _split(text)
    return split[0] if split else None


def _render_body(a: VenueRefAnalysis) -> str:
    lines: list[str] = [f"# {a.title or a.slug}", ""]
    meta_bits = []
    if a.authors:
        meta_bits.append(", ".join(a.authors))
    if a.year:
        meta_bits.append(str(a.year))
    if a.venue:
        meta_bits.append(a.venue)
    if meta_bits:
        lines.extend([" · ".join(meta_bits), ""])

    if a.sections:
        lines.append("## Section structure")
        lines.append("")
        for s in a.sections:
            lines.append(f"- **{s.name}** — {s.opening_pattern or '_unspecified_'}")
            if s.canonical_sentence:
                lines.append(f"  > {s.canonical_sentence}")
        lines.append("")

    lines.append("## Micro-style")
    lines.append("")
    lines.append(f"- Abstract pattern: {a.abstract_structural_pattern or '_unspecified_'}")
    lines.append(f"- Intro hook: {a.intro_hook or '_unspecified_'}")
    lines.append(f"- 'We propose' verb: {a.we_propose_verb or '_unspecified_'}")
    lines.append(f"- Contributions: {a.contribution_presentation or '_unspecified_'}")
    lines.append(f"- Method voice/tense: {a.method_voice or '_'}/{a.method_tense or '_'}")
    lines.append(
        f"- Citations: {a.citations.form or '_unspecified_'} "
        f"({a.citations.integration_pattern or 'no pattern noted'})"
    )
    lines.append(
        f"- Figures/equations: {a.figures.figure_form or '_'} / {a.figures.equation_form or '_'}"
    )
    if a.results.hedging_vocab or a.results.verbs:
        lines.append(
            f"- Result claims: hedging={a.results.hedging_vocab}, verbs={a.results.verbs}"
        )
    lines.append(
        f"- Limitations: {a.limitations_placement or '_'} ({a.limitations_language or '_'})"
    )
    lines.append("")

    if _has_figure_content(a.figure_style):
        lines.append("## Figure style")
        lines.append("")
        fs = a.figure_style
        if fs.typical_kinds:
            lines.append(f"- Typical kinds: {', '.join(fs.typical_kinds)}")
        if fs.column_span:
            lines.append(f"- Column span: {fs.column_span}")
        if fs.subfigures:
            lines.append("- Subfigures: yes (a/b/c pattern)")
        if fs.caption_pattern:
            lines.append(f"- Caption pattern: {fs.caption_pattern}")
        if fs.caption_tense:
            lines.append(f"- Caption tense: {fs.caption_tense}")
        if fs.palette:
            lines.append(f"- Palette: {fs.palette}")
        if fs.placement:
            lines.append(f"- Placement: {fs.placement}")
        if fs.canonical_caption:
            lines.append("")
            lines.append(f"> {fs.canonical_caption}")
        lines.append("")

    if _has_table_content(a.table_style):
        lines.append("## Table style")
        lines.append("")
        ts = a.table_style
        if ts.rule_style:
            lines.append(f"- Rule style: {ts.rule_style}")
        if ts.highlight_best:
            lines.append(f"- Highlight-best: {ts.highlight_best}")
        if ts.units_in:
            lines.append(f"- Units in: {ts.units_in}")
        if ts.significance_markers:
            lines.append(f"- Significance markers: {ts.significance_markers}")
        if ts.typical_columns:
            lines.append(f"- Typical columns: {', '.join(ts.typical_columns)}")
        if ts.canonical_caption:
            lines.append("")
            lines.append(f"> {ts.canonical_caption}")
        lines.append("")

    if a.notable_transitions:
        lines.append("## Notable transitions")
        lines.append("")
        for t in a.notable_transitions:
            lines.append(f"- {t}")
        lines.append("")

    if a.sentence_templates:
        lines.append("## Sentence templates")
        lines.append("")
        for section, templates in a.sentence_templates.items():
            lines.append(f"**{section}**")
            for t in templates:
                lines.append(f"- {t}")
            lines.append("")

    if a.antipatterns_avoided:
        lines.append("## Anti-patterns avoided")
        lines.append("")
        for ap in a.antipatterns_avoided:
            lines.append(f"- {ap}")

    return "\n".join(lines).rstrip()
