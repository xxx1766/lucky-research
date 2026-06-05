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

Two panels, both read straight from on-disk truth (no AgentDB dependency):

| Panel | Source | Columns |
|---|---|---|
| **Ideas** | `outputs/idea-checks/<slug>/idea.md` (via `ideas.registry.list_ideas`) | slug · status · updated · venue · verdict · statement |
| **Papers** | every `(venue, direction)` under `outputs/papers/` | venue · paper (expandable section list) · conference · progress · deadline · due-in · open gaps |

- **Progress** is the 7-stage pipeline (`venue → direction → scout → focus →
  motivate → write → render`), shown as a bar + `N/7` + percent.
- **Paper** cell is expandable (`▸`): per drafted `sections/*.tex` it lists the
  approximate word count and the count of unresolved evidence-first
  placeholders (`[REF_NEEDED]` / `[DATA_NEEDED]` / `[FIGURE_NEEDED]` /
  `[CLAIM_UNVERIFIED]`). Comment-only (`%`) occurrences are not counted.
- **Conference** + **deadline** are parsed best-effort from each venue's
  `_venue.md` (the `Conference` row and the `Full paper` deadline row). The
  deadline is a *coarse* sort key — lock real dates against the official CFP.
- **Due-in** is `deadline − today`; overdue is flagged red, ≤30 days amber.
- The page is a static HTML file with inline CSS/JS — open it in a browser;
  every column header is clickable to re-sort. Papers default to
  soonest-deadline-first.

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
