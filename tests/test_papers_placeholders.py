"""Tests for `research_assistant.papers.placeholders` — evidence-first tokens."""
from __future__ import annotations

from research_assistant.papers.placeholders import (
    DebtSummary,
    debt_summary,
    scan_placeholders,
)


def _section(direction_dir, name: str, text: str) -> None:
    sections = direction_dir / "sections"
    sections.mkdir(exist_ok=True)
    (sections / name).write_text(text, encoding="utf-8")


def test_scan_empty_when_missing(tmp_path):
    assert scan_placeholders(tmp_path / "nope") == []


def test_scan_no_tokens(tmp_path):
    _section(tmp_path, "intro.tex", "Plain prose with a \\cite{vaswani2017} key.\n")
    assert scan_placeholders(tmp_path) == []


def test_scan_finds_each_token_kind(tmp_path):
    _section(
        tmp_path,
        "method.tex",
        "We use [REF_NEEDED: cite the original sampler].\n"
        "See [FIGURE_NEEDED: architecture overview].\n"
        "Accuracy is [DATA_NEEDED: fill from v1.2].\n"
        "This [CLAIM_UNVERIFIED: matches SOTA] on the benchmark.\n",
    )
    found = scan_placeholders(tmp_path)
    assert [p.token for p in found] == [
        "REF_NEEDED",
        "FIGURE_NEEDED",
        "DATA_NEEDED",
        "CLAIM_UNVERIFIED",
    ]
    assert [p.debt for p in found] == ["citation", "figure", "evidence", "evidence"]
    # line numbers + hints captured
    assert found[0].line == 1
    assert found[0].hint == "cite the original sampler"
    assert found[2].line == 3
    assert all(p.file == "sections/method.tex" for p in found)


def test_scan_token_without_hint(tmp_path):
    _section(tmp_path, "intro.tex", "Bare token [REF_NEEDED] here.\n")
    found = scan_placeholders(tmp_path)
    assert len(found) == 1
    assert found[0].hint == ""


def test_scan_ignores_tokens_in_comments(tmp_path):
    # The Chinese-translation comment shadows the English line; a token that
    # appears only after an un-escaped % must not be counted.
    _section(
        tmp_path,
        "intro.tex",
        "% 这里需要引用 [REF_NEEDED: 中文注释]\n"
        "Real prose with [DATA_NEEDED: from experiment].\n",
    )
    found = scan_placeholders(tmp_path)
    assert len(found) == 1
    assert found[0].token == "DATA_NEEDED"


def test_scan_includes_main_tex(tmp_path):
    (tmp_path / "main.tex").write_text("Title needs [REF_NEEDED: x].\n", encoding="utf-8")
    found = scan_placeholders(tmp_path)
    assert len(found) == 1
    assert found[0].file == "main.tex"


def test_debt_summary_counts_by_class(tmp_path):
    _section(
        tmp_path,
        "method.tex",
        "[REF_NEEDED: a] [REF_NEEDED: b] [FIGURE_NEEDED: c] [DATA_NEEDED: d]\n",
    )
    summary = debt_summary(tmp_path)
    assert summary.citation == 2
    assert summary.figure == 1
    assert summary.evidence == 1
    assert summary.total == 4


def test_debt_summary_adds_unresolved_cites(tmp_path):
    # cited key with no refs.bib entry -> citation debt
    _section(tmp_path, "intro.tex", "As shown \\cite{ghost2025}.\n")
    summary = debt_summary(tmp_path)
    assert summary.citation == 1  # the unresolved \cite
    assert summary.total == 1


def test_debt_summary_resolved_cite_not_counted(tmp_path):
    _section(tmp_path, "intro.tex", "As shown \\cite{real2025}.\n")
    (tmp_path / "refs.bib").write_text(
        "@article{real2025, title={x}, author={Y, Z}}\n", encoding="utf-8"
    )
    summary = debt_summary(tmp_path)
    assert summary.citation == 0
    assert summary.total == 0


def test_debt_summary_as_line():
    assert DebtSummary().as_line() == "none"
    line = DebtSummary(citation=1, evidence=2).as_line()
    assert line.startswith("3 open · ")
    assert "1 citation" in line
    assert "2 evidence" in line
    assert "figure" not in line  # zero classes omitted
