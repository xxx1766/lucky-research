"""Palette loading: shipped presets + per-direction overrides + ANSI swatch rendering."""
from __future__ import annotations

from pathlib import Path

import yaml

from research_assistant.figures.schema import PaletteSpec

_SHIPPED_DIR = Path(__file__).parent / "styles" / "palette"


def list_shipped_palettes() -> list[str]:
    return sorted(p.stem for p in _SHIPPED_DIR.glob("*.yml"))


def load_palette(name: str) -> PaletteSpec:
    path = _SHIPPED_DIR / f"{name}.yml"
    if not path.exists():
        raise FileNotFoundError(f"palette '{name}' not found in {_SHIPPED_DIR}")
    data = yaml.safe_load(path.read_text(encoding="utf-8"))
    return PaletteSpec.model_validate(data)


def load_palette_for_direction(figures_dir: Path, *, fallback: str) -> PaletteSpec:
    """Look for `_palette.yml` in the direction's figures/ dir; fall back to a shipped name."""
    override = figures_dir / "_palette.yml"
    if override.exists():
        data = yaml.safe_load(override.read_text(encoding="utf-8"))
        return PaletteSpec.model_validate(data)
    return load_palette(fallback)


def ansi_swatch(spec: PaletteSpec, *, width: int = 4) -> str:
    """Render the palette's sequence as ANSI true-color background blocks.

    Used by /figure new step 5 to show palette options in the terminal.
    """
    blocks = []
    for hex_color in spec.sequence:
        r, g, b = _hex_to_rgb(hex_color)
        blocks.append(f"\x1b[48;2;{r};{g};{b}m{' ' * width}\x1b[0m")
    return "".join(blocks) + f"  {spec.name}"


def _hex_to_rgb(hex_color: str) -> tuple[int, int, int]:
    h = hex_color.lstrip("#")
    if len(h) != 6:
        raise ValueError(f"expected #RRGGBB, got {hex_color!r}")
    return int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16)
