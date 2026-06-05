---
name: dashboard
description: Build a single self-contained HTML overview of all captured ideas and every paper's pipeline progress (per-section completion, conference name, deadline, days-left). Click any column header to re-sort; papers default to soonest-deadline-first. Triggered by /dashboard.
---

# /dashboard

Invoke the `dashboard` skill to build `outputs/dashboard.html`.

## Usage

- `/dashboard` — build `outputs/dashboard.html` once and print a text summary.
- `/dashboard --out <path>` — write the static HTML somewhere else.
- `/dashboard serve [--port 8765] [--refresh 30]` — run a localhost server that
  regenerates the page live on every request (so it always reflects current
  disk state) and auto-refreshes the browser every `--refresh` seconds. Bound to
  `127.0.0.1` only; Ctrl-C to stop. The active column sort survives reloads.

## What it shows

Three panels, all read straight from on-disk truth (no AgentDB dependency):

| Panel | Source | Columns |
|---|---|---|
| **Papers** | every `(venue, direction)` under `outputs/papers/` | venue · paper (expandable sections) · progress · deadline · due-in · updated · gaps · next |
| **Experiments** | every `outputs/experiments/<slug>/` | experiment (expandable title+repo) · status · progress · versions · bound papers · updated · next |
| **Ideas** | `outputs/idea-checks/<slug>/idea.md` (via `ideas.registry.list_ideas`) | idea · status · updated · venue · verdict · statement (filterable + collapsible) |

- **Paper progress** is page-share weighted — `Σ(planned_pages × fill) ÷
  Σ(planned_pages)` from `outline.md`'s `## Page budget` table; falls back to
  the 7-stage pipeline % when a direction has no budget. The **paper** cell is
  expandable (`▸`): per planned section it shows planned pp · words · % filled ·
  unresolved placeholders (`[REF_NEEDED]`/`[DATA_NEEDED]`/`[FIGURE_NEEDED]`/
  `[CLAIM_UNVERIFIED]`; `%`-comment occurrences ignored), and `not started` for
  undrafted ones. **Experiment progress** is the 5-stage board (`init → analyze`).
- **deadline** is a numeric ISO date parsed best-effort from each venue's
  `_venue.md` `Full paper` row (original fuzzy window kept as a hover tooltip);
  `TBD` when unknown. It's a *coarse* sort key — lock real dates against the CFP.
- **Due-in** is `deadline − today` (overdue red, ≤30 days amber). **Behind**
  papers (near/past deadline + low progress) get a `⚠` and a red row tint, with
  a `Behind N` count in the header. **Updated** is the newest write-surface
  mtime ("Nd ago"); items untouched ≥21 days and unfinished are flagged stale.
- **next** shows the recommended next slash-command per row.
- Self-contained HTML with inline CSS/JS — click any column header to re-sort
  (sort survives auto-refresh); papers default to soonest-deadline-first; the
  Ideas panel has a live search box.

## Action

1. Load the `dashboard` skill (`.claude/skills/dashboard/SKILL.md`).
2. Build mode — run `python -m research_assistant.dashboard` (pass `--out`
   through from `$ARGUMENTS` if present). Never re-implement walk/render in the
   prompt. Print the written path + the text summary; tell the user to open the
   HTML file in a browser.
3. Serve mode (`$ARGUMENTS` starts with `serve`) — run
   `python -m research_assistant.dashboard serve [--port …] [--refresh …]` in
   the background, then tell the user the `http://127.0.0.1:<port>/` URL and how
   to stop it. Don't block the session waiting on the server.
