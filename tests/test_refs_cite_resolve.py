"""Tests for `research_assistant.refs` cite-resolution helpers (citation debt)."""
from __future__ import annotations

from research_assistant.refs import bib_entry_keys, unresolved_cite_keys


def _write(path, text: str) -> None:
    path.write_text(text, encoding="utf-8")


def test_bib_entry_keys_empty_when_missing(tmp_path):
    assert bib_entry_keys(tmp_path / "refs.bib") == set()


def test_bib_entry_keys_parsed(tmp_path):
    refs = tmp_path / "refs.bib"
    _write(
        refs,
        "@article{vaswani2017, title={Attention}, author={Vaswani, A}}\n"
        "@inproceedings{he2016, title={ResNet}, author={He, K}}\n",
    )
    assert bib_entry_keys(refs) == {"vaswani2017", "he2016"}


def test_bib_entry_keys_malformed_returns_empty(tmp_path):
    refs = tmp_path / "refs.bib"
    _write(refs, "this is not bibtex {{{")
    # Malformed -> empty set (every cite reads as unresolved, no crash).
    assert bib_entry_keys(refs) == set()


def test_unresolved_cite_keys_flags_missing(tmp_path):
    sections = tmp_path / "sections"
    sections.mkdir()
    _write(sections / "intro.tex", "Prior work \\cite{vaswani2017} and \\cite{ghost2025}.\n")
    _write(tmp_path / "refs.bib", "@article{vaswani2017, title={x}, author={V, A}}\n")
    assert unresolved_cite_keys(tmp_path) == ["ghost2025"]


def test_unresolved_cite_keys_none_when_all_resolved(tmp_path):
    sections = tmp_path / "sections"
    sections.mkdir()
    _write(sections / "intro.tex", "See \\citet{he2016}.\n")
    _write(tmp_path / "refs.bib", "@inproceedings{he2016, title={x}, author={H, K}}\n")
    assert unresolved_cite_keys(tmp_path) == []


def test_unresolved_cite_keys_all_missing_when_no_bib(tmp_path):
    sections = tmp_path / "sections"
    sections.mkdir()
    _write(sections / "intro.tex", "See \\cite{a} and \\cite{b}.\n")
    assert unresolved_cite_keys(tmp_path) == ["a", "b"]
