"""matplotlib `save_all` helper for data-kind figures — writes pdf + png.

Data figures' source of truth is the matplotlib script (`plot_<slug>.py`); SVG
adds noise without giving the user anything they'd actually hand-edit. So this
helper produces just the two formats the user actually consumes:

  * `<slug>.pdf` — vector, used by LaTeX `\\includegraphics`.
  * `<slug>.png` — 300 DPI raster, used for slides / posters / raster-only venues.

For structural figures (Claude-written SVG that the user iterates in Inkscape)
use `research_assistant.figures.export.export(svg_path)` instead — that path
keeps the editable SVG plus its derived PDF + PNG.
"""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class SavedFigure:
    pdf: Path
    png: Path


def save_all(fig, out_dir: Path, slug: str, *, dpi: int = 300) -> SavedFigure:
    """Write `<out_dir>/<slug>.{pdf,png}` from a matplotlib Figure.

    Both formats use `bbox_inches='tight'`. PNG uses the supplied dpi; PDF is
    vector. No SVG is produced — the script is the canonical source.
    """
    out_dir.mkdir(parents=True, exist_ok=True)
    pdf_path = out_dir / f"{slug}.pdf"
    png_path = out_dir / f"{slug}.png"
    fig.savefig(pdf_path, bbox_inches="tight")
    fig.savefig(png_path, bbox_inches="tight", dpi=dpi)
    return SavedFigure(pdf=pdf_path, png=png_path)
