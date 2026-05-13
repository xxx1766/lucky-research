"""matplotlib `save_all` helper — drop-in to write svg + pdf + png in one call."""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class SavedFigure:
    svg: Path
    pdf: Path
    png: Path


def save_all(fig, out_dir: Path, slug: str, *, dpi: int = 300) -> SavedFigure:
    """Write `<out_dir>/<slug>.{svg,pdf,png}` from a matplotlib Figure.

    All three formats use `bbox_inches='tight'`. PNG uses the supplied dpi;
    SVG and PDF are vector.
    """
    out_dir.mkdir(parents=True, exist_ok=True)
    svg_path = out_dir / f"{slug}.svg"
    pdf_path = out_dir / f"{slug}.pdf"
    png_path = out_dir / f"{slug}.png"
    fig.savefig(svg_path, bbox_inches="tight")
    fig.savefig(pdf_path, bbox_inches="tight")
    fig.savefig(png_path, bbox_inches="tight", dpi=dpi)
    return SavedFigure(svg=svg_path, pdf=pdf_path, png=png_path)
