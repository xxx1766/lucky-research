"""matplotlib save_all helper tests."""
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import pytest

from research_assistant.figures import save as fs


def test_save_all_writes_three_files(tmp_path: Path):
    fig, ax = plt.subplots(figsize=(4, 3))
    ax.plot([0, 1, 2], [0, 1, 4])
    paths = fs.save_all(fig, tmp_path, "demo")
    plt.close(fig)
    assert paths.svg.exists() and paths.svg.suffix == ".svg"
    assert paths.pdf.exists() and paths.pdf.suffix == ".pdf"
    assert paths.png.exists() and paths.png.suffix == ".png"
    for p in (paths.svg, paths.pdf, paths.png):
        assert p.stat().st_size > 0


def test_save_all_respects_dpi(tmp_path: Path):
    fig, ax = plt.subplots(figsize=(4, 3))
    ax.plot([0, 1, 2], [0, 1, 4])
    paths = fs.save_all(fig, tmp_path, "demo", dpi=72)
    plt.close(fig)
    small = paths.png.stat().st_size
    fig2, ax2 = plt.subplots(figsize=(4, 3))
    ax2.plot([0, 1, 2], [0, 1, 4])
    paths2 = fs.save_all(fig2, tmp_path, "demo-hi", dpi=300)
    plt.close(fig2)
    assert paths2.png.stat().st_size > small
