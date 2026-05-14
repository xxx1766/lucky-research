"""Idempotency + venue-driven package selection for preamble injection."""
from pathlib import Path

import pytest

from research_assistant.pseudocode import preamble as pre


MAIN_TEX_BASE = r"""\documentclass{article}
\usepackage{graphicx}

\begin{document}
\section{Intro}
\end{document}
"""


def _write_main(tmp_path: Path, body: str = MAIN_TEX_BASE) -> Path:
    p = tmp_path / "main.tex"
    p.write_text(body, encoding="utf-8")
    return p


def test_default_package_injects_algpseudocode(tmp_path: Path):
    main = _write_main(tmp_path)
    result = pre.ensure_preamble(main)
    assert result.package == "algpseudocode"
    text = main.read_text()
    assert r"\usepackage{algorithm}" in text
    assert r"\usepackage{algpseudocode}" in text
    assert r"\usepackage{graphicx}" in text  # untouched


def test_idempotent_no_duplicate_lines(tmp_path: Path):
    main = _write_main(tmp_path)
    pre.ensure_preamble(main)
    second = pre.ensure_preamble(main)
    assert second.added_lines == ()
    text = main.read_text()
    assert text.count(r"\usepackage{algorithm}") == 1
    assert text.count(r"\usepackage{algpseudocode}") == 1


def test_venue_opt_in_algorithm2e(tmp_path: Path):
    venue_md = tmp_path / "_venue.md"
    venue_md.write_text(
        "---\nname: TPAMI-2026\npseudocode-package: algorithm2e\n---\n\nbody\n",
        encoding="utf-8",
    )
    main = _write_main(tmp_path)
    result = pre.ensure_preamble(main, venue_md_path=venue_md)
    assert result.package == "algorithm2e"
    text = main.read_text()
    assert r"\usepackage[ruled,vlined,linesnumbered]{algorithm2e}" in text
    assert r"\usepackage{algpseudocode}" not in text


def test_venue_default_when_no_frontmatter(tmp_path: Path):
    venue_md = tmp_path / "_venue.md"
    venue_md.write_text("# ICML 2026\nplain markdown, no frontmatter\n", encoding="utf-8")
    main = _write_main(tmp_path)
    result = pre.ensure_preamble(main, venue_md_path=venue_md)
    assert result.package == "algpseudocode"


def test_venue_default_when_missing_file(tmp_path: Path):
    main = _write_main(tmp_path)
    result = pre.ensure_preamble(main, venue_md_path=tmp_path / "absent.md")
    assert result.package == "algpseudocode"


def test_explicit_package_arg_wins(tmp_path: Path):
    venue_md = tmp_path / "_venue.md"
    venue_md.write_text(
        "---\npseudocode-package: algorithm2e\n---\n", encoding="utf-8"
    )
    main = _write_main(tmp_path)
    result = pre.ensure_preamble(main, venue_md_path=venue_md, package="algpseudocode")
    assert result.package == "algpseudocode"


def test_invalid_venue_value_falls_back_to_default(tmp_path: Path):
    venue_md = tmp_path / "_venue.md"
    venue_md.write_text(
        "---\npseudocode-package: bogus\n---\n", encoding="utf-8"
    )
    main = _write_main(tmp_path)
    result = pre.ensure_preamble(main, venue_md_path=venue_md)
    assert result.package == "algpseudocode"


def test_insertion_before_begin_document_when_no_usepackages(tmp_path: Path):
    body = r"""\documentclass{article}
\begin{document}
hi
\end{document}
"""
    main = _write_main(tmp_path, body=body)
    pre.ensure_preamble(main)
    text = main.read_text()
    pre_position = text.index(r"\usepackage{algorithm}")
    doc_position = text.index(r"\begin{document}")
    assert pre_position < doc_position


def test_missing_main_tex_raises(tmp_path: Path):
    with pytest.raises(FileNotFoundError):
        pre.ensure_preamble(tmp_path / "nope.tex")
