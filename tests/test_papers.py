"""Smoke tests for the paper-output helper package."""

from research_assistant.common.io import PAPERS_DIR
from research_assistant.papers import (
    StageStatus,
    direction_path,
    next_suggested,
    render_progress_board,
    render_progress_footer,
    slugify_direction,
    slugify_venue,
    stage_status,
    tex_files,
    venue_path,
)


def test_slugify_venue_shape():
    assert slugify_venue("NeurIPS", 2026) == "NeurIPS-2026"
    # Trailing year in the name is stripped before slugifying — no double-year.
    assert slugify_venue("ICLR 2026", 2026) == "ICLR-2026"
    assert slugify_venue("ICLR-2026", 2026) == "ICLR-2026"
    assert slugify_venue("NeurIPS 2025", 2026) == "NeurIPS-2026"  # year override
    assert slugify_venue("CoLM", 2025) == "CoLM-2025"
    # Only YYYY at end is stripped, not embedded numerics.
    assert slugify_venue("EMNLP1", 2026) == "EMNLP1-2026"


def test_slugify_direction_shape():
    assert slugify_direction("Diffusion fine-tuning") == "diffusion-fine-tuning"
    assert slugify_direction("Retrieval Rerank") == "retrieval-rerank"
    assert slugify_direction("  spaced  ") == "spaced"


def test_venue_path_under_papers_dir():
    p = venue_path("NeurIPS-2026")
    assert p.parent == PAPERS_DIR
    assert p.name == "NeurIPS-2026"


def test_direction_path_nested():
    p = direction_path("NeurIPS-2026", "diffusion-finetune")
    assert p.parent.name == "NeurIPS-2026"
    assert p.name == "diffusion-finetune"


def test_tex_files_empty_when_missing(tmp_path):
    assert tex_files(tmp_path) == []


def test_tex_files_lists_only_tex(tmp_path):
    sections = tmp_path / "sections"
    sections.mkdir()
    (sections / "intro.tex").write_text("")
    (sections / "method.tex").write_text("")
    (sections / "notes.md").write_text("not a section")
    assert {p.name for p in tex_files(tmp_path)} == {"intro.tex", "method.tex"}


def test_stage_status_empty_dir(tmp_path):
    status = stage_status(tmp_path)
    assert status.has_expert is False
    assert status.has_main_tex is False
    assert status.has_pdf is False
    assert status.has_outline is False
    assert status.has_benchmark is False
    assert status.has_refs is False
    assert status.sections_written == 0
    assert status.refs_entries == 0


def test_stage_status_with_tex_sections(tmp_path):
    (tmp_path / "main.tex").write_text("")
    sections = tmp_path / "sections"
    sections.mkdir()
    (sections / "intro.tex").write_text("")
    status = stage_status(tmp_path)
    assert status.has_main_tex is True
    assert status.sections_written == 1


def test_stage_status_tracks_new_artifacts(tmp_path):
    (tmp_path / "outline.md").write_text("# outline")
    experiments = tmp_path / "experiments"
    experiments.mkdir()
    (experiments / "benchmark.md").write_text("plan")
    (tmp_path / "refs.bib").write_text(
        "@article{foo, title={x}}\n@inproceedings{bar, title={y}}\n",
    )
    status = stage_status(tmp_path)
    assert status.has_outline is True
    assert status.has_benchmark is True
    assert status.has_refs is True
    assert status.refs_entries == 2


def _fresh_status(**overrides) -> StageStatus:
    base = dict(
        has_expert=False,
        has_scout=False,
        has_focus=False,
        has_motivate=False,
        has_benchmark=False,
        has_outline=False,
        has_main_tex=False,
        has_pdf=False,
        has_refs=False,
        sections_written=0,
        refs_entries=0,
    )
    base.update(overrides)
    return StageStatus(**base)


def _all_done_status() -> StageStatus:
    return _fresh_status(
        has_expert=True,
        has_scout=True,
        has_focus=True,
        has_motivate=True,
        has_benchmark=True,
        has_outline=True,
        has_main_tex=True,
        has_pdf=True,
        has_refs=True,
        sections_written=3,
        refs_entries=5,
    )


def test_next_suggested_after_each_gap():
    s = _fresh_status()
    assert next_suggested(s) == "/paper direction <slug>"
    s = _fresh_status(has_expert=True)
    assert next_suggested(s) == "/paper scout"
    s = _fresh_status(has_expert=True, has_scout=True)
    assert next_suggested(s) == "/paper focus"
    s = _fresh_status(has_expert=True, has_scout=True, has_focus=True)
    assert next_suggested(s) == "/paper motivate"
    s = _fresh_status(
        has_expert=True, has_scout=True, has_focus=True,
        has_motivate=True, has_benchmark=True,
    )
    assert next_suggested(s) == "/paper write"
    s = _fresh_status(
        has_expert=True, has_scout=True, has_focus=True,
        has_motivate=True, has_benchmark=True,
        has_outline=True, has_main_tex=True,
    )
    assert next_suggested(s) == "/paper write intro"
    s = _fresh_status(
        has_expert=True, has_scout=True, has_focus=True,
        has_motivate=True, has_benchmark=True,
        has_outline=True, has_main_tex=True, sections_written=2,
    )
    assert next_suggested(s) == "/paper render"
    s = _fresh_status(
        has_expert=True, has_scout=True, has_focus=True,
        has_motivate=True, has_benchmark=True,
        has_outline=True, has_main_tex=True, sections_written=2,
        has_pdf=True,
    )
    assert next_suggested(s) == "/cite"
    assert next_suggested(_all_done_status()).startswith("all stages complete")


def test_render_progress_footer_no_venue():
    footer = render_progress_footer(None, None, None)
    assert "no current paper" in footer
    assert "/paper venue" in footer


def test_render_progress_footer_no_direction():
    footer = render_progress_footer("NeurIPS-2026", None, None)
    assert "NeurIPS-2026" in footer
    assert "/paper direction" in footer


def test_render_progress_footer_fresh_direction():
    footer = render_progress_footer("NeurIPS-2026", "diffusion-ft", _fresh_status())
    assert "[#------] 1/7" in footer
    assert "next: /paper direction" in footer


def test_render_progress_footer_partial():
    status = _fresh_status(
        has_expert=True, has_scout=True, has_focus=True,
        has_motivate=True, has_benchmark=True,
        has_outline=True, has_main_tex=True, sections_written=2,
    )
    footer = render_progress_footer("NeurIPS-2026", "diffusion-ft", status)
    assert "[######-] 6/7" in footer
    assert "next: /paper render" in footer


def test_render_progress_footer_all_done():
    footer = render_progress_footer("NeurIPS-2026", "diffusion-ft", _all_done_status())
    assert "[#######] 7/7" in footer


def test_render_progress_board_structure():
    status = _fresh_status(
        has_expert=True, has_scout=True, has_focus=True,
        has_motivate=True, has_benchmark=True,
        has_outline=True, has_main_tex=True, sections_written=2,
    )
    board = render_progress_board("NeurIPS-2026", "diffusion-ft", status)
    assert board.startswith("NeurIPS-2026 / diffusion-ft")
    assert "[######-] 6/7 stages" in board
    # Seven numbered stage lines.
    lines = board.splitlines()
    stage_lines = [ln for ln in lines if ln.lstrip().startswith(("[x]", "[.]", "[ ]"))]
    assert len(stage_lines) == 7
    assert "cite" in board
    assert "Suggested next:" in board


def test_render_progress_board_marks_partial_write(tmp_path):
    status = _fresh_status(
        has_expert=True, has_scout=True, has_focus=True,
        has_motivate=True, has_benchmark=True,
        has_outline=True,  # outline.md only, no main.tex, no sections
    )
    board = render_progress_board("NeurIPS-2026", "diffusion-ft", status)
    write_line = next(ln for ln in board.splitlines() if "6. write" in ln)
    assert write_line.lstrip().startswith("[.]")
