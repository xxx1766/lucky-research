"""Tests for `research_assistant.papers.claim_strength` — overclaim scan."""
from __future__ import annotations

from research_assistant.papers.claim_strength import scan_strength_words


def _section(direction_dir, name: str, text: str) -> None:
    sections = direction_dir / "sections"
    sections.mkdir(exist_ok=True)
    (sections / name).write_text(text, encoding="utf-8")


def test_empty_when_missing(tmp_path):
    assert scan_strength_words(tmp_path / "nope") == []


def test_no_hits_on_plain_prose(tmp_path):
    _section(tmp_path, "method.tex", "We train the model on the dataset.\n")
    assert scan_strength_words(tmp_path) == []


def test_flags_each_category(tmp_path):
    _section(
        tmp_path,
        "results.tex",
        "Our method significantly improves accuracy.\n"   # significance
        "The approach is robust to noise.\n"              # robustness
        "This demonstrates the benefit.\n"                # demonstration
        "It generalizes to new domains.\n"               # generalization
        "We achieve state-of-the-art results.\n"         # sota
        "This proves the hypothesis.\n",                  # proof
    )
    cats = {h.category for h in scan_strength_words(tmp_path)}
    assert cats == {
        "significance", "robustness", "demonstration",
        "generalization", "sota", "proof",
    }


def test_hit_carries_required_and_downgrade(tmp_path):
    _section(tmp_path, "r.tex", "We achieve SOTA performance.\n")
    hits = scan_strength_words(tmp_path)
    assert len(hits) == 1
    h = hits[0]
    assert h.word == "SOTA"
    assert h.line == 1
    assert "baseline" in h.required
    assert h.downgrade


def test_word_boundary_no_false_positive(tmp_path):
    # "insignificant" / "approves" must not trigger significant / proves.
    _section(
        tmp_path,
        "m.tex",
        "The difference is insignificant here.\n"
        "The committee approves the budget.\n"
        "We use a generative model.\n",  # not 'generalize'
    )
    assert scan_strength_words(tmp_path) == []


def test_ignores_comment_lines(tmp_path):
    _section(
        tmp_path,
        "intro.tex",
        "% 这里我们 significantly 改进\n"      # in a comment -> ignored
        "We report the measured gain.\n",       # clean prose
    )
    assert scan_strength_words(tmp_path) == []


def test_state_of_the_art_spaced_and_hyphenated(tmp_path):
    _section(
        tmp_path,
        "r.tex",
        "A state-of-the-art system.\n"
        "Beats the state of the art.\n",
    )
    hits = scan_strength_words(tmp_path)
    assert [h.category for h in hits] == ["sota", "sota"]


def test_results_ordered_by_file_line(tmp_path):
    _section(tmp_path, "a.tex", "robust\n")
    _section(tmp_path, "b.tex", "significant\n")
    hits = scan_strength_words(tmp_path)
    assert [h.file for h in hits] == ["sections/a.tex", "sections/b.tex"]


def test_scans_main_tex(tmp_path):
    (tmp_path / "main.tex").write_text("We prove it.\n", encoding="utf-8")
    hits = scan_strength_words(tmp_path)
    assert len(hits) == 1
    assert hits[0].file == "main.tex"
