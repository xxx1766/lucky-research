"""Venue-stage reference-paper helpers."""
from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock

import pytest

from research_assistant import common
from research_assistant.papers import venue_refs as vr_mod
from research_assistant.papers.venue_conventions import (
    VenueRefAnalysis,
    analysis_to_markdown,
)
from research_assistant.papers.venue_merge import SENTINEL_BEGIN, SENTINEL_END


@pytest.fixture
def fake_papers_dir(tmp_path, monkeypatch):
    fake_papers = tmp_path / "papers"
    fake_inputs = tmp_path / "inputs-papers"
    fake_papers.mkdir()
    fake_inputs.mkdir()
    monkeypatch.setattr(common.io, "PAPERS_DIR", fake_papers)
    monkeypatch.setattr(common.io, "PAPERS_INPUT_DIR", fake_inputs)
    monkeypatch.setattr(vr_mod, "PAPERS_DIR", fake_papers)
    monkeypatch.setattr(vr_mod, "PAPERS_INPUT_DIR", fake_inputs)
    return fake_papers, fake_inputs


def _make_venue(papers_dir: Path, slug: str) -> Path:
    venue_dir = papers_dir / slug
    venue_dir.mkdir()
    (venue_dir / "_venue.md").write_text("# v\n", encoding="utf-8")
    return venue_dir


def _stub_analysis(slug="x", title="x", added_at="2026-05-14") -> VenueRefAnalysis:
    return VenueRefAnalysis(slug=slug, title=title, added_at=added_at)


# ---------- paths + slug ----------

def test_venue_refs_dir_under_papers_dir(fake_papers_dir):
    papers, _ = fake_papers_dir
    out = vr_mod.venue_refs_dir("NeurIPS-2026")
    assert out == (papers / "NeurIPS-2026" / "_venue-refs").absolute()


def test_venue_refs_dir_rejects_traversal(fake_papers_dir):
    with pytest.raises(ValueError):
        vr_mod.venue_refs_dir("../escape")
    with pytest.raises(ValueError):
        vr_mod.venue_refs_dir(".hidden")


def test_venue_ref_path_rejects_traversal(fake_papers_dir):
    _make_venue(fake_papers_dir[0], "NeurIPS-2026")
    with pytest.raises(ValueError):
        vr_mod.venue_ref_path("NeurIPS-2026", "../escape")


def test_slugify_paper_ref_uses_author_year_title():
    s = vr_mod.slugify_paper_ref(
        title="On the Foundations of Weightlets",
        year=2024,
        arxiv_id=None,
        authors=["Smith, Alice", "Jones, Bob"],
    )
    assert s.startswith("smith-2024-")
    assert "foundations" in s
    assert "weightlets" in s


def test_slugify_paper_ref_no_authors_uses_year_title():
    s = vr_mod.slugify_paper_ref(
        title="Diffusion Fine-tuning Tricks",
        year=2025,
        arxiv_id=None,
    )
    assert s.startswith("2025-")
    assert "diffusion" in s


def test_slugify_paper_ref_arxiv_fallback():
    s = vr_mod.slugify_paper_ref(title=None, year=None, arxiv_id="2401.12345")
    assert "2401" in s
    assert "12345" in s


def test_slugify_paper_ref_raises_when_no_signals():
    with pytest.raises(ValueError):
        vr_mod.slugify_paper_ref(title=None, year=None, arxiv_id=None)


# ---------- list / summary ----------

def test_list_venue_refs_empty(fake_papers_dir):
    papers, _ = fake_papers_dir
    _make_venue(papers, "NeurIPS-2026")
    assert vr_mod.list_venue_refs("NeurIPS-2026") == []


def test_list_venue_refs_sorts_by_added_desc(fake_papers_dir):
    papers, _ = fake_papers_dir
    _make_venue(papers, "NeurIPS-2026")
    refs_dir = papers / "NeurIPS-2026" / "_venue-refs"
    refs_dir.mkdir()
    for slug, added in [("a", "2026-01-01"), ("b", "2026-03-01"), ("c", "2026-02-15")]:
        path = refs_dir / f"{slug}.md"
        path.write_text(
            analysis_to_markdown(_stub_analysis(slug=slug, added_at=added)),
            encoding="utf-8",
        )
    entries = vr_mod.list_venue_refs("NeurIPS-2026")
    assert [e.slug for e in entries] == ["b", "c", "a"]


def test_venue_refs_summary_distilled_flag(fake_papers_dir):
    papers, _ = fake_papers_dir
    _make_venue(papers, "NeurIPS-2026")
    refs_dir = papers / "NeurIPS-2026" / "_venue-refs"
    refs_dir.mkdir()
    (refs_dir / "x.md").write_text(
        analysis_to_markdown(_stub_analysis()), encoding="utf-8"
    )
    summary = vr_mod.venue_refs_summary("NeurIPS-2026")
    assert summary is not None
    assert summary.count == 1
    assert summary.distilled is False

    # Now add sentinels to _venue.md.
    venue_md = papers / "NeurIPS-2026" / "_venue.md"
    venue_md.write_text(
        f"# v\n\n## Writing conventions\n{SENTINEL_BEGIN}\nbody\n{SENTINEL_END}\n",
        encoding="utf-8",
    )
    summary = vr_mod.venue_refs_summary("NeurIPS-2026")
    assert summary is not None
    assert summary.distilled is True


def test_venue_refs_summary_none_when_venue_missing(fake_papers_dir):
    assert vr_mod.venue_refs_summary("DoesNotExist") is None


# ---------- ingest / distill ----------

def test_ingest_venue_ref_skips_existing(fake_papers_dir, tmp_path):
    papers, _ = fake_papers_dir
    _make_venue(papers, "NeurIPS-2026")
    refs_dir = papers / "NeurIPS-2026" / "_venue-refs"
    refs_dir.mkdir()
    pdf = tmp_path / "ref.pdf"
    pdf.write_bytes(b"%PDF-1.4 fake")

    # Pre-create a file matching the slug we'll produce below.
    pre_slug = vr_mod.slugify_paper_ref(
        title="A Paper", year=2024, arxiv_id=None, authors=["Smith, Alice"]
    )
    (refs_dir / f"{pre_slug}.md").write_text(
        analysis_to_markdown(_stub_analysis(slug=pre_slug)), encoding="utf-8"
    )

    parse_metadata = MagicMock(return_value={
        "title": "A Paper", "authors": ["Smith, Alice"], "year": 2024,
    })
    extract = MagicMock()
    analyze = MagicMock()

    path = vr_mod.ingest_venue_ref(
        "NeurIPS-2026",
        str(pdf),
        parse_metadata=parse_metadata,
        extract_pdf_text=extract,
        analyze=analyze,
    )
    assert path.exists()
    parse_metadata.assert_called_once()
    extract.assert_not_called()
    analyze.assert_not_called()


def test_ingest_venue_ref_writes_yaml_frontmatter(fake_papers_dir, tmp_path):
    papers, _ = fake_papers_dir
    _make_venue(papers, "NeurIPS-2026")
    pdf = tmp_path / "ref.pdf"
    pdf.write_bytes(b"%PDF-1.4 fake")

    parse_metadata = MagicMock(return_value={
        "title": "Foundations of X", "authors": ["Smith, Alice"], "year": 2024,
    })
    extract_pdf_text = MagicMock(return_value="full text")
    analyze = MagicMock(side_effect=lambda text, meta: VenueRefAnalysis(
        slug=meta["slug"], title=meta["title"], added_at=meta["added_at"],
    ))

    path = vr_mod.ingest_venue_ref(
        "NeurIPS-2026",
        str(pdf),
        parse_metadata=parse_metadata,
        extract_pdf_text=extract_pdf_text,
        analyze=analyze,
    )
    assert path.exists()
    text = path.read_text(encoding="utf-8")
    assert text.startswith("---\n")
    assert "slug:" in text
    assert "title: Foundations of X" in text
    assert "authors:" in text
    assert "added_at:" in text
    extract_pdf_text.assert_called_once()
    analyze.assert_called_once()


def test_ingest_venue_ref_errors_if_venue_missing(fake_papers_dir, tmp_path):
    pdf = tmp_path / "x.pdf"
    pdf.write_bytes(b"%PDF-1.4")
    with pytest.raises(FileNotFoundError, match="venue not initialized"):
        vr_mod.ingest_venue_ref(
            "Phantom-9999",
            str(pdf),
            parse_metadata=MagicMock(return_value={"title": "t", "year": 2024}),
        )


def test_distill_venue_conventions_upserts_block(fake_papers_dir):
    papers, _ = fake_papers_dir
    _make_venue(papers, "NeurIPS-2026")
    refs_dir = papers / "NeurIPS-2026" / "_venue-refs"
    refs_dir.mkdir()
    for slug in ("a", "b"):
        (refs_dir / f"{slug}.md").write_text(
            analysis_to_markdown(_stub_analysis(slug=slug)), encoding="utf-8"
        )

    aggregate = MagicMock(return_value="AGGREGATED BODY")
    out = vr_mod.distill_venue_conventions("NeurIPS-2026", aggregate=aggregate)

    assert out.name == "_venue.md"
    venue_text = out.read_text(encoding="utf-8")
    assert "## Writing conventions" in venue_text
    assert "AGGREGATED BODY" in venue_text
    assert SENTINEL_BEGIN in venue_text and SENTINEL_END in venue_text
    # Aggregator received both analyses.
    args, _kwargs = aggregate.call_args
    analyses = args[0]
    assert {a.slug for a in analyses} == {"a", "b"}


def test_distill_venue_conventions_errors_if_venue_md_missing(fake_papers_dir):
    papers, _ = fake_papers_dir
    (papers / "Phantom").mkdir()  # venue dir exists but no _venue.md
    with pytest.raises(FileNotFoundError):
        vr_mod.distill_venue_conventions("Phantom", aggregate=MagicMock())


# ---------- analysis_to_markdown round-trip ----------

def test_analysis_to_markdown_roundtrip():
    from research_assistant.papers.venue_conventions import (
        FigureStyle,
        SectionSpec,
        TableStyle,
        analysis_from_markdown,
    )
    original = VenueRefAnalysis(
        slug="smith-2024-foo",
        title="Foo",
        authors=["Smith, Alice"],
        year=2024,
        venue="NeurIPS-2026",
        added_at="2026-05-14",
        sections=[SectionSpec(name="Intro", order_index=0, opening_pattern="hook")],
        intro_hook="motivating example",
        we_propose_verb="propose",
        notable_transitions=["Conversely,", "Crucially,"],
        sentence_templates={"intro": ["We propose ...", "In this paper, we ..."]},
        figure_style=FigureStyle(
            typical_kinds=["line plot", "system diagram"],
            column_span="double",
            subfigures=True,
            caption_pattern="title+interpretation",
            palette="few-colors",
            placement="top-of-page",
            canonical_caption="Throughput vs. batch size on A100 (higher is better).",
        ),
        table_style=TableStyle(
            rule_style="booktabs",
            highlight_best="bold",
            units_in="column-header",
            significance_markers="stars",
            typical_columns=["Method", "Dataset", "Accuracy"],
            canonical_caption="Top-1 accuracy on ImageNet-1k (%).",
        ),
    )
    text = analysis_to_markdown(original)
    parsed = analysis_from_markdown(text)
    assert parsed.slug == original.slug
    assert parsed.title == original.title
    assert parsed.authors == original.authors
    assert parsed.year == original.year
    assert parsed.intro_hook == original.intro_hook
    assert parsed.sentence_templates == original.sentence_templates
    assert len(parsed.sections) == 1
    assert parsed.sections[0].name == "Intro"
    # Visual style round-trips.
    assert parsed.figure_style.typical_kinds == original.figure_style.typical_kinds
    assert parsed.figure_style.column_span == "double"
    assert parsed.figure_style.subfigures is True
    assert parsed.figure_style.canonical_caption == original.figure_style.canonical_caption
    assert parsed.table_style.rule_style == "booktabs"
    assert parsed.table_style.highlight_best == "bold"
    assert parsed.table_style.typical_columns == original.table_style.typical_columns
    assert parsed.table_style.canonical_caption == original.table_style.canonical_caption


def test_ingest_venue_ref_passes_pdf_abs_path(fake_papers_dir, tmp_path):
    papers, _ = fake_papers_dir
    _make_venue(papers, "NeurIPS-2026")
    pdf = tmp_path / "ref.pdf"
    pdf.write_bytes(b"%PDF-1.4 fake")
    captured: dict[str, dict] = {}

    def analyze(text, meta):
        captured["meta"] = meta
        return VenueRefAnalysis(
            slug=meta["slug"], title=meta["title"], added_at=meta["added_at"]
        )

    vr_mod.ingest_venue_ref(
        "NeurIPS-2026",
        str(pdf),
        parse_metadata=MagicMock(return_value={
            "title": "Foo", "authors": ["Smith, Alice"], "year": 2024,
        }),
        extract_pdf_text=MagicMock(return_value="full text"),
        analyze=analyze,
    )
    meta = captured["meta"]
    assert "pdf_abs_path" in meta
    abs_path = Path(meta["pdf_abs_path"])
    assert abs_path.is_absolute()
    assert abs_path == pdf.resolve()
    # Repo-relative `pdf_path` is still present and is *not* absolute.
    assert "pdf_path" in meta
    assert not Path(meta["pdf_path"]).is_absolute()


def test_render_body_includes_figure_table_sections_when_nonempty():
    from research_assistant.papers.venue_conventions import (
        FigureStyle,
        TableStyle,
    )
    populated = VenueRefAnalysis(
        slug="x", title="X", added_at="2026-05-15",
        figure_style=FigureStyle(
            typical_kinds=["bar chart"],
            palette="categorical",
            canonical_caption="Figure 1: Throughput vs. concurrency.",
        ),
        table_style=TableStyle(
            rule_style="booktabs",
            highlight_best="bold",
            canonical_caption="Table 1: Latency breakdown (ms).",
        ),
    )
    text = analysis_to_markdown(populated)
    assert "## Figure style" in text
    assert "## Table style" in text
    assert "bar chart" in text
    assert "booktabs" in text
    assert "> Figure 1: Throughput vs. concurrency." in text
    assert "> Table 1: Latency breakdown (ms)." in text

    empty = VenueRefAnalysis(slug="y", title="Y", added_at="2026-05-15")
    text_empty = analysis_to_markdown(empty)
    assert "## Figure style" not in text_empty
    assert "## Table style" not in text_empty
