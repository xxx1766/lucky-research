"""Palette load, override, and ANSI swatch tests."""
from pathlib import Path

import pytest

from research_assistant.figures import palette as fp
from research_assistant.figures.schema import PaletteSpec


def test_load_shipped_palettes_all_four():
    for name in ("paper-mono", "paper-trio", "paper-extended", "dark-on-light"):
        spec = fp.load_palette(name)
        assert isinstance(spec, PaletteSpec)
        assert spec.name == name
        assert len(spec.sequence) >= 3


def test_load_unknown_palette_raises():
    with pytest.raises(FileNotFoundError):
        fp.load_palette("does-not-exist")


def test_list_shipped_palettes():
    names = fp.list_shipped_palettes()
    assert set(names) == {"paper-mono", "paper-trio", "paper-extended", "dark-on-light"}


def test_direction_override_takes_precedence(tmp_path: Path):
    direction_dir = tmp_path / "papers" / "ICLR-2026" / "main"
    fig_dir = direction_dir / "figures"
    fig_dir.mkdir(parents=True)
    (fig_dir / "_palette.yml").write_text(
        "name: custom-direction\n"
        "slots: {primary: '#111111'}\n"
        "sequence: ['#111111', '#222222']\n"
        "colorblind_safe: false\n"
        "suggested_for: []\n"
    )
    spec = fp.load_palette_for_direction(fig_dir, fallback="paper-trio")
    assert spec.name == "custom-direction"


def test_direction_override_falls_back_to_shipped(tmp_path: Path):
    fig_dir = tmp_path / "figures"
    fig_dir.mkdir()
    spec = fp.load_palette_for_direction(fig_dir, fallback="paper-trio")
    assert spec.name == "paper-trio"


def test_ansi_swatch_contains_color_blocks():
    spec = fp.load_palette("paper-trio")
    swatch = fp.ansi_swatch(spec)
    # ANSI true-color escape: ESC[48;2;R;G;Bm
    assert "\x1b[48;2;" in swatch
    # Reset sequence
    assert "\x1b[0m" in swatch


def test_extract_palette_creates_hex_strings(tmp_path: Path):
    # Build a tiny synthetic PNG to feed colorthief.
    from PIL import Image
    img_path = tmp_path / "fixture.png"
    Image.new("RGB", (60, 60), (255, 0, 0)).save(img_path)
    palette = fp.extract_palette_from_image(img_path, count=3)
    assert len(palette) == 3
    for hex_color in palette:
        assert hex_color.startswith("#")
        assert len(hex_color) == 7


def test_extract_palette_rejects_missing_file(tmp_path: Path):
    with pytest.raises(FileNotFoundError):
        fp.extract_palette_from_image(tmp_path / "no-such-file.png", count=3)
