"""Reference-figure intake + AgentDB payload tests."""
import shutil
from pathlib import Path

import pytest
from PIL import Image

from research_assistant.figures import refs as fr
from research_assistant.figures.schema import FigureRef


@pytest.fixture
def fake_refs_dir(tmp_path: Path, monkeypatch):
    refs_dir = tmp_path / "figure-refs"
    refs_dir.mkdir()
    monkeypatch.setattr(fr, "FIGURE_REFS_DIR", refs_dir)
    return refs_dir


@pytest.fixture
def sample_image(tmp_path: Path):
    img_path = tmp_path / "ref.png"
    Image.new("RGB", (80, 80), (30, 120, 200)).save(img_path)
    return img_path


def test_add_ref_creates_dir_and_note(fake_refs_dir: Path, sample_image: Path):
    ref = FigureRef(
        slug="vaswani-arch",
        source="Vaswani et al. 2017 (NeurIPS), Fig 1",
        kind="structural",
        tags=["architecture", "encoder-decoder"],
        palette=["#1F77B4"],
        why_i_like_it="Symmetric layout.",
    )
    fr.add_ref(sample_image, ref)
    entry_dir = fake_refs_dir / "vaswani-arch"
    assert (entry_dir / "image.png").exists()
    assert (entry_dir / "note.md").exists()


def test_add_ref_rejects_duplicate_without_force(fake_refs_dir: Path, sample_image: Path):
    ref = FigureRef(slug="dup", source="s", kind="structural")
    fr.add_ref(sample_image, ref)
    with pytest.raises(FileExistsError):
        fr.add_ref(sample_image, ref)


def test_add_ref_force_overwrites(fake_refs_dir: Path, sample_image: Path):
    ref = FigureRef(slug="force-me", source="s", kind="structural")
    fr.add_ref(sample_image, ref)
    fr.add_ref(sample_image, ref, force=True)  # should not raise


def test_list_refs_excludes_staging(fake_refs_dir: Path, sample_image: Path):
    (fake_refs_dir / "staging").mkdir()
    ref = FigureRef(slug="real", source="s", kind="structural")
    fr.add_ref(sample_image, ref)
    slugs = fr.list_refs()
    assert "real" in slugs
    assert "staging" not in slugs


def test_to_agentdb_payload_includes_search_text():
    ref = FigureRef(
        slug="vaswani-arch",
        source="Vaswani et al. 2017",
        kind="structural",
        tags=["architecture", "callouts"],
        why_i_like_it="Symmetric layout.",
    )
    payload = fr.to_agentdb_payload(ref)
    assert payload["namespace"] == "project/figure-refs"
    assert payload["key"] == "vaswani-arch"
    text = payload["text"]
    assert "Vaswani" in text
    assert "structural" in text
    assert "architecture" in text
    assert "Symmetric layout" in text


def test_read_ref_round_trip(fake_refs_dir: Path, sample_image: Path):
    ref = FigureRef(
        slug="round-trip",
        source="Doe 2026",
        kind="data",
        tags=["dual-axis"],
        palette=["#000000", "#FFFFFF"],
        why_i_like_it="Clean baseline.",
    )
    fr.add_ref(sample_image, ref)
    loaded = fr.read_ref("round-trip")
    assert loaded == ref
