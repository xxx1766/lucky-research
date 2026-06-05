---
name: dashboard
description: Build a single self-contained HTML dashboard of all captured ideas and every paper's pipeline progress — per-section completion, conference name, deadline, and days-left, with click-to-sort columns. Use when the user says "show my dashboard", "overview of my ideas and papers", "which paper is due first", or triggers /dashboard.
---

# dashboard

> **STATUS**: real implementation. Backed by `research_assistant.dashboard`.

## Mental model

The plugin already tracks two kinds of state on disk. The dashboard is a
**read-only aggregator** that joins them into one HTML page — it invents no new
state and writes nothing except the single output file.

```
outputs/idea-checks/<slug>/idea.md     ─┐
                                         ├─▶ python -m research_assistant.dashboard
outputs/papers/<venue>/<direction>/     ─┘        │
  + <venue>/_venue.md (conference + deadline)     ▼
                                          outputs/dashboard.html  (open in browser)
```

- **Ideas** come from `ideas.registry.list_ideas()` — every captured idea's
  slug / status / updated / venue / verdict / statement.
- **Papers** come from walking `outputs/papers/`. For each `(venue, direction)`
  the 7-stage board (`papers.stage_status` → `papers.stages_completed`) gives a
  percent; `papers.placeholders.scan_placeholders` + `papers.tex_files` give the
  per-section word count and unresolved-placeholder count. A venue with no
  direction still appears as a single direction-less row (so its deadline shows).
- **Conference name + deadline** are parsed best-effort from `_venue.md`
  (`dashboard.venue_meta`). Venue briefs are `TBD`-heavy scaffolds, so the
  deadline is a *coarse* sort key, not an authoritative date. Bound directions
  are symlinks into experiment repos — `is_dir()` follows them, so they show up.

## Flow

Non-interactive. Two modes, picked from `$ARGUMENTS`.

### Build (default) — render once

1. `--out <path>` is the only flag (default `outputs/dashboard.html`).
2. Run the helper — **do not** re-implement the walk or the HTML in the prompt:

   ```bash
   python -m research_assistant.dashboard            # or: --out <path>
   ```

3. The CLI prints the written path, the idea/paper counts, and a one-line
   text summary per paper (`venue/direction  NN%  due <window>  · N gaps`).
   Relay that verbatim, then tell the user to open the HTML file in a browser
   and that every column header is click-to-sort (papers default to
   soonest-deadline-first).

### Serve — live localhost server

When `$ARGUMENTS` starts with `serve`:

```bash
python -m research_assistant.dashboard serve [--port 8765] [--refresh 30]
```

- The server regenerates the page from disk on **every** request, so it always
  reflects the current state — no rebuild step needed. The browser re-polls via
  a `<meta refresh>` every `--refresh` seconds (default 30). The active column
  sort is restored after each reload (sessionStorage), so auto-refresh doesn't
  reset the user's view.
- Bound to `127.0.0.1` only — never `0.0.0.0`. It's a personal dev surface.
- Launch it with `run_in_background: true` so the session isn't blocked; then
  hand the user the `http://127.0.0.1:<port>/` URL and tell them Ctrl-C (or
  killing the background task) stops it. If the port is taken the CLI exits
  non-zero with a hint to pick another `--port`.

## Notes

- **No AgentDB / network** — pure filesystem read + one file write. Safe to run
  anytime, including offline.
- **Honest metrics.** Progress is pipeline-stage completion, not a guarantee
  the prose is finished; the per-section word count is an approximate proxy
  (LaTeX commands inflate it slightly) and placeholder counts surface
  evidence-first debts still open. Don't oversell the percentages.
- **Deadlines are coarse.** If a `_venue.md` deadline is `TBD`, the row sorts by
  Dec 1 of the year in the venue slug and shows `TBD`. Remind the user to lock
  real dates against the official CFP.
- If `outputs/papers/` or `outputs/idea-checks/` is empty, the matching panel
  renders a friendly "nothing yet — run `/paper venue` / `/idea-check`" note;
  the page still builds.
