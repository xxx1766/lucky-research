---
name: paper-architect
description: Multi-stage paper output flow — venue setup, direction discussion, paper scouting, problem focusing, motivation experiment design, section drafting. Organizes everything under outputs/papers/<venue>/<direction>/. Use when the user is starting or working on a paper for a specific venue. Triggered by /paper.
---

# paper-architect

> **STATUS**: active. All stage work shipped. `## Open TODOs` at the bottom of this file is currently empty — add new items there as scope shows up.

## Mental model

A paper lives at `outputs/papers/<venue>/<direction>/`. The flow has eight stages, each
backed by one subcommand of `/paper`. Stages can be revisited in any order, but later
stages assume earlier ones are non-empty.

```
venue → direction → scout → focus → motivate → write ↔ experiments
                                                 │
                                                 ├─ humanize · review · verify (post-write polish + audit)
                                                 ├─ status snapshot any time
                                                 └─ render any time (auto after write)
```

The "current paper" is just a `(venue, direction)` tuple stored in AgentDB
`project/paper-context`. Every stage reads it; the `venue` and `direction` subcommands
write it.

## References (load on demand)

Stable, detail-heavy content lives in `references/` so this SKILL stays scan-
nable. Each entry below names the file and what it contains, and the stages
that pull it in:

| File | Contents | Loaded by |
|---|---|---|
| `references/section-heuristics.md` | Per-section-kind Do/Don't/Beats lists (adapted from xxx1766's "how to write a paper"). Includes the `<synonym map>` for `design`/`approach`→`method`, `evaluation`/`eval`→`results`, …, the `## section: <kind>` blocks, and `## family: <name>` additive overrides for `systems` / `nlp` / `cv`. | Stage 6 (always, before drafting any section) |
| `references/latex-conventions.md` | Project-wide LaTeX style rules: `hard-rules` (no `---`, no `--` outside numeric ranges, no bare `;`, Chinese-comment shape), math notation, tables-and-figures (`Caption format` etc.), word choice, tense, citations, paragraph layout, pre-submission checklist. | Stage 6 (always); Stages 8.5 / 8.6 (lint reference) |
| `references/write-workflow.md` | Stage 6's full step-by-step: **preflight gate** (`write_preflight` — venue/focus/literature blocking + evidence warning), **placeholder tokens** (`[REF_NEEDED]`/`[FIGURE_NEEDED]`/`[DATA_NEEDED]`/`[CLAIM_UNVERIFIED]` evidence-first rules) + **placeholder audit** (`scan_placeholders`), cross-cutting principles, no-section-given path, section-given path (kind resolution, family stacking, intro funnel gate, title revisit, draft, banned-phrase scan, hard-rule lint, `% TODO` block), figure-inclusion + algorithm-inclusion blocks (with the exact `\includegraphics` / `\input{algorithms/...}` shapes and `<W>` size mapping), auto-render fallback chain. | Stage 6 (when drafting begins) |
| `references/humanize-prompt.md` | Verbatim "去 AI 味（LaTeX 英文）" prompt prelude. Three-part response format (`Part 1 [LaTeX]`, `Part 2 [Translation]`, `Part 3 [Modification Log]`); `[检测通过]` sentinel meaning "already natural, skip rewrite". | Stage 8.5 (`/paper humanize`) |
| `references/review-prompt.md` | Verbatim reviewer-perspective audit prompt. Two-part response (`Part 1 [The Review Report]`, `Part 2 [Strategic Advice]`); uses the `{{TARGET_VENUE}}` token (substituted in code, model never sees it). | Stage 8.6 (`/paper review`) |
| `references/verify-workflow.md` | Source-level evidence-closure protocol: the iron three-pass order (Evidence → Argument → Style, no skipping), the 5 debt classes (hard `citation`/`evidence`/`consistency`/`prose` + soft `figure`), Pass-1/2/3 checklists, claim → evidence map, computed verdict (`passed`/`failed`/`blocked`) + 3-round cap, score rubric. | Stage 8.7 (`/paper verify`) |

## Progress display

Every `/paper` subcommand ends by printing a **one-line progress footer** so the user
always knows which stage they're at and what's next. `/paper status` prints the full
multi-line **board** and persists it to `<direction>/status.md`.

Both visualizations are produced by pure helpers in
`research_assistant.papers` — they take `(venue, direction, StageStatus)` and return
a Markdown string. The skill body just prints what they return.

```
# footer (after any /paper subcommand) — ⚠ N debts shows only when > 0
── NeurIPS-2026 / diffusion-finetune   [######-] 6/7   ⚠ 2 debts   next: /paper render ──

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
         debts       2 open · 1 citation · 1 evidence

Suggested next: /paper render
```

The 7-stage bar counts pipeline checkpoints
(`venue, direction, scout, focus, motivate, write, render`); `cite` is shown as a
sidebar check because `/cite` is a separate command. Use `[x]` done / `[.]` partial /
`[ ]` empty. The `debts` sidebar (shown when a direction is resolved) rolls up
open placeholder tokens + unresolved `\cite{}` keys by class — see Stage 6's
evidence-first rules; `none ✓` when clear.

Helpers (all in `research_assistant.papers`):

- `stage_status(direction_dir) -> StageStatus` — inspect a direction folder.
- `render_progress_footer(venue, direction, status, debts=None) -> str` —
  one-line footer. Tolerates `None` for direction/status (use during Stage 1 or
  before any venue). Pass `debts` to append `⚠ N debts` when > 0.
- `render_progress_board(venue, direction, status, debts=None) -> str` — full
  Markdown board. Pass `debts` to add the `debts:` sidebar line.
- `next_suggested(status) -> str` — the next-step command shown in both renders.
- `debt_summary(direction_dir) -> DebtSummary` — open debts by class
  (placeholder tokens + unresolved `\cite{}`). Pass its result to the two
  renderers above.
- `scan_placeholders(direction_dir) -> list[Placeholder]` — every evidence-first
  token with file/line/hint (Stage 6 placeholder audit).
- `write_preflight(direction_dir, venue_dir, section_kind, evidence_present=None)
  -> PreflightResult` — Stage 6 hard gates; `.blocked` + `.render()`.

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

When a `(venue, direction)` is missing locally but a clone of the bound
experiment repo is on disk, run `/paper restore` to recreate the symlinks
explicitly — `/paper status` does NOT auto-restore (it's read-only over the
on-disk state).

## Stage 1 — `/paper venue <slug>`

**Inputs**
- `<slug>` from user (e.g. `NeurIPS-2026`).
- Optional: a CFP URL or pasted call-for-papers text.

**Workflow**
1. Build the canonical slug via `research_assistant.papers.slugify_venue(name, year)`
   — it strips non-alphanumerics and a trailing year in the name so the result
   stays single-year (`"ICLR 2026" → "ICLR-2026"`).
2. Create `outputs/papers/<venue>/` if missing.
3. AI drafts `_venue.md` from the CFP. Sections: page limit, deadlines, review criteria,
   accepted paper styles, recent trends, scoring rubric.
4. Show user the draft; accept inline edits.
5. Write `outputs/papers/<venue>/_venue.md`.
6. `mcp__claude-flow__memory_store(namespace="project/paper-context", key="current",
   value={venue: <slug>, direction: null})`.
7. Bootstrap the template directory. **Check `docs/venues/<CONF>/<YEAR>/`
   first** — if that path exists, the group has already cataloged this venue,
   and the shared snapshot includes `_venue.md` + `_template/` + optionally
   `_venue-refs/`. Tell the user to run:

       cp -r docs/venues/<CONF>/<YEAR>/* outputs/papers/<venue>/

   Then re-read `_venue.md` and refresh deadlines for this cycle. If
   `docs/venues/<CONF>/<YEAR>/` is missing, fall back to the manual path:
   tell the user to drop the conference `.sty`, `.cls`, and (optional)
   `.bst` files into `outputs/papers/<venue>/_template/` — the skill does
   **not** auto-fetch them. Either way, if `_template/` is missing or empty
   when `/paper write` or `/paper render` runs, the render step prints a
   clear "drop the template files here" message and skips the build (the
   `.tex` write itself still succeeds). See `docs/venues/README.md` for the
   shared-library conventions.
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
literature_exempt: false                            # optional; set true to let
                                                    # /paper write draft intro /
                                                    # related-work before /paper
                                                    # scout (clears the write
                                                    # preflight literature gate)
# --- binding fields (set by Stage 0 /paper bind, not direction) ---
experiment: weightlet-1                             # optional; primary binding
experiments: [weightlet-1, sparse-attn-2]           # optional; ALL bindings,
                                                    # consumed by Stage 3 scout
                                                    # (find_experiments_for_paper)
                                                    # and surfaced as "local
                                                    # experiments touching this
                                                    # direction". Primary is
                                                    # auto-included; list extras
                                                    # here to surface them too.
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
5. **Surface local experiments touching this direction** so the user sees what
   they've already run alongside the external literature:
   - Call `research_assistant.papers.find_experiments_for_paper(venue, direction)`
     — explicit hits from `manifest.papers` containing `<venue>/<direction>` plus
     the bound primary from `expert.md`.
   - For semantic discovery, also call
     `mcp__claude-flow__memory_search(namespace="project/experiments", query=<keywords>)`
     and `mcp__claude-flow__memory_search(namespace="project/experiments/<slug>/versions", query=<keywords>)`
     for each hit slug; print top 3 most relevant versions per experiment.
   - Render a table: `slug | title | status | latest_version | binding_source`.
     If the list is empty, print one line ("no local experiments bound to this
     direction yet — `/experiment init` to start one") and move on.
6. Print `render_progress_footer(venue, direction, stage_status(direction_dir))`.

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

This stage is **LaTeX-native**: paper prose goes into `.tex` files that build to
a real PDF via the conference template. Markdown planning artifacts
(`outline.md`, `focused-problem.md`, `experiments/*.md`) stay Markdown.

**Before drafting anything, load these references** (full content described in
the [References](#references-load-on-demand) section near the top of this
file):

- `references/section-heuristics.md` — per-section Do/Don't/Beats lists +
  venue-family overrides. Required prelude.
- `references/latex-conventions.md` — project-wide LaTeX style rules. Required
  prelude.
- `references/write-workflow.md` — the full Stage-6 decision flow this section
  summarises. Load when you actually start drafting.

**Resolve the venue family** before reading any section block. Call
`research_assistant.papers.family_for_venue(venue)`; it returns one of
`systems` / `nlp` / `cv` / `ml` / `db` / `ir` / `default`. The resolver checks
`_venue.md` for an explicit `Family: <name>` override line first, then falls
back to a built-in venue-prefix map. When the family is `systems`, `nlp`, or
`cv`, `section-heuristics.md` carries a matching `## family: <name>` block with
**additive** `### <kind>` sub-blocks — extra Do / Don't / Beats items to layer
on top of the default `## section: <kind>` block. Users can pin a niche venue
to the closest family by adding `Family: systems` to its `_venue.md`.

**Preflight gate (run first, full prose in `write-workflow.md`).** Before
drafting, call `research_assistant.papers.write_preflight(direction_dir,
venue_dir, section_kind, evidence_present=...)`. If `result.blocked`, print
`result.render()` and **STOP** — the user clears the gate (no `_venue.md` →
`/paper venue`; no `focused-problem.md` → `/paper focus`; `intro`/`related-work`
with empty `related-papers/` and no `literature_exempt` → `/paper scout`) or
re-runs with `--force`. Warnings (e.g. a `results` section with no experiment
yet) print but don't block.

**Evidence-first — never fabricate.** A claim with no support gets a
placeholder token, not an invented fact: `[REF_NEEDED: …]`,
`[FIGURE_NEEDED: …]`, `[DATA_NEEDED: …]`, `[CLAIM_UNVERIFIED: …]`. After every
write, run `papers.scan_placeholders(direction_dir)` and surface the tokens;
they roll up into the footer/board as debts. Full token table + close-out paths
in `write-workflow.md`.

**Cross-cutting principles (full prose in `write-workflow.md`):**

- **Drafting order is figures → method → results → related-work → intro →
  abstract → title** — not IMRAD. Method first locks vocabulary; title last
  because abstract narrows what title can promise.
- **Funnel-gate the introduction.** Before drafting `intro`, plain-text prompt
  `"Funnel check: broad → existing → best → limitations → goal? (yes / draft
  anyway / abort)"`; on `abort`, stop.
- **Banned phrases in intro.** After writing `sections/intro.tex`, grep for
  `novel|first ever|first time|paradigm-(changing|shifting)|we propose`; warn
  with line numbers, no auto-rewrite.
- **Hard-rule lint** (every `.tex` write): grep for stray `;`, `---`, and `--`
  outside numeric ranges. Definitions in `latex-conventions.md` →
  `hard-rules`. Warnings only.
- **Chinese translation comments** above every English paragraph in body
  prose (skip `algorithms/*.tex`, `refs.bib`, preamble). Exact shape in
  `latex-conventions.md` → `hard-rules`.
- **Title-revisit** at the end of Stage 6: re-read `\title{}` against the now-
  stable abstract; propose 3 revisions; let the user pick.

**Workflow summary** — `write-workflow.md` has the full step-by-step. The two
top-level branches are:

- **No section given** → generate `outline.md`, scaffold `main.tex +
  sections/ + refs.bib`, call `pseudocode.preamble.ensure_preamble(...)`,
  surface unmade figures (one `→ /figure new <slug>` per outline figure row),
  print the recommended drafting order.
- **Section given** → resolve kind via synonym map, layer family block,
  read context (`expert.md`, `focused-problem.md`, `experiments/*`,
  `related-papers/`, prior `sections/*.tex`); for `results`-kind sections,
  also call `papers.collect_experiment_results_for_paper(venue, direction)`
  and prefer the experiment's `analysis_tex` as authoritative; intro funnels
  through the gate above; title triggers title-revisit; otherwise draft
  `sections/<section>.tex`, run banned-phrase scan + hard-rule lint, append
  `% TODO:` block.
- **Figure inclusion** and **algorithm inclusion** patterns (the exact
  `\begin{figure}[t]` / `\input{algorithms/<slug>.tex}` blocks plus the
  `<W>` size mapping and the experiment-scope path variants) are in
  `write-workflow.md`.

**Auto-render** after every successful section write — full fallback chain
(tectonic → latexmk, missing-toolchain hint, last-40-log on failure, never
undo the write) is in `write-workflow.md`.

After everything above (whether the render fired or not), print the footer
with the debt roll-up:
`render_progress_footer(venue, direction, stage_status(direction_dir), debt_summary(direction_dir))`.

## Stage 7 — `/paper status [<venue>/<direction>] [--all]`

**Workflow**

- **Default (current direction)**:
  1. Read `project/paper-context.current` to resolve `(venue, direction)`.
     If unset: print the no-venue / no-direction footer and stop.
  2. Compute `status = stage_status(direction_path(venue, direction))` and
     `debts = debt_summary(direction_path(venue, direction))`.
  3. Print `render_progress_board(venue, direction, status, debts)` — the board
     gains a `debts:` sidebar line (open count by class, or `none ✓`).
  4. Persist the same string (plus a trailing newline) to
     `<direction>/status.md` — overwrite, this is a snapshot.
  5. Print `render_progress_footer(venue, direction, status, debts)`.
- **Explicit target — `/paper status <venue>/<direction>`** (recovery path for
  in-flight projects whose AgentDB cursor is stale or unset):
  1. Parse the positional arg, split on `/` into `venue` and `direction`. Reject
     if either half is empty.
  2. Verify `direction_path(venue, direction)` exists on disk; if not, error out
     ("no such direction under outputs/papers/...") without writing anything.
  3. Compute `status = stage_status(...)` and `debts = debt_summary(...)`.
  4. Print `render_progress_board(venue, direction, status, debts)` and persist
     `<direction>/status.md` (same as default).
  5. **Adopt the target as the new cursor**:
     `mcp__claude-flow__memory_store(namespace="project/paper-context",
     key="current", value={venue, direction})`. Subsequent stages pick up here.
  6. Print `render_progress_footer(...)`.
- **`--all`**:
  1. Walk `outputs/papers/*/` for venues.
  2. For each venue, walk subdirectories that are not `_template/`; treat each as
     a direction.
  3. For each `(venue, direction)`, compute `stage_status` + `debt_summary`,
     print `render_progress_board(venue, direction, status, debts)` separated by
     `---` lines, and persist the same string to `<direction>/status.md`
     (overwrite — one-shot refresh of every direction's snapshot).
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

## Stage 8.5 — `/paper humanize [<section>] [--dry-run]`

Post-draft pass that strips AI-tone from the prose in `sections/*.tex`. The
prompt comes from `references/humanize-prompt.md` — adapted from the
[awesome-ai-research-writing](https://github.com/Leey21/awesome-ai-research-writing)
"去 AI 味（LaTeX 英文）" entry.

**Inputs**
- Current `(venue, direction)` from `project/paper-context.current`. Reject if
  unset.
- Optional positional `<section>` — process only `sections/<name>.tex`. Section
  synonyms resolve via the same map used by `/paper write` (e.g. `eval` →
  `results`). Default = every `sections/*.tex` in the direction.
- `--dry-run` flag — write to `sections/<name>.humanized.tex` instead of
  overwriting; the user diffs and chooses what to keep.

**Workflow**
1. Resolve cursor → `(venue, direction)`. Verify
   `outputs/papers/<venue>/<direction>/sections/` exists; if empty, point the
   user at `/paper write` and stop.
2. Resolve the target file list. For each file:
   - **Read** the body of `sections/<name>.tex`.
   - **Load** the humanize prompt prelude from
     `references/humanize-prompt.md` (verbatim).
   - **Apply** the prompt with the file body as the `# Input` block.
   - **Parse** the three-part response (`Part 1 [LaTeX]`,
     `Part 2 [Translation]`, `Part 3 [Modification Log]`).
3. **Skip-on-sentinel.** If Part 3 starts with the literal prefix
   `[检测通过]`, the model judged the prose already natural — do NOT rewrite
   the file. Record a `skipped: true` row in the audit log.
4. **Rewrite** (unless `--dry-run`):
   - default: overwrite `sections/<name>.tex` with Part 1.
   - `--dry-run`: write `sections/<name>.humanized.tex` and leave the original
     untouched.
5. **Audit log.** Append a section to
   `<direction>/reviews/humanize-<YYYY-MM-DD>.md` per file, capturing
   `section`, `skipped?`, the Modification Log, and the Chinese translation.
   Same-day reruns get `-2`, `-3`, … suffix (collision-safe).
6. **Auto-render.** After all files are processed (and at least one was
   rewritten), trigger the same render path as `/paper render`. Skip when
   `--dry-run` because the live `.tex` files are unchanged.
7. Print a one-line summary table (`section · status · log path`) followed by
   `render_progress_footer(venue, direction, stage_status(direction_dir))`.

**Output files**
- `outputs/papers/<v>/<d>/sections/<name>.tex` — rewritten (or untouched if
  skipped or dry-run).
- `outputs/papers/<v>/<d>/sections/<name>.humanized.tex` — dry-run only.
- `outputs/papers/<v>/<d>/reviews/humanize-<YYYY-MM-DD>.md` — audit log.

**Memory keys touched** — none. This is purely file-level.

## Stage 8.6 — `/paper review [--target <venue-slug>]`

Reviewer-perspective audit of the **rendered PDF** for the current paper.
Used before submission / rebuttal / advisor sync. The prompt comes from
`references/review-prompt.md` — adapted from the
[awesome-ai-research-writing](https://github.com/Leey21/awesome-ai-research-writing)
"论文整体以 Reviewer 视角进行审视" entry.

**Inputs**
- Current `(venue, direction)` from cursor. Reject if unset.
- The direction's `main.pdf`. If absent, point the user at `/paper render`
  first and stop — reviewers see typeset output, not raw `.tex`, so the audit
  must mirror that.
- Optional `--target <venue-slug>` — overrides the target venue used in the
  prompt's `# Input` substitution. Default = cursor venue.

**Workflow**
1. Resolve cursor → `(venue, direction)`. Verify `main.pdf` exists; if not,
   suggest `/paper render` and stop.
2. **Load** the review prompt prelude from `references/review-prompt.md`.
3. **Read the PDF** via the multimodal `Read` tool —
   `Read(main_pdf_abs_path, pages="1-N")` — so figures, tables, and layout are
   visible. Choose `pages="1-12"` for typical conference papers; expand if
   the page count exceeds 12 (read in 12-page windows until done).
4. **Substitute** the literal token `{{TARGET_VENUE}}` in the prompt with the
   resolved target venue slug (e.g. `ICML 2026`). The substitution happens in
   code; the model never sees the placeholder.
5. **Apply** the prompt and parse the two-part response (`Part 1 [The Review
   Report]` and `Part 2 [Strategic Advice]`).
6. **Write** the full response to
   `<direction>/reviews/review-<YYYY-MM-DD>.md` with YAML frontmatter:

   ```yaml
   ---
   date: 2026-06-02
   target_venue: ICML 2026
   reviewer: claude-sim
   ---
   ```

   Collision-safe — same-day reruns append `-2`, `-3`, … to the filename.
7. **Surface** to the user: the Rating line from Part 1 + the first
   action-item bullet from Part 2's `行动指南` block. Then
   `render_progress_footer(venue, direction, stage_status(direction_dir))`.

**Output files**
- `outputs/papers/<v>/<d>/reviews/review-<YYYY-MM-DD>.md`

**Memory keys touched** — none. This is purely a write-to-disk audit.

## Stage 8.7 — `/paper verify [<section>] [--round N]`

Source-level **evidence-closure** audit — the engineering counterpart to the
PDF-reading `/paper review`. Where `review` judges the typeset paper as a
reviewer, `verify` checks the `.tex` source + bound-experiment outputs against
a typed **debt ledger** and a **claim → evidence map**, in three ordered passes.
Full protocol in `references/verify-workflow.md`; load it when running this
stage. Adapted from the *academic-reviser* discipline of
[joshua-zyy/academic-paper-writer](https://github.com/joshua-zyy/academic-paper-writer).

**Inputs**
- Current `(venue, direction)` from cursor. Reject if unset.
- Optional positional `<section>` — verify only `sections/<name>.tex` (kind
  synonyms resolve as in `/paper write`). Default = every drafted section.
- `--round N` — the revision round for the iteration cap (default: 1, or
  one past the latest report's round for this section).

**The iron rule:** run **Pass 1 Evidence → Pass 2 Argument → Pass 3 Style**, in
that order, never skipping. Pass 3 is reporting-only while a hard debt is open —
don't polish prose over unverified facts.

**Workflow** (per section)
1. Resolve cursor → `(venue, direction)`. Verify the section file(s) exist; if
   none, point the user at `/paper write` and stop.
2. **Pass 1 — Evidence.** Read the section. For every claim, add a
   `ClaimEvidence(claim, evidence, verified)` row (`exp:<slug>@<vN.M>` /
   `cite:<slug>` / `""` for naked). Cross-check numbers against
   `papers.collect_experiment_results_for_paper(...)` (`analysis_tex` /
   mirrored `results/`). Set `citation` / `evidence` / `figure` debt status;
   confirm `refs.unresolved_cite_keys(direction_dir) == []`.
3. **Pass 2 — Argument.** Read as a skeptical reviewer (the 7 risk questions in
   `verify-workflow.md`). Open `consistency` debt with a note when a promise,
   baseline, ablation, or overclaim fails.
4. **Pass 3 — Style.** Only now: open `prose` debt for comprehension-blocking
   defects (not taste — that's `/paper humanize`).
5. Build the `VerificationReport` (`section`, `date`=today, `round`, `score`
   1–10, `debts`, `claims`, `notes` = the three-pass narrative) and call
   `papers.write_verification_report(direction_dir, report)`. It runs
   `finalize_verdict` — **the verdict is computed from the ledger**, not your
   opinion: `passed` (no open hard debt), `failed` (hard debt, round < 3),
   `blocked`+`unresolvable` (hard debt at round 3).
6. Print the verdict + score + open-debt list. If `papers.naked_claims(
   direction_dir)` is non-empty, print those rows — they're the worst gaps.
7. Print `render_progress_footer(venue, direction, stage_status(direction_dir),
   debt_summary(direction_dir))` — `consistency`/`prose` now surface in the
   board's `debts:` line beside the live citation/figure/evidence counts.

**Output files**
- `outputs/papers/<v>/<d>/reviews/verify-<section>-<YYYY-MM-DD>.md` — YAML
  frontmatter (the machine-readable ledger: verdict, score, debts, claims) +
  human-readable body. Collision-safe (`-2`, `-3`, …) for same-day reruns.

**Memory keys touched** — none. Purely write-to-disk, like `humanize` / `review`.

## Stage 9 — `/paper archive [<venue>/<direction>] [--abandoned]`

Terminal stage. Moves a finished paper out of the active `outputs/papers/`
tree and into `inputs/past-work/<slug>/paper/`, while auto-creating (or
merging into) a sibling `inputs/past-work/<slug>.md` past-work entry. The two
together let the `past-work-historian` agent surface the paper during future
`/idea-check` and `/paper direction` recalls — archiving doesn't delete
anything, it just demotes the paper from "active" to "historical".

**Preconditions**
- Either `<venue>/<direction>` is passed as an arg, or the cursor in
  `project/paper-context.current` resolves to a real direction folder.
- The direction is **not** a symlink. A symlinked direction is bound to an
  experiment repo via `/paper bind`; archiving the symlink would dangle the
  link. Refuse with a hint to run `/paper unbind` first.

**Workflow**
1. Resolve `(venue, direction)`. Print a one-line summary
   ("about to archive `<venue>/<direction>/` → `inputs/past-work/<slug>/`")
   so the user can ctrl-C if surprised.
2. Call `research_assistant.papers.archive_direction(venue, direction,
   abandoned=<flag>)`. Surface exceptions cleanly:
   - `ArchiveError("... is a symlink ...")` → user runs `/paper unbind` first.
   - `ArchiveError("no such direction ...")` → user typo'd or the cursor is stale.
3. The helper:
   - Computes `slug = slugify(f"{venue}-{direction}")` (collision-safe — picks
     `<slug>-2`, `<slug>-3`, ... if the companion folder is taken).
   - Pulls the title from `expert.md` frontmatter or `main.tex` `\title{...}`.
   - Pulls the abstract from `main.tex` `\begin{abstract}` (or
     `sections/abstract.tex`) if present.
   - Reads any `experiment:` binding from `expert.md` and stamps it as
     `experiment:<slug>` in the new past-work entry's `links:` list.
   - Moves the direction tree to `inputs/past-work/<slug>/paper/`.
   - Appends `archived: <YYYY-MM-DD>` to the moved `status.md` (or creates one).
   - Writes / merges `inputs/past-work/<slug>.md` — preserves any user prose,
     fills empty frontmatter fields, dedupes the `links:` list.
4. Clear the paper-context cursor if it pointed at this paper:
   `mcp__claude-flow__memory_store(namespace="project/paper-context",
   key="current", value={venue: null, direction: null})`.
5. Print the `ArchiveResult` (slug, destination paths, entry-created vs merged).
6. Print `render_progress_footer(None, None, None)` — no current paper.

**`/paper unarchive <slug>`** — reverse the move. Reads `(venue, direction)`
from the archived `expert.md` frontmatter (or the `archived-from:` link in
the past-work .md as fallback). Calls
`research_assistant.papers.unarchive_direction(slug)`. Refuses if
`outputs/papers/<venue>/<direction>/` already exists. The past-work
`<slug>.md` is left in place — user keeps or deletes manually.

**`/paper archive list`** — call `research_assistant.papers.list_archived()`
and print a table of every archived paper (slug, venue, direction,
archived-on, has-pdf).

**Venue-level files are NOT moved.** `outputs/papers/<venue>/_venue.md`,
`outputs/papers/<venue>/_template/`, and `outputs/papers/<venue>/_venue-refs/`
stay where they are — they're shared across every direction in that venue,
including any future ones the user starts.

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

_All previously-tracked items shipped. Cross-skill items belong in the
relevant SKILL (e.g. `/mentor add-past-work` UX is owned by
`research-mentor/SKILL.md`)._
