"""SVG → PDF + PNG export pipeline (cairosvg). Idempotent."""
from __future__ import annotations

from pathlib import Path


class ExportError(RuntimeError):
    """Raised when cairosvg cannot render the SVG (malformed, unsupported feature)."""


def export(svg_path: Path, *, dpi: int = 300) -> tuple[Path, Path]:
    """Render <svg_path> to a sibling <stem>.pdf and <stem>.png. Returns the two paths.

    Idempotent — re-runs overwrite outputs. PNG is rendered at the given DPI;
    PDF is vector and DPI-independent.
    """
    import cairosvg

    if not svg_path.exists():
        raise FileNotFoundError(svg_path)

    pdf_path = svg_path.with_suffix(".pdf")
    png_path = svg_path.with_suffix(".png")

    try:
        cairosvg.svg2pdf(url=str(svg_path), write_to=str(pdf_path))
        cairosvg.svg2png(url=str(svg_path), write_to=str(png_path), dpi=dpi)
    except Exception as e:
        raise ExportError(f"cairosvg failed to render {svg_path}: {e}") from e

    return pdf_path, png_path
