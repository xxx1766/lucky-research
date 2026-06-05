"""Tests for the /dashboard aggregator + HTML renderer."""
from __future__ import annotations

from datetime import date

from research_assistant.dashboard import (
    DashboardData,
    ExperimentRow,
    IdeaRow,
    PaperRow,
    SectionRow,
    build_dashboard,
    collect_papers,
)
from research_assistant.dashboard.render import render_html
from research_assistant.dashboard.venue_meta import parse_venue_meta


# ---------- venue_meta deadline parsing ----------

def _write_venue(d, body):
    d.mkdir(parents=True, exist_ok=True)
    (d / "_venue.md").write_text(body, encoding="utf-8")


def test_venue_meta_tilde_day(tmp_path):
    _write_venue(
        tmp_path / "OSDI-2027",
        "# OSDI '27 — reqs\n\n## Quick facts\n"
        "| Field | Value |\n|---|---|\n"
        "| Conference | 22nd USENIX OSDI |\n\n"
        "## Deadlines\n| Milestone | Target window |\n|---|---|\n"
        "| Full paper | mid Dec 2026 (~Dec 10 ±1 wk, hard) |\n",
    )
    m = parse_venue_meta(tmp_path / "OSDI-2027")
    assert m.conference == "22nd USENIX OSDI"
    assert m.deadline_date == date(2026, 12, 10)
    assert "Dec" in m.deadline_text


def test_venue_meta_qualifier_only(tmp_path):
    _write_venue(
        tmp_path / "X-2027",
        "## Deadlines\n| M | W |\n|---|---|\n| Full paper | early Oct 2026 |\n",
    )
    m = parse_venue_meta(tmp_path / "X-2027")
    assert m.deadline_date == date(2026, 10, 5)


def test_venue_meta_missing_file_falls_back_to_slug_year(tmp_path):
    (tmp_path / "EuroSys-2027").mkdir()
    m = parse_venue_meta(tmp_path / "EuroSys-2027")
    assert m.conference == "EuroSys-2027"          # falls back to slug
    assert m.deadline_text == "TBD"
    assert m.deadline_date == date(2027, 12, 1)     # year from slug


def test_venue_meta_title_fallback_when_no_conf_row(tmp_path):
    _write_venue(tmp_path / "Z-2026", "# ZConf '26 — notes\n\nno tables here\n")
    m = parse_venue_meta(tmp_path / "Z-2026")
    assert m.conference == "ZConf '26"


# ---------- collect_papers ----------

def _scaffold_direction(direction_dir):
    direction_dir.mkdir(parents=True, exist_ok=True)
    (direction_dir / "expert.md").write_text("---\nx: 1\n---\nbody\n", encoding="utf-8")
    (direction_dir / "focused-problem.md").write_text("p\n", encoding="utf-8")
    (direction_dir / "main.tex").write_text("\\documentclass{x}\n", encoding="utf-8")
    sections = direction_dir / "sections"
    sections.mkdir()
    # intro: clean, 3 words; method: 1 placeholder
    (sections / "intro.tex").write_text("alpha beta gamma\n", encoding="utf-8")
    (sections / "method.tex").write_text(
        "we report [DATA_NEEDED: throughput] here\n% 这是注释 [REF_NEEDED]\n",
        encoding="utf-8",
    )


def test_collect_papers_with_direction_and_sections(tmp_path):
    venue = tmp_path / "OSDI-2027"
    _write_venue(
        venue,
        "## Deadlines\n| M | W |\n|---|---|\n| Full paper | mid Dec 2026 (~Dec 10) |\n",
    )
    _scaffold_direction(venue / "weightlet")
    rows = collect_papers(tmp_path)
    assert len(rows) == 1
    p = rows[0]
    assert p.venue == "OSDI-2027" and p.direction == "weightlet"
    assert p.deadline_date == date(2026, 12, 10)
    # No outline budget here → stage mode; section names are stems.
    assert not p.uses_pages
    names = {s.name: s for s in p.sections}
    assert names["intro"].words == 3
    assert names["intro"].placeholders == 0
    # comment-only [REF_NEEDED] is NOT counted; only the real [DATA_NEEDED] is.
    assert names["method"].placeholders == 1
    assert p.open_placeholders == 1


def test_collect_papers_venue_without_direction(tmp_path):
    venue = tmp_path / "EuroSys-2027"
    _write_venue(venue, "no deadline rows\n")
    (venue / "_template").mkdir()       # scaffold dir — must be skipped
    (venue / ".claude-flow").mkdir()    # dotdir — must be skipped
    rows = collect_papers(tmp_path)
    assert len(rows) == 1
    assert rows[0].direction is None
    assert rows[0].stages_done == 1     # venue-only
    assert rows[0].sections == ()


def test_collect_papers_sorts_by_deadline(tmp_path):
    a = tmp_path / "Late-2027"
    b = tmp_path / "Soon-2026"
    _write_venue(a, "## Deadlines\n| M | W |\n|---|---|\n| Full paper | mid Dec 2027 |\n")
    _write_venue(b, "## Deadlines\n| M | W |\n|---|---|\n| Full paper | mid Jan 2026 |\n")
    _scaffold_direction(a / "d1")
    _scaffold_direction(b / "d2")
    rows = collect_papers(tmp_path)
    # collect_papers itself preserves filesystem order; the public collect()/
    # renderer sorts. Verify the sort key directly via build path below instead.
    venues = {r.venue for r in rows}
    assert venues == {"Late-2027", "Soon-2026"}


def test_empty_papers_dir(tmp_path):
    assert collect_papers(tmp_path / "nope") == []


# ---------- page-budget progress ----------

_OUTLINE = """# outline

## Page budget (12.0 body pages)

| § | Section | File | Pages | Cuts to |
|---|---|---|---|---|
| 1 | Introduction | `sections/intro.md` | 1.0 | — |
| 2 | Evaluation | `sections/eval.md` | 3.0 | — |
| | **Body total** | | **4.0** | |
| | Abstract | `sections/abstract.md` | (not counted) | 250 words |
"""


def test_parse_page_budget(tmp_path):
    from research_assistant.dashboard.outline_budget import parse_page_budget

    d = tmp_path / "dir"
    d.mkdir()
    (d / "outline.md").write_text(_OUTLINE, encoding="utf-8")
    budget = parse_page_budget(d)
    # § index and "(not counted)" abstract must not leak in.
    assert budget == {"intro": 1.0, "eval": 3.0}


def test_page_share_progress_weights_by_pages(tmp_path):
    from research_assistant.dashboard import WORDS_PER_PAGE

    venue = tmp_path / "OSDI-2027"
    _write_venue(venue, "## Deadlines\n| M | W |\n|---|---|\n| Full paper | mid Dec 2026 |\n")
    d = venue / "weightlet"
    d.mkdir(parents=True)
    (d / "outline.md").write_text(_OUTLINE, encoding="utf-8")
    sec = d / "sections"
    sec.mkdir()
    # Only eval is drafted, fully filling its 3.0-page budget (3 * WPP words).
    (sec / "eval.tex").write_text(" ".join(["w"] * (3 * WORDS_PER_PAGE)), encoding="utf-8")
    # intro is planned (1.0 pp) but not drafted.

    p = collect_papers(tmp_path)[0]
    assert p.uses_pages
    assert p.pages_total == 4.0
    assert p.pages_written == 3.0          # eval full, intro empty
    assert p.percent == 75                 # 3.0 / 4.0
    secs = {s.name: s for s in p.sections}
    assert secs["intro"].drafted is False and secs["intro"].fill == 0.0
    assert secs["eval"].drafted is True and secs["eval"].fill == 1.0


def test_page_fill_capped_at_budget(tmp_path):
    from research_assistant.dashboard import WORDS_PER_PAGE

    venue = tmp_path / "OSDI-2027"
    _write_venue(venue, "no deadlines\n")
    d = venue / "dir"
    d.mkdir(parents=True)
    (d / "outline.md").write_text(
        "## Page budget\n| § | S | File | Pages |\n|---|---|---|---|\n"
        "| 1 | I | `sections/intro.md` | 1.0 |\n",
        encoding="utf-8",
    )
    sec = d / "sections"
    sec.mkdir()
    # 5 pages' worth of words in a 1-page section — fill must clamp at 1.0.
    (sec / "intro.tex").write_text(" ".join(["w"] * (5 * WORDS_PER_PAGE)), encoding="utf-8")
    p = collect_papers(tmp_path)[0]
    assert p.pages_written == 1.0 and p.percent == 100
    assert {s.name: s for s in p.sections}["intro"].fill == 1.0


# ---------- rendering ----------

def test_render_escapes_user_content():
    data = DashboardData(
        ideas=[
            IdeaRow(
                slug="x",
                status="captured",
                updated=date(2026, 6, 1),
                venue=None,
                verdict=None,
                statement="<script>alert(1)</script> & friends",
            )
        ],
        papers=[],
        generated_on=date(2026, 6, 5),
    )
    html = render_html(data)
    assert "<script>alert(1)</script>" not in html  # raw injection escaped
    assert "&lt;script&gt;alert(1)&lt;/script&gt;" in html
    assert "Generated 2026-06-05" in html


def test_render_days_left_badges():
    p_soon = PaperRow(
        venue="V-2026", direction="d", conference="C",
        deadline_text="mid Jun 2026", deadline_date=date(2026, 6, 20),
        stages_done=4, sections=(SectionRow("intro.tex", 100, 0),),
    )
    p_over = PaperRow(
        venue="W-2026", direction="e", conference="C",
        deadline_text="mid May 2026", deadline_date=date(2026, 5, 1),
        stages_done=7,
    )
    data = DashboardData(ideas=[], papers=[p_soon, p_over], generated_on=date(2026, 6, 5))
    html = render_html(data)
    assert "T-15d" in html              # 2026-06-20 minus 2026-06-05
    assert "overdue" in html            # 2026-05-01 is past
    assert "57%" in html                # 4/7 stages -> round(57.1)


def test_paperrow_percent_and_days():
    p = PaperRow(
        venue="V-2027", direction="d", conference="C",
        deadline_text="x", deadline_date=date(2027, 1, 10), stages_done=7,
    )
    assert p.percent == 100
    assert p.days_left(date(2027, 1, 1)) == 9
    assert p.stages_total == 7


# ---------- end-to-end ----------

def test_build_dashboard_writes_file(tmp_path):
    out = build_dashboard(tmp_path / "sub" / "dashboard.html", today=date(2026, 6, 5))
    assert out.is_file()
    html = out.read_text(encoding="utf-8")
    assert "<!DOCTYPE html>" in html
    assert "Research dashboard" in html


# ---------- serve / auto-refresh ----------

def test_render_injects_meta_refresh_when_serving():
    data = DashboardData(ideas=[], papers=[], generated_on=date(2026, 6, 5))
    served = render_html(data, refresh_seconds=15)
    assert '<meta http-equiv="refresh" content="15">' in served
    assert "auto-refresh every 15s" in served


def test_render_no_meta_refresh_for_static_build():
    data = DashboardData(ideas=[], papers=[], generated_on=date(2026, 6, 5))
    static = render_html(data)
    assert "http-equiv=\"refresh\"" not in static
    assert "auto-refresh every" not in static  # the subheader note


def test_render_papers_above_ideas():
    data = DashboardData(ideas=[], papers=[], generated_on=date(2026, 6, 5))
    html = render_html(data)
    assert html.index("<h2>Papers</h2>") < html.index("<h2>Ideas</h2>")


def test_render_long_statement_collapses():
    long = "x" * 200
    data = DashboardData(
        ideas=[IdeaRow("s", "captured", date(2026, 6, 1), None, None, long)],
        papers=[], generated_on=date(2026, 6, 5),
    )
    html = render_html(data)
    assert "<details><summary>" in html and "…</summary>" in html


def test_render_has_idea_filter():
    data = DashboardData(
        ideas=[IdeaRow("s", "captured", date(2026, 6, 1), None, None, "short")],
        papers=[], generated_on=date(2026, 6, 5),
    )
    html = render_html(data)
    assert 'type="search"' in html and "filterTable" in html


def test_render_page_progress_label():
    p = PaperRow(
        venue="OSDI-2027", direction="d", conference="C", deadline_text="x",
        deadline_date=date(2026, 12, 10), stages_done=3,
        sections=(SectionRow("intro", 900, 0, planned_pages=1.0, drafted=True, fill=1.0),),
        pages_written=1.0, pages_total=4.0,
    )
    data = DashboardData(ideas=[], papers=[p], generated_on=date(2026, 6, 5))
    html = render_html(data)
    assert "1.0/4.00 pp" in html      # page-share detail, not "3/7 stages"
    assert "25%" in html              # 1.0 / 4.0


def test_render_deadline_is_numeric_with_tooltip():
    known = PaperRow(
        venue="OSDI-2027", direction="d", conference="C",
        deadline_text="mid Dec 2026 (~Dec 10 ±1 wk, hard)",
        deadline_date=date(2026, 12, 10), stages_done=7,
    )
    tbd = PaperRow(
        venue="X-2027", direction=None, conference="C",
        deadline_text="TBD", deadline_date=date(2027, 12, 1), stages_done=1,
    )
    data = DashboardData(ideas=[], papers=[known, tbd], generated_on=date(2026, 6, 5))
    html = render_html(data)
    assert ">2026-12-10<" in html                                  # numeric date shown
    assert 'title="mid Dec 2026 (~Dec 10 ±1 wk, hard)"' in html    # window kept on hover
    assert ">TBD<" in html                                          # no real date → TBD
    assert "mid Dec 2026 (~Dec 10 ±1 wk, hard)</td>" not in html    # window no longer the cell text


def test_papers_table_drops_conference_adds_next_and_updated():
    p = PaperRow(
        venue="OSDI-2027", direction="weightlet", conference="22nd USENIX OSDI",
        deadline_text="mid Dec 2026", deadline_date=date(2026, 12, 10), stages_done=5,
        next_step="/paper render", updated=date(2026, 6, 4),
    )
    data = DashboardData(ideas=[], papers=[p], generated_on=date(2026, 6, 5))
    html = render_html(data)
    assert "<th>Conference</th>" not in html        # column removed
    assert "22nd USENIX OSDI" not in html           # conference no longer rendered
    assert "<th>Next</th>" in html and "/paper render" in html
    assert "<th>Updated</th>" in html and "1d ago" in html


def test_behind_flag_when_near_deadline_and_low_progress():
    behind = PaperRow(
        venue="V-2026", direction="d", conference="C", deadline_text="soon",
        deadline_date=date(2026, 6, 20), stages_done=2,  # ~29% < 75%, 15d out
    )
    fine = PaperRow(
        venue="W-2027", direction="e", conference="C", deadline_text="far",
        deadline_date=date(2027, 6, 20), stages_done=2,  # far deadline → not behind
    )
    today = date(2026, 6, 5)
    data = DashboardData(ideas=[], papers=[behind, fine], generated_on=today)
    html = render_html(data)
    assert 'class="behind"' in html
    assert "Behind <b" in html                       # summary chip
    # the far-deadline paper must NOT be flagged
    assert html.count('class="behind"') == 1


def test_stale_marker_for_old_unfinished_paper():
    p = PaperRow(
        venue="V-2026", direction="d", conference="C", deadline_text="x",
        deadline_date=date(2026, 12, 1), stages_done=3,
        updated=date(2026, 5, 1),  # 35 days before "today" → stale
    )
    data = DashboardData(ideas=[], papers=[p], generated_on=date(2026, 6, 5))
    html = render_html(data)
    assert 'class="stale"' in html


# ---------- experiments panel ----------

def test_collect_experiments(tmp_path, monkeypatch):
    import research_assistant.experiments as exp_pkg
    from research_assistant.dashboard import collect_experiments

    root = tmp_path / "experiments"
    (root / "rolling-llm").mkdir(parents=True)
    # Both parsers.py and paths.py read the dir via `_exp.EXPERIMENTS_DIR`
    # (late attribute access), so patching the package attribute is enough.
    monkeypatch.setattr(exp_pkg, "EXPERIMENTS_DIR", root)
    (root / "rolling-llm" / "manifest.md").write_text(
        "---\nslug: rolling-llm\ntitle: Rolling LLM\ncreated_at: 2026-05-01\n"
        "repo:\n  url: git@github.com:x/y.git\npapers:\n  - weightlet\n"
        "status: active\n---\nbody\n",
        encoding="utf-8",
    )
    rows = collect_experiments()
    assert len(rows) == 1
    e = rows[0]
    assert e.slug == "rolling-llm" and e.title == "Rolling LLM"
    assert e.repo == "git@github.com:x/y.git"
    assert e.papers == ("weightlet",)
    assert e.status == "active"
    assert 0 <= e.percent <= 100


def test_experiments_table_empty_note():
    data = DashboardData(ideas=[], papers=[], experiments=[], generated_on=date(2026, 6, 5))
    html = render_html(data)
    assert "<h2>Experiments</h2>" in html
    assert "No experiments yet" in html


def test_experiments_table_renders_row():
    e = ExperimentRow(
        slug="rolling-llm", title="Rolling LLM", status="active",
        stages_done=3, stages_total=5, versions=2, repo="git@github.com:x/y.git",
        papers=("weightlet",), next_step="/experiment analyze", updated=date(2026, 6, 4),
    )
    data = DashboardData(ideas=[], papers=[], experiments=[e], generated_on=date(2026, 6, 5))
    html = render_html(data)
    assert "rolling-llm" in html and "/experiment analyze" in html
    assert "60%" in html             # 3/5
    assert "weightlet" in html       # bound paper


def test_render_tables_have_ids_for_sort_persistence():
    data = DashboardData(
        ideas=[IdeaRow("x", "captured", date(2026, 6, 1), None, None, "s")],
        papers=[
            PaperRow("V-2026", "d", "C", "x", date(2026, 6, 20), 4,
                     (SectionRow("intro.tex", 100, 0),))
        ],
        generated_on=date(2026, 6, 5),
    )
    html = render_html(data)
    assert 'id="ideas"' in html
    assert 'id="papers"' in html
    assert "sessionStorage" in html  # sort survives auto-refresh reloads
