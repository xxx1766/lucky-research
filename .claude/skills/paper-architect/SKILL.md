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

## Storage model — where paper files actually live

By default, `outputs/papers/<v>/<d>/` is a real local directory and is gitignored
(so a paper exists only on the machine that authored it). Once the user runs
`/paper bind <experiment-slug>` (see Stage 0 below), that directory becomes a
**symlink** into the bound experiment's git repo at
`outputs/experiments/<slug>/repo/paper/<v>/<d>/`. The experiment's repo is the
durable source of truth — clone it on a new machine and the paper comes along.

All writing commands (`/paper write`, `/paper render`, `/figure new`,
`/pseudocode new`) keep writing to `outputs/papers/<v>/<d>/`. The symlink is
transparent — Python's `open()`, `Path.mkdir()`, etc. follow it. **No stage in
this skill needs to be aware of binding state.** The exception is `/paper sync`
(Stage 0.5), which operates on the experiment repo's git remote.

Venue-level files (`outputs/papers/<venue>/_venue.md` and
`outputs/papers/<venue>/_template/`) are NOT symlinks — they are real local
copies kept in sync with the experiment repo by `/paper bind` (Q2c / C-2 in the
design). Two experiments that target the same venue each carry their own copy
in their own repo, with `/paper bind` copying the first-bound experiment's
version into `outputs/papers/<venue>/`.

## Stage 0 — `/paper bind <experiment-slug>`

Move the local `outputs/papers/<v>/<d>/` directory into the named experiment's
repo at `<exp-repo>/paper/<v>/<d>/`, replace the local path with a symlink,
copy venue files, write `.gitignore`, record the binding. Driven by
`research_assistant.papers.bind(venue=..., direction=..., experiment_slug=...,
force=...)`.

**Preconditions**
- The current `(venue, direction)` cursor is set in AgentDB
  `project/paper-context.current`.
- The named experiment exists with a local clone at
  `outputs/experiments/<slug>/repo/`. If not, error out with a hint to run
  `/experiment init` first.

**Workflow**
1. Read the cursor; resolve `(venue, direction)`. Reject if absent.
2. Call `research_assistant.papers.bind(venue=v, direction=d,
   experiment_slug=<slug>, force=<flag>)`. Surface exceptions cleanly:
   - `BindError` ("experiment not cloned") → tell user to run /experiment init.
   - `ConflictError` (`<exp-repo>/paper/<v>/<d>/` already populated) → suggest
     `--force` after the user verifies they want to overwrite.
   - `AlreadyBoundError` (already linked to a different experiment) → suggest
     `/paper unbind` first or `--force`.
3. Print the resulting `BindingResult`:
   - the new symlink path,
   - the real paper dir inside the experiment repo,
   - venue files copied (`_venue.md`, `_template/`),
   - bytes migrated.
4. Update `expert.md` frontmatter (the helper already wrote `experiment:
   <slug>`; if the user has additional experiments to reference, prompt for
   them and write `experiments: [<list>]`).
5. Record `project/paper-bindings.<v>__<d>` = `{experiment_slug: <slug>,
   bound_at: <iso-timestamp>}` in AgentDB via
   `mcp__claude-flow__memory_store` (fast cache; the durable record is in
   `expert.md`).
6. Trigger an initial sync — `/paper sync` (Stage 0.5) so the migration lands
   in the remote.

`/paper unbind [--keep-files]` is the inverse — calls
`research_assistant.papers.unbind(venue=v, direction=d, keep_files=<flag>)`.
Removes the symlink; with `--keep-files`, copies the experiment repo's content
back to a regular local directory at the symlink path.

## Stage 0.5 — `/paper sync [-m "<msg>"]`

Stage `paper/<v>/<d>/` paths inside the experiment repo, fetch (no auto-merge),
commit, and push. Driven by
`research_assistant.papers.sync(venue=v, direction=d, message=<opt>)`.

**Workflow**
1. Resolve the bound experiment via `papers.is_bound(v, d)`; reject with
   `NotBoundError` if absent.
2. Call `papers.sync(...)`. Surface:
   - `DivergedError` → print "remote is ahead by N commits. Run
     `git pull --rebase` inside `<exp-repo>` then re-run /paper sync."
   - `SyncResult.committed=False` with "no changes" → tell user nothing to do.
   - Successful commit → print the commit SHA + the auto-generated message
     (`paper(<v>/<d>): <verb> <files>`). `verb ∈ {write, revise, render, prune}`.
3. If `pushed=False` (e.g. no remote configured), print a one-line warning but
   leave the commit in place — `git push` can be retried manually.

**Scope**
- Stages only paths under `paper/<v>/<d>/`. Dirty non-paper code elsewhere in
  the experiment repo is left alone (Q3d in the design).
- `-m "<msg>"` overrides the auto-generated message.

## Cross-machine restore

On a fresh checkout of lucky-research, `outputs/` is empty (gitignored). To get
paper artifacts back:

```bash
git clone git@github.com:xxx1766/lucky-research.git
cd lucky-research && pip install -e ".[dev]"

# Restore each experiment that owns one or more papers:
/experiment init --from-url git@github.com:xxx1766/weightlet-exp.git
/experiment init --from-url git@github.com:xxx1766/sparse-attn-exp.git

# Then re-create the paper symlinks in one shot:
/paper restore --all
```

`/paper restore [--all] [<venue>/<direction>]` is driven by
`research_assistant.papers.restore(venue=..., direction=..., all_papers=...)`.
It walks `outputs/experiments/*/repo/paper/*/*/`, and for each
`(experiment, venue, direction)` triple it creates a symlink at
`outputs/papers/<v>/<d>/` and copies venue-level files. It refuses to clobber
real local directories — if a `outputs/papers/<v>/<d>/` already exists as a
real (non-symlink) dir, the restore for that paper is skipped.

`/paper status` soft-restores missing symlinks automatically — useful when the
user runs status on a freshly cloned machine before remembering to run
`/paper restore`.

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

### Sub-stage 1b — `/paper venue refs` (reference-paper writing conventions)

The `_venue.md` written above captures *administrative* facts (deadlines, page
limit, review rubric). To teach `/paper write` how this venue's prose actually
*reads*, the user can drop 2–5 reference papers from the target venue and we
distill their writing conventions into a sentinel-fenced `## Writing
conventions` block of `_venue.md`.

This is purely additive — refs are optional, the venue stage stays "done"
without them.

**When to use**
- The user has a venue cursor set (i.e. Stage 1 already ran).
- They have 2–5 PDFs from the target venue (under `inputs/papers/`) or arXiv
  IDs/URLs handy.

**Subcommands**
- `/paper venue refs add <pdf-or-arxiv>...` — ingest one or more references, then
  auto-distill.
- `/paper venue refs list` — table of currently-ingested refs.
- `/paper venue refs distill` — re-aggregate the `## Writing conventions` block
  without re-ingesting.

**Workflow for `refs add`**
1. Resolve venue from `mcp__claude-flow__memory_retrieve(namespace="project/paper-context", key="current")`.
   If unset, error clearly: "run `/paper venue <slug>` first".
2. For each source, call `research_assistant.papers.ingest_venue_ref(venue, source, extract_pdf_text=lit.extract_pdf_text, fetch_arxiv=lit.fetch_arxiv, parse_metadata=lit.parse_metadata, analyze=<see prompt below>)`. The helper:
   - Resolves arXiv id/URL → PDF download into `inputs/papers/` via `lit.fetch_arxiv`.
   - For local paths under `inputs/papers/`, uses them directly.
   - Parses metadata, builds a slug, and **skips if `_venue-refs/<slug>.md` already exists** (idempotent — delete the file to force re-analysis).
3. The `analyze(text, meta)` callable is **you** — read the paper text and produce a `VenueRefAnalysis` JSON object following the **per-paper analysis prompt** below.
4. After every source is ingested, store each analysis in AgentDB:
   `mcp__claude-flow__memory_store(namespace="papers/venue-style", key=f"{venue}/{slug}", value=<analysis JSON>, metadata={"year": ..., "venue": venue})`.
5. Auto-call `distill_venue_conventions(venue, aggregate=<see prompt below>)`.
6. Print the progress footer — it now shows `· N refs · conventions distilled`.

**Per-paper analysis prompt** (run once per reference paper; emit a JSON object matching `VenueRefAnalysis`)
1. Identify the **section structure & order** (top-level headings as a list). Flag any non-standard sections (e.g. "Threat Model" in security, "Artifact" in systems).
2. For each of `{abstract, introduction, method, results, limitations}`: describe the **opening sentence pattern**, **tense** (past/present/mixed), **voice** (active/passive/mixed), and quote **one canonical sentence verbatim** from the paper.
3. Characterize **citation style**: parenthetical vs textual, density per paragraph (rough average), and integration pattern (e.g. "Prior work [N] establishes...").
4. Catalogue **figure/equation reference style** (`Fig. N`, `Figure N`, `\Cref{fig:...}`, `(N)` for equations) and **hedging vocabulary** used around result claims ("we observe", "suggests", "achieves", "matches").
5. Surface **3 notable transition phrases / sentence templates** worth imitating, plus any **anti-patterns** the paper visibly avoids relative to a generic workshop submission.
6. **Figure style** — call `Read(meta["pdf_abs_path"], pages="1-8")` to see the first 8 pages as rendered images. Describe: typical figure kinds (line plot / bar chart / scatter / architecture diagram), column span (single / double / mixed), subfigure usage (a/b/c pattern), caption pattern (short-title / title+interpretation / narrative), caption tense, palette family (monochrome / few-colors / categorical / sequential), placement (top-of-page / inline / deferred-to-end). Quote one full caption verbatim into `figure_style.canonical_caption`.
7. **Table style** — from the same `Read` (extend `pages` if no tables appear in the first 8), describe rule style (booktabs / grid / mixed), highlight convention for the best result (bold / underline / shaded-cell / none), units placement (column-header / row-header / inline), significance markers (stars / daggers / none), and the typical comparison-table column layout. Quote one full table caption verbatim into `table_style.canonical_caption`.

Note that step 3 above (running `analyze`) now expects to inspect the PDF visually via the `Read` tool on `meta["pdf_abs_path"]` for the figure/table portion — full text alone is insufficient for visual conventions.

**Aggregation prompt** (run once after all adds; produces the markdown body of the `## Writing conventions` block)
- Given N `VenueRefAnalysis` blobs, produce markdown with these sub-headings: Section structure, Abstract style, Intro openings, Method narration, Result claims, Citations & in-text figure refs, Figures, Tables, Limitations, Voice, Quotable templates, Do/Don't.
- For each finding, cite counts when meaningful (e.g. "4/5 papers open intros with a motivating example"). Quote canonical sentences verbatim where they exist.
- Keep the aggregated block under ~400 lines of markdown — `/paper write` will read it on every draft, so dense > exhaustive.

**Idempotency contract**
- `refs add` skips by slug — deleting a `_venue-refs/<slug>.md` file is the only way to force re-analysis of that paper.
- `refs distill` only rewrites the sentinel-fenced block (`<!-- venue-refs:begin -->` … `<!-- venue-refs:end -->`) of `_venue.md`. Anything else in `_venue.md` survives byte-for-byte — manual edits outside the sentinels are safe.

**Memory keys touched**
- write: `papers/venue-style/<venue>/<paper-slug>`
- read (on distill): `papers/venue-style/<venue>/*`

**File outputs**
- `outputs/papers/<venue>/_venue-refs/<paper-slug>.md` — YAML frontmatter (round-trip source) + human-readable body. The frontmatter is authoritative for `distill`.
- `outputs/papers/<venue>/_venue.md` — gains a `## Writing conventions` section, sentinel-fenced.

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

**Writing habits (read before drafting any section)**

Always load `references/section-heuristics.md`. It carries the per-section
do/don't/beat lists adapted from
[xxx1766's "how to write a paper"](https://xxx1766.github.io/2026/03/19/how-to-write-paper/),
plus the cross-cutting principles below. Treat it as a *required* prelude — it
overrides default drafting habits (IMRAD order, "we propose…" openers, etc.).

Cross-cutting principles enforced in this stage:

- **Drafting order is not IMRAD.** The blog's order — and therefore this skill's
  default — is **figures → method → results → related-work → intro → abstract → title**.
  Method first because it locks the vocabulary every other section reuses; intro
  late because its funnel depends on the headline number from results; title last
  because the abstract narrows what the title can promise.
- **Title is provisional at outline time, final after abstract stabilises.** Stage 6
  ends with a `title-revisit` step that re-reads `\title{}` against the now-stable
  abstract.
- **Funnel-gate the introduction.** Before drafting `intro`, print a plain-text
  prompt: `"Funnel check: have you discussed broad → existing → best → limitations
  → this paper's goal with your advisor? (yes / draft anyway / abort)"`. On
  `abort`, stop without writing. (Plain text, not `AskUserQuestion` — research
  picks belong in the chat.)
- **Banned phrases in intro.** After writing `sections/intro.tex`, grep
  case-insensitively for `novel`, `first ever`, `first time`, `paradigm-changing`,
  `paradigm-shifting`, `we propose`. Any hit prints a warning with line numbers —
  do not auto-rewrite, the user decides.

**Workflow**

- If no section given (first write call):
  1. Generate `outline.md` — section-by-section plan grounded in `expert.md` +
     `focused-problem.md` + `experiments/`. Markdown, not LaTeX.
  2. Scaffold the LaTeX skeleton if missing:
     - `<direction>/main.tex` — `\documentclass` pointing at `../_template/`,
       `\input`s each `sections/<name>.tex`, sets `\bibliography{refs}`.
     - `<direction>/sections/` — empty directory.
     - `<direction>/refs.bib` — empty file.
     - Call `research_assistant.pseudocode.preamble.ensure_preamble(<direction>/main.tex, venue_md_path=<venue>/_venue.md)` so the algorithm package (`algorithm + algpseudocode` by default, or `algorithm2e` if the venue opts in) is in the preamble from day one. Idempotent — safe to call on every write.
  3. **Surface unmade figures.** Read `outline.md`'s figure table; for every row
     whose source figure isn't in `figures/` (or, for experiment-scope figures,
     `repo/figures/<vN.M>/`), print `→ /figure new <slug>` so figures land before
     Method drafting (figures lock the vocabulary the prose then quotes).
  4. **Print the recommended next-call sequence** in the blog's order, mapped onto
     the outline's actual section names. Use the synonym map in
     `references/section-heuristics.md` (`design`/`approach` → `method` kind,
     `evaluation`/`eval` → `results` kind, …). Example output:
     ```
     Recommended drafting order:
       1. /paper write design        # method kind
       2. /paper write evaluation    # results kind
       3. /paper write related-work
       4. /paper write discussion
       5. /paper write intro         # funnel-gated
       6. /paper write abstract
       7. /paper write title         # revisit \title{}
     ```
     One section per invocation — the skill does not auto-loop.
- If section given (`intro` / `method` / `results` / `discussion` / ...):
  1. **Resolve the section's kind** via the synonym map in
     `references/section-heuristics.md` and read the matching
     `## section: <kind>` block. If no match, use `## section: default`.
  2. **Read the cross-cutting block** plus `expert.md`, `focused-problem.md`,
     `experiments/*`, `related-papers/`, `outline.md`'s block for this section,
     and any existing `sections/*.tex` for tone + terminology consistency.
  3. **Intro gate.** If kind is `intro`, run the funnel check above; on `abort`,
     stop.
  4. **Title revisit.** If kind is `title`, do not draft a new section file —
     instead: read the current `\title{}` from `main.tex` and the abstract from
     `sections/abstract.tex`; propose 3 revised titles (8–12 English words,
     concise + specific, no banned padding); let the user pick (plain text) or
     reply with their own; rewrite `\title{...}` in `main.tex`. Skip the `% TODO`
     block and the figure/algorithm includes (none apply to titles).
  5. **Draft `<direction>/sections/<section>.tex`.** Prepend the heuristics block's
     Do / Don't / Beats lists at the top of your reasoning before writing — every
     paragraph should be traceable to a beat. **Cite directly as `\cite{<slug>}`**
     (no `[@cite:]` placeholder). `<slug>` should match `papers/<slug>` in AgentDB
     so `/cite` can resolve it into `refs.bib`.
  6. **Banned-phrase scan.** If kind is `intro`, after writing the file run
     `grep -niE 'novel|first ever|first time|paradigm-(changing|shifting)|we propose' sections/intro.tex`
     and print each hit; suggest a rewrite but leave the file as-is.
  7. Append a `% TODO:` LaTeX comment block listing experiments still needed.
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

### Algorithm inclusion

When the section being drafted needs an algorithm (method / approach sections
almost always do):

1. List `algorithms/*.tex` in the current direction.
2. If a slug matches a section keyword (read the corresponding `<slug>.note.md`
   `intent:` field for the match), pick it; otherwise list the available slugs
   and ask the user. Each algorithm `.tex` is self-contained — it already
   carries `\begin{algorithm} ... \end{algorithm}`, so the section just
   `\input{}`s it (no extra wrapping).
3. Emit the include block exactly in this form:

```latex
\input{algorithms/<slug>.tex}
```

   Or, if the section refers to the algorithm in prose without immediately
   placing it, use `See Algorithm~\ref{alg:<slug>}.` and `\input{...}` the
   algorithm at the natural reading position.

4. If no matching `algorithms/<slug>.tex` exists, suggest the user runs
   `/pseudocode new <slug>` first — do not synthesise a placeholder algorithm
   box. Pseudocode is method-level documentation; it must be authored
   deliberately, not auto-generated from incomplete context.

5. The required `\usepackage` lines are kept in `main.tex` by
   `pseudocode.preamble.ensure_preamble(...)` (called during scaffold and on
   first `/pseudocode new`). No action needed here.

For **experiment-scope** algorithms (referenced from a paper section discussing
that experiment), the include path is `algorithms/<vN.M>/<slug>.tex`. Surface
this only when the algorithm is intrinsically tied to one experiment version
(e.g. an ablated sampler); otherwise prefer the paper-scope variant.

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
