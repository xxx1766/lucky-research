"""Tests for `research_assistant.refs` — bibtex merge, pandoc convert, tex scan, LaTeX render."""
from __future__ import annotations

import shutil

import pytest

from research_assistant.refs import (
    convert_document,
    merge_bibtex,
    render_latex,
    scan_tex_cite_keys,
)

# ---------------------------------------------------------------------------
# merge_bibtex
# ---------------------------------------------------------------------------


def _write(path, text: str) -> None:
    path.write_text(text, encoding="utf-8")


def _entry(key: str, **fields: str) -> str:
    body = ",\n  ".join(f"{k} = {{{v}}}" for k, v in fields.items())
    return f"@article{{{key},\n  {body}\n}}\n"


def test_merge_bibtex_empty_sources_writes_empty_file(tmp_path):
    dest = tmp_path / "out.bib"
    written = merge_bibtex([], dest)
    assert written == 0
    assert dest.is_file()
    assert dest.read_text(encoding="utf-8").strip() == ""


def test_merge_bibtex_dedupes_by_doi(tmp_path):
    src_a = tmp_path / "a.bib"
    src_b = tmp_path / "b.bib"
    _write(src_a, _entry("smith2024a", title="Foundations", doi="10.1/abc", author="Smith, J"))
    _write(src_b, _entry("smith2024b", title="Foundations (preprint)", doi="10.1/abc", author="Smith, John"))
    dest = tmp_path / "out.bib"

    written = merge_bibtex([src_a, src_b], dest)

    assert written == 1
    text = dest.read_text(encoding="utf-8")
    assert "smith2024a" in text  # first writer wins
    assert "smith2024b" not in text


def test_merge_bibtex_dedupes_by_title_when_doi_missing(tmp_path):
    src_a = tmp_path / "a.bib"
    src_b = tmp_path / "b.bib"
    _write(src_a, _entry("jones2023x", title="A Survey", author="Jones, A"))
    _write(src_b, _entry("jones2023y", title="A Survey", author="Jones, A"))
    dest = tmp_path / "out.bib"

    written = merge_bibtex([src_a, src_b], dest)

    assert written == 1


def test_merge_bibtex_preserves_distinct_entries(tmp_path):
    src = tmp_path / "src.bib"
    _write(
        src,
        _entry("a2024", title="Alpha", doi="10.1/a", author="A, A")
        + _entry("b2024", title="Beta", doi="10.1/b", author="B, B"),
    )
    dest = tmp_path / "out.bib"

    written = merge_bibtex([src], dest)

    assert written == 2
    text = dest.read_text(encoding="utf-8")
    assert "a2024" in text and "b2024" in text


def test_merge_bibtex_normalizes_doi_prefixes(tmp_path):
    src_a = tmp_path / "a.bib"
    src_b = tmp_path / "b.bib"
    _write(src_a, _entry("p", title="X", doi="10.1/SAME", author="P, P"))
    _write(src_b, _entry("q", title="Y", doi="https://doi.org/10.1/same", author="Q, Q"))
    dest = tmp_path / "out.bib"

    written = merge_bibtex([src_a, src_b], dest)

    assert written == 1


def test_merge_bibtex_output_is_sorted(tmp_path):
    src = tmp_path / "src.bib"
    _write(
        src,
        _entry("zulu2024", title="Z", author="Z")
        + _entry("alpha2024", title="A", author="A")
        + _entry("mike2024", title="M", author="M"),
    )
    dest = tmp_path / "out.bib"

    merge_bibtex([src], dest)

    text = dest.read_text(encoding="utf-8")
    assert text.index("alpha2024") < text.index("mike2024") < text.index("zulu2024")


def test_merge_bibtex_raises_on_missing_source(tmp_path):
    dest = tmp_path / "out.bib"
    with pytest.raises(FileNotFoundError):
        merge_bibtex([tmp_path / "nope.bib"], dest)


def test_merge_bibtex_creates_parent_dir(tmp_path):
    src = tmp_path / "src.bib"
    _write(src, _entry("x", title="t", author="a"))
    dest = tmp_path / "nested" / "deeper" / "out.bib"

    merge_bibtex([src], dest)

    assert dest.is_file()


# ---------------------------------------------------------------------------
# scan_tex_cite_keys
# ---------------------------------------------------------------------------


def _make_paper_dir(tmp_path, main_tex: str | None, sections: dict[str, str] | None = None):
    paper = tmp_path / "paper"
    paper.mkdir()
    if main_tex is not None:
        _write(paper / "main.tex", main_tex)
    if sections:
        (paper / "sections").mkdir()
        for name, body in sections.items():
            _write(paper / "sections" / name, body)
    return paper


def test_scan_tex_cite_keys_plain_and_multi(tmp_path):
    paper = _make_paper_dir(
        tmp_path,
        r"Intro \cite{alpha}. Background \cite{beta, gamma}." + "\n",
    )
    assert scan_tex_cite_keys(paper) == ["alpha", "beta", "gamma"]


def test_scan_tex_cite_keys_handles_variants(tmp_path):
    paper = _make_paper_dir(
        tmp_path,
        r"\citep{a} and \citet{b} and \cite*{c} and \citep[see][p.~3]{d}." + "\n",
    )
    assert scan_tex_cite_keys(paper) == ["a", "b", "c", "d"]


def test_scan_tex_cite_keys_ignores_comments(tmp_path):
    paper = _make_paper_dir(
        tmp_path,
        "Real \\cite{keeper}.\n% \\cite{ignored}\n"
        "Inline % \\cite{also_ignored}\n"
        "After 50\\% \\cite{still_kept}\n",
    )
    assert scan_tex_cite_keys(paper) == ["keeper", "still_kept"]


def test_scan_tex_cite_keys_dedupes_preserving_first_order(tmp_path):
    paper = _make_paper_dir(
        tmp_path,
        r"\cite{b} \cite{a} \cite{b} \cite{c} \cite{a}" + "\n",
    )
    assert scan_tex_cite_keys(paper) == ["b", "a", "c"]


def test_scan_tex_cite_keys_walks_sections(tmp_path):
    paper = _make_paper_dir(
        tmp_path,
        r"\cite{from_main}" + "\n",
        sections={
            "intro.tex": r"\cite{from_intro}" + "\n",
            "method.tex": r"\cite{from_method}" + "\n",
        },
    )
    assert set(scan_tex_cite_keys(paper)) == {"from_main", "from_intro", "from_method"}


def test_scan_tex_cite_keys_no_main_only_sections(tmp_path):
    paper = _make_paper_dir(
        tmp_path,
        main_tex=None,
        sections={"intro.tex": r"\cite{only}" + "\n"},
    )
    assert scan_tex_cite_keys(paper) == ["only"]


def test_scan_tex_cite_keys_missing_dir_returns_empty(tmp_path):
    assert scan_tex_cite_keys(tmp_path / "nope") == []


# ---------------------------------------------------------------------------
# convert_document  (pandoc binary required)
# ---------------------------------------------------------------------------

requires_pandoc = pytest.mark.skipif(
    shutil.which("pandoc") is None, reason="pandoc binary not on PATH"
)


@requires_pandoc
def test_convert_document_md_to_tex(tmp_path):
    src = tmp_path / "draft.md"
    dest = tmp_path / "draft.tex"
    _write(src, "# Title\n\nBody text with **bold**.\n")
    result = convert_document(src, dest)
    assert result == dest
    text = dest.read_text(encoding="utf-8")
    assert "\\textbf{bold}" in text or "\\section" in text


@requires_pandoc
def test_convert_document_creates_parent_dir(tmp_path):
    src = tmp_path / "draft.md"
    dest = tmp_path / "out" / "deep" / "draft.tex"
    _write(src, "# T\n")
    convert_document(src, dest)
    assert dest.is_file()


@requires_pandoc
def test_convert_document_explicit_formats_override_extension(tmp_path):
    src = tmp_path / "draft.input"
    dest = tmp_path / "draft.output"
    _write(src, "# Title\n\nBody.\n")
    convert_document(src, dest, from_fmt="markdown", to_fmt="latex")
    assert "\\section" in dest.read_text(encoding="utf-8") or dest.stat().st_size > 0


def test_convert_document_rejects_unsupported_format(tmp_path):
    src = tmp_path / "x.xyz"
    _write(src, "junk")
    with pytest.raises(ValueError, match="source format"):
        convert_document(src, tmp_path / "out.md")


def test_convert_document_missing_src_raises(tmp_path):
    with pytest.raises(FileNotFoundError):
        convert_document(tmp_path / "nope.md", tmp_path / "out.tex")


# ---------------------------------------------------------------------------
# render_latex
# ---------------------------------------------------------------------------


def test_render_latex_no_main_tex_raises(tmp_path):
    paper = tmp_path / "paper"
    paper.mkdir()
    with pytest.raises(FileNotFoundError, match="no main.tex"):
        render_latex(paper)


def test_render_latex_no_engine_on_path_raises(tmp_path):
    paper = tmp_path / "paper"
    paper.mkdir()
    _write(paper / "main.tex", r"\documentclass{article}\begin{document}x\end{document}")
    with pytest.raises(RuntimeError, match="no LaTeX engine"):
        render_latex(paper, engines=("definitely-not-an-engine",))


@pytest.mark.skipif(
    shutil.which("pdflatex") is None and shutil.which("latexmk") is None
    and shutil.which("xelatex") is None and shutil.which("tectonic") is None,
    reason="no LaTeX engine available",
)
def test_render_latex_produces_pdf(tmp_path):
    paper = tmp_path / "paper"
    paper.mkdir()
    _write(
        paper / "main.tex",
        r"""\documentclass{article}
\begin{document}
Hello, ref-manager.
\end{document}
""",
    )
    pdf = render_latex(paper, timeout_sec=120)
    assert pdf == paper / "main.pdf"
    assert pdf.is_file()
    assert pdf.stat().st_size > 100


@pytest.mark.skipif(
    shutil.which("pdflatex") is None and shutil.which("latexmk") is None
    and shutil.which("xelatex") is None and shutil.which("tectonic") is None,
    reason="no LaTeX engine available",
)
def test_render_latex_surfaces_log_tail_on_compile_error(tmp_path):
    paper = tmp_path / "paper"
    paper.mkdir()
    _write(
        paper / "main.tex",
        r"""\documentclass{article}
\begin{document}
\undefinedcommandobviouslyfails
\end{document}
""",
    )
    with pytest.raises(RuntimeError) as exc:
        render_latex(paper, timeout_sec=60)
    msg = str(exc.value)
    assert "failed" in msg or "Undefined" in msg or "\\undefinedcommand" in msg
