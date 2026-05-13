---
name: paper-architect
description: Multi-stage paper output flow — venue setup, direction discussion, paper scouting, problem focusing, motivation experiment design, section drafting. Organizes everything under outputs/papers/<venue>/<direction>/. Use when the user is starting or working on a paper for a specific venue. Triggered by /paper.
---

# paper-architect

> **STATUS**: stub. Workflow contracts only — real bodies land stage-by-stage.

## Mental model

A paper lives at `outputs/papers/<venue>/<direction>/`. The flow has eight stages, each
backed by one subcommand of `/paper`. Stages can be revisited in any order, but later
stages assume earlier ones are non-empty.

```
venue → direction → scout → focus → motivate → write ↔ experiments
                                                 │
                                                 ├─ status snapshot any time
                                                 └─ render any time (auto after write)
```

The "current paper" is just a `(venue, direction)` tuple stored in AgentDB
`project/paper-context`. Every stage reads it; the `venue` and `direction` subcommands
write it.

## Progress display

Every `/paper` subcommand ends by printing a **one-line progress footer** so the user
always knows which stage they're at and what's next. `/paper status` prints the full
multi-line **board** and persists it to `<direction>/status.md`.

Both visualizations are produced by pure helpers in
`research_assistant.papers` — they take `(venue, direction, StageStatus)` and return
a Markdown string. The skill body just prints what they return.

```
# footer (after any /paper subcommand)
── NeurIPS-2026 / diffusion-finetune   [######-] 6/7   next: /paper render ──

# board (from /paper status)
NeurIPS-2026 / diffusion-finetune
[######-] 6/7 stages

  [x] 1. venue       venue dir present
  [x] 2. direction   expert.md ok
  [x] 3. scout       related-papers/ present
  [x] 4. focus       focused-problem.md
  [x] 5. motivate    motivation.md · benchmark.md
  [.] 6. write       outline.md · 2 sections · main.tex
  [ ] 7. render      main.pdf missing
         cite        refs.bib: 0 entries  ← /cite to populate

Suggested next: /paper render
```

The 7-stage bar counts pipeline checkpoints
(`venue, direction, scout, focus, motivate, write, render`); `cite` is shown as a
sidebar check because `/cite` is a separate command. Use `[x]` done / `[.]` partial /
`[ ]` empty.

Helpers (all in `research_assistant.papers`):

- `stage_status(direction_dir) -> StageStatus` — inspect a direction folder.
- `render_progress_footer(venue, direction, status) -> str` — one-line footer.
  Tolerates `None` for direction/status (use during Stage 1 or before any venue).
- `render_progress_board(venue, direction, status) -> str` — full Markdown board.
- `next_suggested(status) -> str` — the next-step command shown in both renders.

## Directory layout this skill owns

```
outputs/papers/<venue>/
  _venue.md                  论文特点和要求
  _template/                 user-supplied conference .sty / .cls / .bst
  <direction>/
    expert.md                小方向专家角色 (YAML frontmatter + body)
    related-papers/<slug>.md 对比论文
    focused-problem.md       聚焦问题
    experiments/             对比实验和benchmark
      motivation.md
      benchmark.md
      results/
    outline.md               写作思路和架构 (Markdown, planning)
    refs.bib                 per-direction BibTeX
    main.tex                 top-level driver — \include's sections/*
    sections/                paper prose (intro.tex, method.tex, ...)
    main.pdf                 auto-rendered preview / submission PDF
    status.md                auto-updated stage tracker
```

## Stage 1 — `/paper venue <slug>`

**Inputs**
- `<slug>` from user (e.g. `NeurIPS-2026`).
- Optional: a CFP URL or pasted call-for-papers text.

**Workflow**
1. Validate slug shape via `research_assistant.papers.slugify_venue`.
2. Create `outputs/papers/<venue>/` if missing.
3. AI drafts `_venue.md` from the CFP. Sections: page limit, deadlines, review criteria,
   accepted paper styles, recent trends, scoring rubric.
4. Show user the draft; accept inline edits.
5. Write `outputs/papers/<venue>/_venue.md`.
6. `mcp__claude-flow__memory_store(namespace="project/paper-context", key="current",
   value={venue: <slug>, direction: null})`.
7. Tell the user the expected template location:
   `outputs/papers/<venue>/_template/`. The user drops the conference `.sty`, `.cls`,
   and (optional) `.bst` files there — the skill does **not** auto-fetch them.
   If `_template/` is missing or empty when `/paper write` or `/paper render` runs,
   the render step prints a clear "drop the template files here" message and skips
   the build (the `.tex` write itself still succeeds).
8. Print `render_progress_footer(<slug>, None, None)` — venue set, direction pending.

## Stage 2 — `/paper direction <slug>`

**Inputs**
- `<slug>` (e.g. `diffusion-finetune`).
- Current venue context.

**Workflow**
1. Invoke the `past-work-historian` agent (via the Agent tool) to surface relevant
   prior work from `project/past-work/`.
2. Discuss direction with the user — what's the angle, why this venue, what would
   make it land. Multi-turn conversation, not single-shot.
3. Ask about the experiment code repo (plain text, no AskUserQuestion — per the
   `feedback_decision_ui` memory). Three branches:
   - existing repo → record `code_repo: "github:<owner>/<repo>"` in `expert.md`
     frontmatter.
   - want a new one → suggest `xxx1766/<direction-slug>-exp` and let the user create
     it on GitHub. This skill does **not** run `gh repo create`.
   - skip → leave the field absent. Re-running `/paper direction <slug>` later is
     idempotent and will ask again if the field is still empty; the user can also
     edit `expert.md` directly at any time.
4. Draft `expert.md` — YAML frontmatter on top (see schema below) + body sections
   (voice, taste, anti-patterns, prior takes). Mirror `docs/direction-template.md`.
   Show + edit.
5. Create `outputs/papers/<venue>/<direction>/{expert.md, status.md}`.
6. Update `project/paper-context.current` to `{venue, direction, code_repo}` so
   downstream stages can read the repo pointer without parsing markdown.
7. Print `render_progress_footer(venue, direction, stage_status(direction_dir))`.

**`expert.md` frontmatter schema**

```yaml
---
venue: NeurIPS-2026
direction: diffusion-finetune
code_repo: "github:xxx1766/diffusion-finetune-exp"   # optional
created: 2026-05-12
---
```

## Stage 3 — `/paper scout`

**Inputs**
- Current `(venue, direction)`.
- Direction keywords (extracted from `expert.md` or asked).

**Workflow**
1. Call `research_assistant.lit.sourcing.search_for_direction(venue, keywords)`.
2. For each `PaperRef`, fetch PDF if available, then reuse `lit-summarize`'s workflow
   but write into `<direction>/related-papers/<slug>.md` instead of `outputs/summaries/`.
3. Index each summary in AgentDB namespace `papers/` (lit-summarize already does this).
4. Print a short table of all scouted papers.
5. Print `render_progress_footer(venue, direction, stage_status(direction_dir))`.

## Stage 4 — `/paper focus`

**Workflow**
1. Read `<direction>/related-papers/*.md` + `expert.md`.
2. Interactive narrowing — ask the user three questions:
   - what's the specific gap?
   - why does it matter now?
   - what's the smallest empirical claim that would close it?
3. Write `<direction>/focused-problem.md`. Sections: Problem, Gap claim, Why now,
   Smallest empirical claim, Out-of-scope.
4. Print `render_progress_footer(venue, direction, stage_status(direction_dir))`.

## Stage 5 — `/paper motivate`

**Workflow**
1. Read `focused-problem.md` + `related-papers/`.
2. Design two artifacts:
   - `experiments/motivation.md` — the small experiment a reviewer would expect to
     see to believe the problem is real.
   - `experiments/benchmark.md` — main comparison + ablations the paper will run.
3. List datasets, metrics, baselines, expected outcome ranges.
4. Print `render_progress_footer(venue, direction, stage_status(direction_dir))`.

## Stage 6 — `/paper write [section]`

This stage is **LaTeX-native**: paper prose goes into `.tex` files that build to a
real PDF via the conference template. Markdown planning artifacts (`outline.md`,
`focused-problem.md`, `experiments/*.md`) stay Markdown.

**Workflow**

- If no section given (first write call):
  1. Generate `outline.md` — section-by-section plan grounded in `expert.md` +
     `focused-problem.md` + `experiments/`. Markdown, not LaTeX.
  2. Scaffold the LaTeX skeleton if missing:
     - `<direction>/main.tex` — `\documentclass` pointing at `../_template/`,
       `\input`s each `sections/<name>.tex`, sets `\bibliography{refs}`.
     - `<direction>/sections/` — empty directory.
     - `<direction>/refs.bib` — empty file.
- If section given (`intro` / `method` / `results` / `discussion` / ...):
  1. Read `expert.md`, `focused-problem.md`, `experiments/*`, `related-papers/`, and
     any existing `sections/*.tex` for tone + terminology consistency.
  2. Draft `<direction>/sections/<section>.tex`. **Cite directly as `\cite{<slug>}`**
     (no `[@cite:]` placeholder). `<slug>` should match `papers/<slug>` in AgentDB so
     `/cite` can resolve it into `refs.bib`.
  3. Append a `% TODO:` LaTeX comment block listing experiments still needed.
- **Auto-render** after every successful section write:
  1. Verify `outputs/papers/<venue>/_template/` exists and is non-empty. If missing,
     print the expected drop location and **skip** the render — the `.tex` write
     itself still succeeded.
  2. Shell out to `tectonic` (preferred) or fall back to `latexmk -pdf`. Run from the
     direction directory so `../_template/` resolves.
  3. On success: tell the user the path to `main.pdf`.
  4. On build failure: print the last ~40 lines of the log; do **not** undo the
     write. User fixes the `.tex` and runs `/paper render` to retry.
  5. If neither toolchain is on PATH: print install hints
     (`brew install tectonic` / `cargo install tectonic` /
     `apt install texlive-latex-extra`) and skip the render.
- After everything above (whether the render fired or not), print
  `render_progress_footer(venue, direction, stage_status(direction_dir))`.

### Figure inclusion

When the section being drafted needs a figure:

1. List `figures/*.pdf` in the current direction.
2. If a slug matches the section's keyword (read the corresponding `<slug>.note.md`
   `intent:` field for the match), pick it; otherwise list the available slugs and
   ask the user.
3. Emit the include block exactly in this form (no `\graphicspath`, explicit
   path with `.pdf` extension):

```latex
\begin{figure}[t]
  \centering
  \includegraphics[width=<W>]{figures/<slug>.pdf}
  \caption{<from the figure's note.md `intent:` — user-editable>}
  \label{fig:<slug>}
\end{figure}
```

`<W>` is chosen from the figure's `size.preset`:

* `single-column` → `\columnwidth`
* `double-column-half` → `0.48\textwidth`
* `double-column-full` → `\textwidth`
* `custom` → `\columnwidth`

If no matching `figures/<slug>.pdf` exists, suggest the user runs `/figure new <slug>` first — do not synthesise a placeholder include.

For **experiment-scope** figures (referenced from a paper section discussing
that experiment), the include path uses `repo/figures/<vN.M>/<slug>.pdf` —
read the experiment's `versions/<vN.M>.md` `figures:` list (populated by
`/figure new --scope experiment`) to enumerate.

## Stage 7 — `/paper status [<venue>/<direction>] [--all]`

**Workflow**

- **Default (current direction)**:
  1. Read `project/paper-context.current` to resolve `(venue, direction)`.
     If unset: print the no-venue / no-direction footer and stop.
  2. Compute `status = stage_status(direction_path(venue, direction))`.
  3. Print `render_progress_board(venue, direction, status)`.
  4. Persist the same string (plus a trailing newline) to
     `<direction>/status.md` — overwrite, this is a snapshot.
  5. Print `render_progress_footer(venue, direction, status)`.
- **Explicit target — `/paper status <venue>/<direction>`** (recovery path for
  in-flight projects whose AgentDB cursor is stale or unset):
  1. Parse the positional arg, split on `/` into `venue` and `direction`. Reject
     if either half is empty.
  2. Verify `direction_path(venue, direction)` exists on disk; if not, error out
     ("no such direction under outputs/papers/...") without writing anything.
  3. Compute `status = stage_status(direction_path(venue, direction))`.
  4. Print `render_progress_board(...)` and persist `<direction>/status.md`
     (same as default).
  5. **Adopt the target as the new cursor**:
     `mcp__claude-flow__memory_store(namespace="project/paper-context",
     key="current", value={venue, direction})`. Subsequent stages pick up here.
  6. Print `render_progress_footer(...)`.
- **`--all`**:
  1. Walk `outputs/papers/*/` for venues.
  2. For each venue, walk subdirectories that are not `_template/`; treat each as
     a direction.
  3. For each `(venue, direction)`, compute `stage_status`, print
     `render_progress_board(...)` separated by `---` lines, and persist the same
     string to `<direction>/status.md` (overwrite — one-shot refresh of every
     direction's snapshot).
  4. End with one `render_progress_footer(...)` for the current direction
     (whatever `project/paper-context.current` points at).

## Stage 8 — `/paper render`

Explicit re-render of `main.pdf` for the current direction. Same toolchain as the
auto-render baked into Stage 6 — use this after manual `.tex` edits or to retry
after a build failure.

**Workflow**
1. Resolve the current `(venue, direction)` from `project/paper-context`.
2. Verify `outputs/papers/<venue>/_template/` exists and is non-empty; if not,
   point the user at the expected drop location and abort.
3. Call `research_assistant.refs.render_latex(direction_dir)`. Tectonic preferred,
   `latexmk -pdf` fallback, both run from the direction directory.
4. On success: print the absolute path to `main.pdf`. On failure: surface the tail
   of the log so the user can fix the source.
5. Print `render_progress_footer(venue, direction, stage_status(direction_dir))`.

## Outputs

Every artifact named above lives under `outputs/papers/<venue>/<direction>/`. AgentDB
side: `project/paper-context` (cursor), `papers/<slug>` (scouted papers — written by
lit-summarize), `drafts/<venue>/<direction>` (lightweight snapshot of the outline so the
mentor can detect drift).

## Memory keys touched

- `project/paper-context` — read/write (cursor: `{venue, direction, code_repo}`).
- `project/past-work/*` — read (via `past-work-historian`).
- `papers/<slug>` — write (during scout).
- `drafts/<venue>/<direction>` — write (during write).

## Open TODOs

- [ ] Real `search_openreview` + `search_arxiv` implementations.
- [ ] Section-template variants per venue family (NLP / CV / systems).
- [ ] Coupling between `experiments/results/` and external trackers (deferred).
- [ ] Real `render_latex` body in `research_assistant.refs` — shell out to tectonic.
- [ ] Real `scan_tex_cite_keys` body — extract `\cite{...}` keys for `/cite`.
- [ ] `/mentor add-past-work` UX.
