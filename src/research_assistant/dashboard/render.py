"""Render :class:`DashboardData` to one self-contained HTML page.

No external assets, no build step: inline ``<style>`` + a ~40-line vanilla-JS
table sorter. Open the file in any browser; click a column header to sort
(papers default to soonest-deadline-first). Every value that originates from
user content (idea statements, venue names, slugs) is HTML-escaped — the page
is written under ``outputs/`` and must be safe to open locally.
"""
from __future__ import annotations

from datetime import date
from html import escape

from research_assistant.dashboard import (
    DashboardData,
    ExperimentRow,
    IdeaRow,
    PaperRow,
)

# A paper is "behind" if its deadline is close (or past) and progress is low —
# this is what the row-tint + ⚠ flag surface so you can triage at a glance.
_BEHIND_DAYS = 30
_BEHIND_PCT = 75
# A paper/experiment is "stale" if its writing surface hasn't changed in a
# while and it isn't finished — mirrors /mentor's stale-experiment nudge.
_STALE_DAYS = 21

_CSS = """
:root{--fg:#1c2128;--muted:#656d76;--line:#d0d7de;--bg:#f6f8fa;--accent:#0969da;
--ok:#1a7f37;--warn:#9a6700;--bad:#cf222e;--barbg:#eaeef2}
*{box-sizing:border-box}
body{font:14px/1.5 -apple-system,BlinkMacSystemFont,"Segoe UI",Helvetica,Arial,sans-serif;
color:var(--fg);margin:0;padding:32px;background:#fff}
h1{font-size:22px;margin:0 0 4px}h2{font-size:16px;margin:32px 0 10px}
.sub{color:var(--muted);font-size:13px;margin-bottom:20px}
.chips{display:flex;gap:10px;flex-wrap:wrap;margin-bottom:8px}
.chip{background:var(--bg);border:1px solid var(--line);border-radius:20px;
padding:4px 12px;font-size:13px}.chip b{color:var(--accent)}
table{border-collapse:collapse;width:100%;font-size:13px;margin-bottom:8px}
th,td{text-align:left;padding:7px 10px;border-bottom:1px solid var(--line);vertical-align:top}
th{background:var(--bg);cursor:pointer;user-select:none;white-space:nowrap;font-weight:600}
th:hover{color:var(--accent)}th .arr{color:var(--muted);font-size:11px}
tr:hover td{background:#fafbfc}
code{font:12px ui-monospace,SFMono-Regular,Menlo,monospace;background:var(--bg);
padding:1px 5px;border-radius:4px}
.bar{position:relative;height:14px;width:120px;background:var(--barbg);border-radius:7px;
overflow:hidden;display:inline-block;vertical-align:middle}
.bar>span{position:absolute;left:0;top:0;bottom:0;background:var(--accent)}
.pct{margin-left:8px;font-variant-numeric:tabular-nums}
.badge{font-variant-numeric:tabular-nums}
.soon{color:var(--warn);font-weight:600}.over{color:var(--bad);font-weight:600}
.statement{max-width:560px;color:var(--muted)}
details summary{cursor:pointer;font-weight:600}
ul.sections{margin:6px 0 2px;padding-left:18px;color:var(--muted)}
ul.sections li{font-variant-numeric:tabular-nums}
ul.sections .ph{color:var(--warn)}ul.sections .clean{color:var(--ok)}
.empty{color:var(--muted);font-style:italic;padding:8px 0}
.st{display:inline-block;padding:1px 8px;border-radius:10px;background:var(--bg);
border:1px solid var(--line);font-size:12px}
.statement details summary{font-weight:400;color:var(--fg)}
input.filter{margin:0 0 8px;padding:5px 10px;width:280px;max-width:100%;
border:1px solid var(--line);border-radius:6px;font-size:13px}
input.filter:focus{outline:none;border-color:var(--accent)}
tr.behind td{background:#fff5f5}tr.behind:hover td{background:#ffecec}
.flag{color:var(--bad);font-weight:600;margin-right:4px}
.next{font-size:12px;color:var(--muted)}
.stale{color:var(--warn);font-weight:600}
"""

_JS = """
function sortTable(t,col,th,save){
 var tb=t.tBodies[0],rows=[].slice.call(tb.rows);
 var asc=th.getAttribute('data-asc')!=='true';
 [].forEach.call(t.tHead.rows[0].cells,function(c){c.removeAttribute('data-asc');
   var a=c.querySelector('.arr');if(a)a.textContent='';});
 th.setAttribute('data-asc',asc);
 var arr=th.querySelector('.arr');if(arr)arr.textContent=asc?'▲':'▼';
 rows.sort(function(a,b){
  var x=a.cells[col],y=b.cells[col];
  var xv=x.getAttribute('data-sort'),yv=y.getAttribute('data-sort');
  xv=xv!==null?xv:x.textContent;yv=yv!==null?yv:y.textContent;
  var xn=parseFloat(xv),yn=parseFloat(yv),num=!isNaN(xn)&&!isNaN(yn);
  var r=num?xn-yn:String(xv).localeCompare(String(yv));
  return asc?r:-r;});
 rows.forEach(function(r){tb.appendChild(r);});
 if(save!==false&&t.id){try{sessionStorage.setItem('sort:'+t.id,col+','+asc);}catch(e){}}
}
function filterTable(id,q){
 var t=document.getElementById(id);if(!t)return;q=q.toLowerCase();
 [].forEach.call(t.tBodies[0].rows,function(r){
  r.style.display=r.textContent.toLowerCase().indexOf(q)>=0?'':'none';});
}
[].forEach.call(document.querySelectorAll('table.sortable'),function(t){
 [].forEach.call(t.tHead.rows[0].cells,function(th,i){
  th.innerHTML+=' <span class="arr"></span>';
  th.addEventListener('click',function(){sortTable(t,i,th);});});
 // restore the active sort so auto-refresh reloads don't reset it
 if(t.id){try{var s=sessionStorage.getItem('sort:'+t.id);
  if(s){var p=s.split(','),ci=+p[0],asc=p[1]==='true',h=t.tHead.rows[0].cells[ci];
   if(h){h.setAttribute('data-asc',(!asc).toString());sortTable(t,ci,h,false);}}
 }catch(e){}}});
"""


def _esc(v: object) -> str:
    return escape("" if v is None else str(v))


def _ideas_table(ideas: list[IdeaRow]) -> str:
    if not ideas:
        return '<p class="empty">No ideas captured yet — run <code>/idea-check</code>.</p>'
    head = (
        "<thead><tr><th>Idea</th><th>Status</th><th>Updated</th>"
        "<th>Venue</th><th>Verdict</th><th>Statement</th></tr></thead>"
    )
    rows = []
    for i in ideas:
        upd = i.updated.isoformat() if i.updated else ""
        rows.append(
            "<tr>"
            f"<td><code>{_esc(i.slug)}</code></td>"
            f'<td><span class="st">{_esc(i.status)}</span></td>'
            f'<td data-sort="{_esc(upd)}">{_esc(upd) or "—"}</td>'
            f"<td>{_esc(i.venue) if i.venue else '—'}</td>"
            f"<td>{_esc(i.verdict) if i.verdict else '—'}</td>"
            f'<td class="statement">{_statement_cell(i.statement)}</td>'
            "</tr>"
        )
    search = (
        '<input type="search" class="filter" placeholder="filter ideas…" '
        "oninput=\"filterTable('ideas',this.value)\">"
    )
    return (
        f"{search}"
        f'<table class="sortable" id="ideas">{head}<tbody>{"".join(rows)}</tbody></table>'
    )


def _statement_cell(statement: str, preview: int = 90) -> str:
    """Collapsible statement: a short summary that expands to the full text."""
    full = _esc(statement)
    if len(statement) <= preview:
        return full
    head = _esc(statement[:preview].rstrip())
    return f"<details><summary>{head}…</summary>{full}</details>"


def _sections_detail(p: PaperRow) -> str:
    label = _esc(p.direction)
    if not p.sections:
        return label
    items = []
    for s in p.sections:
        bits: list[str] = []
        if s.planned_pages is not None:
            bits.append(f"{s.planned_pages:g}pp planned")
        if not s.drafted:
            bits.append('<span class="ph">not started</span>')
        else:
            bits.append(f"{s.words}w")
            if s.planned_pages is not None:
                bits.append(f"{round(s.fill * 100)}% filled")
            if s.placeholders:
                bits.append(
                    f'<span class="ph">{s.placeholders} placeholder'
                    f'{"s" if s.placeholders != 1 else ""} ⚠</span>'
                )
            else:
                bits.append('<span class="clean">✓</span>')
        items.append(f"<li><code>{_esc(s.name)}</code> · {' · '.join(bits)}</li>")
    return (
        f"<details><summary>{label}</summary>"
        f'<ul class="sections">{"".join(items)}</ul></details>'
    )


def _deadline_cell(p: PaperRow) -> str:
    """Numeric ISO date (e.g. ``2026-12-10``); the original fuzzy window from
    ``_venue.md`` is preserved as a hover tooltip. ``TBD`` when unknown."""
    iso = p.deadline_date.isoformat() if p.deadline_date else ""
    known = bool(p.deadline_date) and p.deadline_text != "TBD"
    show = iso if known else "TBD"
    title = f' title="{_esc(p.deadline_text)}"' if known else ""
    return f'<td data-sort="{iso or "9999-12-31"}"{title}>{show}</td>'


def _days_cell(p: PaperRow, today: date) -> str:
    d = p.days_left(today)
    if d is None:
        return '<td data-sort="999999">—</td>'
    if d < 0:
        return f'<td data-sort="{d}"><span class="over badge">{d}d (overdue)</span></td>'
    cls = "soon" if d <= 30 else "badge"
    return f'<td data-sort="{d}"><span class="{cls}">T-{d}d</span></td>'


def _updated_cell(updated: date | None, today: date, *, stale: bool) -> str:
    """Relative 'Nd ago' (ISO on hover); amber when stale."""
    if updated is None:
        return '<td data-sort="999999">—</td>'
    days = max(0, (today - updated).days)
    rel = "today" if days == 0 else f"{days}d ago"
    cls = ' class="stale"' if stale else ""
    iso = updated.isoformat()
    return f'<td data-sort="{days}" title="{iso}"><span{cls}>{rel}</span></td>'


def _is_behind(p: PaperRow, today: date) -> bool:
    d = p.days_left(today)
    if d is None or p.percent >= 100:
        return False
    if d < 0:
        return True                       # past deadline, not done
    return d <= _BEHIND_DAYS and p.percent < _BEHIND_PCT


def _is_stale(updated: date | None, today: date, percent: int) -> bool:
    if updated is None or percent >= 100:
        return False
    return (today - updated).days >= _STALE_DAYS


def _papers_table(papers: list[PaperRow], today: date) -> str:
    if not papers:
        return '<p class="empty">No papers yet — run <code>/paper venue</code>.</p>'
    head = (
        "<thead><tr><th>Venue</th><th>Paper</th><th>Progress</th><th>Deadline</th>"
        "<th>Due in</th><th>Updated</th><th>Gaps</th><th>Next</th></tr></thead>"
    )
    rows = []
    for p in papers:
        behind = _is_behind(p, today)
        bar = (
            f'<span class="bar"><span style="width:{p.percent}%"></span></span>'
            f'<span class="pct">{p.percent}% '
            f"({_esc(p.progress_detail)})</span>"
        )
        flag = '<span class="flag" title="behind: near deadline, low progress">⚠</span>' if behind else ""
        paper_cell = (
            _sections_detail(p) if p.direction else '<span class="empty">(no direction)</span>'
        )
        stale = _is_stale(p.updated, today, p.percent)
        rows.append(
            f'<tr class="{"behind" if behind else ""}">'
            f"<td><code>{_esc(p.venue)}</code></td>"
            f"<td>{flag}{paper_cell}</td>"
            f'<td data-sort="{p.percent}">{bar}</td>'
            f"{_deadline_cell(p)}"
            f"{_days_cell(p, today)}"
            f"{_updated_cell(p.updated, today, stale=stale)}"
            f'<td data-sort="{p.open_placeholders}">{p.open_placeholders or "—"}</td>'
            f'<td class="next">{_esc(p.next_step)}</td>'
            "</tr>"
        )
    return f'<table class="sortable" id="papers">{head}<tbody>{"".join(rows)}</tbody></table>'


def _experiments_table(experiments: list[ExperimentRow], today: date) -> str:
    if not experiments:
        return (
            '<p class="empty">No experiments yet — run <code>/experiment init</code>.</p>'
        )
    head = (
        "<thead><tr><th>Experiment</th><th>Status</th><th>Progress</th>"
        "<th>Versions</th><th>Papers</th><th>Updated</th><th>Next</th></tr></thead>"
    )
    rows = []
    for e in experiments:
        bar = (
            f'<span class="bar"><span style="width:{e.percent}%"></span></span>'
            f'<span class="pct">{e.percent}% ({e.stages_done}/{e.stages_total})</span>'
        )
        name = (
            f'<details><summary>{_esc(e.slug)}</summary>'
            f'<div class="next">{_esc(e.title)}'
            + (f' · <code>{_esc(e.repo)}</code>' if e.repo else "")
            + "</div></details>"
            if (e.title and e.title != e.slug) or e.repo
            else f"<code>{_esc(e.slug)}</code>"
        )
        papers = ", ".join(_esc(s) for s in e.papers) if e.papers else "—"
        stale = _is_stale(e.updated, today, e.percent)
        rows.append(
            "<tr>"
            f"<td>{name}</td>"
            f'<td><span class="st">{_esc(e.status)}</span></td>'
            f'<td data-sort="{e.percent}">{bar}</td>'
            f'<td data-sort="{e.versions}">{e.versions or "—"}</td>'
            f"<td>{papers}</td>"
            f"{_updated_cell(e.updated, today, stale=stale)}"
            f'<td class="next">{_esc(e.next_step)}</td>'
            "</tr>"
        )
    return (
        f'<table class="sortable" id="experiments">{head}'
        f'<tbody>{"".join(rows)}</tbody></table>'
    )


def render_html(data: DashboardData, *, refresh_seconds: int | None = None) -> str:
    """Produce the full standalone HTML document.

    When ``refresh_seconds`` is set (the ``serve`` mode), a ``<meta refresh>``
    tag is injected so the page reloads itself on that cadence; each reload hits
    the server, which regenerates from current disk state. The active column
    sort is preserved across reloads via ``sessionStorage``.
    """
    today = data.generated_on or date.today()
    meta_refresh = (
        f'<meta http-equiv="refresh" content="{refresh_seconds}">'
        if refresh_seconds and refresh_seconds > 0
        else ""
    )
    refresh_note = (
        f" · auto-refresh every {refresh_seconds}s"
        if refresh_seconds and refresh_seconds > 0
        else ""
    )
    soonest = next((p for p in data.papers if p.days_left(today) is not None), None)
    soon_txt = (
        f"{_esc(soonest.venue)} · {soonest.deadline_date.isoformat()}"
        if soonest and soonest.deadline_date
        else "—"
    )
    behind_n = sum(1 for p in data.papers if _is_behind(p, today))
    behind_chip = (
        f'<span class="chip">Behind <b style="color:var(--bad)">{behind_n}</b></span>'
        if behind_n
        else ""
    )
    chips = (
        f'<span class="chip">Papers <b>{len(data.papers)}</b></span>'
        f'<span class="chip">Experiments <b>{len(data.experiments)}</b></span>'
        f'<span class="chip">Ideas <b>{len(data.ideas)}</b></span>'
        f'<span class="chip">Next deadline <b>{soon_txt}</b></span>'
        f"{behind_chip}"
    )
    return f"""<!DOCTYPE html>
<html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">{meta_refresh}
<title>Research dashboard</title><style>{_CSS}</style></head>
<body>
<h1>Research dashboard</h1>
<div class="sub">Generated {today.isoformat()} · click any column header to re-sort{refresh_note}</div>
<div class="chips">{chips}</div>
<h2>Papers</h2>
{_papers_table(data.papers, today)}
<h2>Experiments</h2>
{_experiments_table(data.experiments, today)}
<h2>Ideas</h2>
{_ideas_table(data.ideas)}
<script>{_JS}</script>
</body></html>
"""
