---
name: idea-validate
description: Socratic research-direction tool — walk the user through Socratic discussion, scout the last 3 years of arXiv + WebSearch, score value/feasibility, recommend venues, emit a brain-library index, hand off to /paper. Each idea is persisted as an on-disk manifest under outputs/idea-checks/<slug>/ and mirrored to AgentDB ideas/<slug>. Also retains the legacy horizontal-matrix and vertical-lineage modes. Use when the user says "help me find a research direction", "is this idea novel", "compare these N papers", "what should I learn for this idea", "where does this idea come from", or triggers `/idea-check`.
---

# idea-validate

A captured idea is the source of truth on disk:
`outputs/idea-checks/<slug>/idea.md` (manifest) + the stage artifacts beside it.
AgentDB `ideas/<slug>` mirrors the manifest for semantic search; if AgentDB is
wiped, `research_assistant.ideas.registry.reindex_from_disk()` rebuilds it.

## Mental model

```
/idea-check "<free-text idea>"
    │
    ▼
Stage 1 — Socratic   (multi-turn Q&A → distilled statement + slug)
    │   …idea is persisted here, even if user stops…
    ▼
Stage 2 — Scout      (arxiv last 3 years; WebSearch fallback for non-arXiv venues)
    │
    ▼
Stage 3 — Evaluate   (5 value axes + 5 feasibility axes, 1–5 each)
    │
    ▼
Stage 4 — Venues     (curated registry × user-curated _venue.md, top 3–5)
    │
    ▼
Stage 5 — Knowledge  (brain-library index → AgentDB ideas/<slug>/knowledge)
    │
    ▼
Stage 6 — Handoff    (writes project/paper-context.current; user runs /paper direction)
```

Each stage is **re-enterable** via its own subcommand. The cursor at
`project/idea-context.current` keeps the "active idea" across invocations so
you never need to retype the slug.

## References (load on demand)

Stable, detail-heavy content lives in `references/` so this SKILL stays scan-
nable. Each entry below names the file, what it contains, and the stage(s)
that pull it in:

| File | Contents | Loaded by |
|---|---|---|
| `references/socratic-workflow.md` | Stage 1 full step-by-step: the 6 plain-text rounds (problem / why-now / gap-and-claim / failure-mode / past-work-recall / distill-and-confirm), the hypothesis-tree shape (`H1` root, optional `H1.1` children, depth cap), the persistence block (manifest save, AgentDB writes, cursor set), and the downstream contract with `/experiment design`. | Stage 1 (`/idea-check` initial capture, `/idea-check socratic`) |
| `references/brainstorm-workflow.md` | Stage 1.5 full step-by-step: scope check, the 4 phases (diagnose / diverge / converge / refine), the 4 handoff kinds (`spawn-sibling` / `refine-active` / `park` / `none`), the save block, and the re-entry contract. The 11 frameworks `F1`…`F11` + Selection Guide + convergence filters live in `ideation-frameworks.md` — load both files together. | Stage 1.5 (`/idea-check brainstorm`) |
| `references/scout-workflow.md` | Stage 2 + 2.5 full step-by-step: arXiv-first scout, the OSDI/SOSP/NSDI/USENIX/CHI/SIGMOD/VLDB WebSearch fallback rule, the 4 gap-consolidation buckets (`tried` / `untried` / `where_broken` / `future_work`), the AgentDB indexing fanout (`papers/<slug>` + `ideas/<slug>/scout`). Plus the Stage 2.5 Contrarian micro-flow auto-trigger (skip-on `跳过`, the 4 questions, accept-vs-reject branches, idempotent scout.md appendix). | Stage 2 (`/idea-check scout`); Stage 2.5 (`/idea-check contrarian`) |
| `references/ideation-frameworks.md` | The 11 ideation frameworks (`F1`…`F11`) with their workflows + the Selection Guide table mapping user stuck-state to recommended framework set + the convergence filters (explain-it test, problem-first, simplicity, stakeholder check, feasibility) used in Stage 1.5 Phase 3. Adapted from Orchestra-Research/AI-Research-SKILLs MIT `21-research-ideation/`. | Stage 1.5 (alongside `brainstorm-workflow.md`) |

## Response style (applies to every stage)

`/idea-check` is the place where sycophancy does the most damage — a flat-
tering Socratic round produces an idea that *feels* validated without ever
being stress-tested. Apply these rules across all stages:

- **No flattery.** Don't open with "great idea / interesting direction /
  promising framing". The user's idea is a hypothesis to be examined, not a
  result to be celebrated. Compliments should be **observations**
  ("this targets a real gap from paper X"), not affect.
- **Both sides may be wrong.** Your answers can be wrong, and the user's
  framing can be wrong — including the framing of the question itself. If
  Stage 1 turns up an unstated assumption that breaks the whole idea, say
  so plainly rather than coaching around it.
- **Verify before asserting.** When a stage involves a factual claim
  ("nobody has tried X", "method Y is SOTA on benchmark Z"), run the check
  — scout call, AgentDB lookup, WebSearch — before stating it. Mark
  un-verified claims as such ("I haven't searched for this; based on memory
  only…").
- **Push back when warranted.** Stage 3 (evaluate) is the explicit
  pushback stage, but the same posture applies in Stage 1 / 2 / 2.5. If a
  user-stated novelty conflicts with what scout found, surface the conflict
  in the *next* turn rather than waiting for the user to notice.
- **Ask for evidence, not opinion.** When something is genuinely
  ambiguous (target users, evaluation metric, novelty boundary), ask a
  concrete probe — "name one paper this should beat" — rather than an
  open-ended "what do you think?". One pointed question beats five vague
  ones.
- **Structure every reply.** Lead with the Socratic question or the
  verdict; follow with the evidence; keep bullets/sections short. Walls of
  prose are a smell — break them into "what I see / what I'm asking /
  what's next".

## Always do this first (cursor read)

At every `/idea-check ...` invocation that isn't `list` or `show <slug>`:

* `mcp__claude-flow__memory_retrieve` namespace=`project`, key=`idea-context.current`
  → expect `{"slug": "...", "area_tags": [...]}` or absent. (The manifest — read
  via `registry` / `status` — is the source of truth for the current stage and
  the chosen venue; the cursor only carries the slug + tags, which is all
  downstream stages need to locate the idea folder.)
* If absent and the subcommand needs an active idea (`scout`/`evaluate`/`venues`/
  `knowledge`/`handoff`/`status`/`horizontal`/`vertical`), tell the user:
  `Run /idea-check "<your idea>" first to capture it.`

## Subcommand router

| Subcommand | Action |
|---|---|
| `/idea-check "<free-text>"` | Auto-start Stage 1; walks through subsequent stages with plain-text confirmations between each. |
| `socratic` | Re-enter Stage 1 for the active idea (refine / edit the statement). |
| `brainstorm [<situation>]` | Stage 1.5 — fresh-angles micro-flow when Socratic stalls. Picks 2–3 lenses from `references/ideation-frameworks.md` and walks diverge → converge → refine. Output appends to `<slug>/brainstorm.md`. |
| `scout` | Run Stage 2 for the active idea. |
| `evaluate` | Run Stage 3. |
| `venues` | Run Stage 4. |
| `knowledge` | Run Stage 5. |
| `handoff` | Run Stage 6. |
| `status` | Print `outputs/idea-checks/<slug>/status.md` for the active idea. |
| `list` | Print `outputs/idea-checks/_index.md` (the vault registry). |
| `show <slug>` | Print the manifest + status board for one idea. |
| `horizontal <free-text>` | Legacy mode: related-work matrix (now backed by `ideas.build_horizontal_matrix`). |
| `vertical <slug>` | Legacy mode: lineage trace (now backed by `ideas.build_vertical_lineage`). |

## Stage 1 — Socratic

**Goal:** distill a free-form idea into one persisted manifest with a 1–2
sentence statement, area tags, and a slug.

**Constraint:** plain-text questions, one turn at a time (per
`feedback_decision_ui` memory — never `AskUserQuestion`). Build a
`research_assistant.ideas.socratic.SocraticTrace` and append every Q/A via
`record_turn(trace, q, a)`.

Full per-round prompts and the persistence block are in
`references/socratic-workflow.md`. The 6-round shape:

1. **Round 1 — problem** (one-sentence problem statement).
2. **Round 2 — why now** (urgency + beneficiary).
3. **Round 3 — gap + claim** — collects a **hypothesis tree** (`H1` root,
   optional `H1.1` children, optional independent `H2` roots; each with an
   optional one-line `prediction`). Stored as `socratic.Hypothesis`
   instances in `trace.hypotheses`. The tree flows downstream — `/experiment
   design` Stage 3 step 2 reads it via
   `socratic.to_experiment_hypothesis_seed(trace)`.
4. **Round 4 — failure mode.**
5. **Round 5 — past-work recall** (invoke `past-work-historian` via the
   `Agent` tool; record matches as `[[prior-slug]]` in
   `trace.past_work_refs`).
6. **Round 6 — distill + confirm** — propose `(slug, area_tags, statement)`,
   user confirms or edits.

**On confirm:** save the manifest via `registry.save_idea(...)`, render
`socratic.md`, mirror to AgentDB (`ideas/<slug>`, `ideas/<slug>/socratic`,
`project/idea-context.current`), then offer to continue with
`/idea-check scout`. The idea is durable from this point; users can resume
anytime via `/idea-check show <slug>`.

## Stage 1.5 — Brainstorm (escape hatch)

**Goal:** when Socratic stalls — the idea feels incremental, the user can't
fill the two-sentence test, or the same shape keeps coming back — pick 2–3
ideation frameworks and walk a structured diverge → converge → refine
session. Adapted from Orchestra-Research/AI-Research-SKILLs (MIT)
`21-research-ideation/`.

**Required loads:** `references/brainstorm-workflow.md` AND
`references/ideation-frameworks.md`. The frameworks file carries `F1`…`F11`
(stable codes — quote by code in prompts and the trace), the Selection
Guide table that maps user stuck-state to recommended framework set, and
the convergence filters. The workflow file carries the 4-phase flow.

**High-level shape** (full step-by-step in `brainstorm-workflow.md`):

1. **Resolve scope** — require an active idea cursor; refuse with
   `Run /idea-check "<your idea>" first` if absent.
2. **Phase 1 — diagnose** — one plain-text question on what's stuck;
   match against Selection Guide; pick 2–3 framework codes; build a
   `BrainstormTrace`.
3. **Phase 2 — diverge** — 3–6 turns per framework (total ≤ 12); capture
   10–20 raw candidates via `brainstorm.add_candidate(...)`. **Don't
   filter yet.**
4. **Phase 3 — converge** — apply the reference's filters; user picks
   which to keep; call `brainstorm.converge(trace, keep=[...],
   kill_reasons={...})`.
5. **Phase 4 — refine** — for each survivor, run F10's two-sentence test
   and route via `trace.handoff` to one of:
   - `spawn-sibling` → `registry.create_variant_idea(...)`; optionally
     switch cursor.
   - `refine-active` → store refined statement; user runs
     `/idea-check socratic` to re-enter Stage 1.
   - `park` → keep the trace; no follow-up action.
   - `none` → user ended early.
6. **Save** — write `brainstorm.md` via `brainstorm.render_brainstorm_md(...)`,
   mirror to AgentDB `ideas/<slug>/brainstorm`. For `spawn-sibling`, also
   write the sibling's files (same shape as Stage 2.5 Contrarian).
7. **Print summary + next step** keyed off the handoff kind.

**Re-entry:** safe to call multiple times — overwrites prior
`brainstorm.md`, AgentDB key is single per parent.

## Stage 2 — Scout (近三年)

**Goal:** ground the discussion in real, recent literature.

Full step-by-step in `references/scout-workflow.md`. High-level:

1. **Load idea + confirm query/year range** — defaults to slug+statement
   keywords + last-3-years; user can override.
2. **arXiv primary** — `scout.scout_recent_papers(query, year_range,
   max_results=25)`.
3. **Non-arXiv fallback** — when area tags include `{sys, sec, db, hci}`
   and arXiv yielded < ~5 hits, fall back to `WebSearch` against OSDI /
   SOSP / NSDI / USENIX / CHI / SIGMOD / VLDB / etc.
4. **Cluster + relation notes** — 2–3 sentences per paper: *what they
   did, how it relates, why it doesn't subsume yours*. Cite by URL +
   arXiv ID.
5. **Gap consolidation** — populate `result.gaps` (a `ScoutGaps`
   instance) with four buckets (`tried` / `untried` / `where_broken` /
   `future_work`). 1–4 bullets each; empty buckets are fine. Adapted
   from Orchestra-Research/AI-Research-SKILLs MIT `0-autoresearch-skill`.
6. **Render** `scout.md` via `scout.render_scout_md(result)`.
7. **Index every paper** under AgentDB `papers/<paper-slug>` (reusable
   by `/paper scout`); mirror the full result to `ideas/<slug>/scout`.
8. **Mark scouted** via `registry.update_idea(slug, status="scouted")`.
9. **Cluster review** — multi-round plain-text refinement until the user
   is satisfied with coverage. Offer to `/summarize` specific papers
   (don't auto-invoke).

### Stage 2.5 — Contrarian micro-flow (反其道而行)

**Goal:** after the user has seen the last-3-years mainstream, ask
whether inverting the dominant assumption could win — capture the
inversion as a sibling idea so both framings live alongside each other.

**Auto-triggered** at the end of Stage 2 (right after step 9 above).
Bail by answering `skip` / `跳过` to Q1. Re-entry on demand via
`/idea-check contrarian` (or `/idea-check contrarian <slug>` for a
specific idea).

Full step-by-step in `references/scout-workflow.md` (under "Stage 2.5").
High-level:

- Build a `contrarian.ContrarianTrace(parent_slug, parent_statement)`.
  Append every Q/A via `contrarian.record_turn(trace, q, a)`.
- **4 questions** in order — Q1 mainstream pattern (skippable with
  `skip` / `跳过`, which short-circuits to Stage 3 with an audit-only
  AgentDB mirror), Q2 shared assumption, Q3 inversion, Q4 win condition.
- **Distill** a 1–2 sentence contrarian framing; show
  `(<parent>-contrarian, framing)`; ask `Y / N / 编辑`.
- **On `Y`** — `registry.create_variant_idea(...)` writes the sibling
  (collisions resolve to `-contrarian-2`, `-3`); write
  `outputs/idea-checks/<new.slug>/contrarian.md`; idempotently splice
  `## Contrarian framings` into the parent's `scout.md`; AgentDB mirrors;
  offer cursor switch (default keeps cursor on parent).
- **On `N`** — still mirror the trace and the scout.md appendix; no
  sibling created.
- Proceed to Stage 3 on whichever idea the cursor points at.

## Stage 3 — Evaluate

**Goal:** score the idea on 5 value axes + 5 feasibility axes; record a verdict.

1. Build an initial `IdeaEvaluation` (from `research_assistant.ideas.evaluate`):
   - **Value axes** (1–5 each): `novelty`, `technical_depth`, `empirical_impact`,
     `theoretical_contribution`, `audience_scope`.
   - **Feasibility axes** (1–5 each): `data_availability`, `compute_cost`,
     `baseline_reproducibility`, `expected_timeline_months`, `risk_level`.
   - Fill `rationale[axis] = "<one line>"` based on the scout findings +
     Socratic turns.
2. Render via `evaluate.render_evaluate_md(ev)` → write `evaluate.md`.
3. Show the table; ask plain text: `要改哪个分数? (e.g. 把 novelty 改成 4)`
   — accept multi-round edits, re-render after each.
4. Compute verdict from the user's preference (or suggest one): `go` / `pivot`
   / `drop`. Add 2–3 named risks with one-line mitigations.
4.5. **Pre-registration** (only when verdict is `go` or `pivot`; skip on `drop`).
   Adapted from Orchestra-Research/AI-Research-SKILLs (MIT)
   `0-autoresearch-skill` Bootstrap step 4 — "lock evaluation criteria upfront
   to prevent unconscious metric gaming". Ask the user (plain text — one
   question at a time, per the `feedback_decision_ui` memory):
   - `用什么 proxy metric 衡量这个 idea？(应能在分钟级，不是小时级跑出来)`
   - `当前 baseline 数值是多少？来自哪里？(可以是论文报告、prior run、或者业内默认值)`
   - `多少改进算成功？(自由文本：'+10%' / '+0.5 BLEU' / '≥ 0.80' 都行)`
   - `有什么前提需要注意？(可选；e.g. "只在长上下文场景有意义")`
   Persist into `ev.pre_registration = PreRegistration(...)`. Skipping this
   block is allowed — the renderer flags it as "_Not yet locked_" so
   `/experiment design` knows to fall back to its own Metrics prompt.
5. Save:
   - Rewrite `evaluate.md` with final scores + verdict + risks + pre-reg.
   - `mcp__claude-flow__memory_store` namespace=`ideas`, key=`<slug>/evaluation`
     with `ev.model_dump()`. `/experiment design` reads this key via
     `evaluate.to_experiment_metrics_seed(ev)` when the experiment is
     bound to this idea.
   - `registry.update_idea(slug, status="evaluated", verdict=<go|pivot|drop>)`.

## Stage 4 — Venues

**Goal:** rank candidate venues by area-tag overlap, surfacing user-curated
venues first.

1. `matches = research_assistant.ideas.venues.suggest_venues(area_tags,
   top_k=5)`. This layers the curated `VENUE_REGISTRY` with any
   `outputs/papers/<venue>/_venue.md` files the user has already curated
   (those get ⭐ + a fit-score boost).
2. Render with `venues.render_venues_md(matches, area_tags)` → write
   `venues.md`. Show the table.
3. Ask plain text: `选一个 venue (输入 slug,或者输入新的 venue 让我加注册表)`.
4. Persist:
   - `registry.update_idea(slug, venue=<picked>, status="venued")` — the
     manifest is the source of truth for the chosen venue.
   - `mcp__claude-flow__memory_store` namespace=`ideas`, key=`<slug>/venues`
     with `[m.model_dump(mode="json") for m in matches]` plus
     `{"picked": <slug>}`. Use `mode="json"` so `next_deadline` (a `date`)
     serializes to an ISO string — a raw `model_dump()` keeps `date` objects and
     `json.dumps` would raise.

## Stage 5 — Knowledge (brain-library index)

**Goal:** emit the per-idea study plan that `/paper write` can later ground in.

1. Build a `KnowledgeIndex` (from `research_assistant.ideas.knowledge`) with:
   - **Foundations** (5–10 concepts): each `KnowledgeItem(topic, why_it_matters,
     reading_url)` — pick from the Socratic discussion + scout hits.
   - **Key papers**: prefer entries from the scout (`papers/<slug>` AgentDB
     keys) — `reading_url` should be the arXiv URL.
   - **Tools & datasets**: concrete things to set up.
   - **Adjacent areas**: 2–4 nearby fields the user should keep on-radar.
2. Render with `knowledge.render_knowledge_md(idx)` → write `knowledge.md`.
3. `mcp__claude-flow__memory_store` namespace=`ideas`,
   key=`<slug>/knowledge` with `knowledge.to_agentdb_payload(idx)`.
4. `registry.update_idea(slug, status="knowledge-indexed")`.
5. Ask: `缺哪些条目要补?` — multi-round refine.

## Stage 6 — Handoff

**Goal:** wire the captured + evaluated idea into `/paper`.

1. Print a compact summary (statement, verdict, picked venue, top-3 risks,
   top-3 knowledge items).
2. Plain text: `确定要开始 /paper 吗? Y/N`.
3. If yes:
   - `registry.update_idea(slug, status="handed-off")`.
   - `mcp__claude-flow__memory_store` namespace=`project`,
     key=`paper-context.current` with `{"venue": <venue-slug>,
     "direction": <idea-slug>}`. Use the venue's registry slug as the
     `venue` key (e.g., `neurips`); the actual `outputs/papers/<venue>/`
     directory name is whatever `_venue.md` is filed under (the user picks
     this in `/paper venue`).
   - Tell the user: `Now run /paper direction to continue.`
4. If no: leave the idea at status `knowledge-indexed`; the manifest stays.

## Always-available subcommands

* `/idea-check status`
  - Active idea only. Call `research_assistant.ideas.status.render_status_md(slug)`
    to render the 6-stage checkbox. Persist to `<slug>/status.md`.
* `/idea-check list`
  - Print `outputs/idea-checks/_index.md`. It's rewritten on every
    `save_idea` / `update_idea`, so it's always fresh.
* `/idea-check show <slug>`
  - `manifest = registry.load_idea(slug)` → print the manifest's frontmatter
    + body, then `status.render_status_md(slug)` underneath.

## Legacy modes (still supported)

### Horizontal

1. Pull candidate papers via `mcp__claude-flow__memory_search` namespace=`papers`
   with the idea statement; also walk `outputs/summaries/*.md`.
2. `matrix = research_assistant.ideas.build_horizontal_matrix(summary_paths,
   axes=["problem","method","dataset","metric","gap"])` — returns the
   skeleton; Claude fills each cell from the corresponding paper summary.
3. Render to `outputs/idea-checks/<slug>/horizontal.md`.
4. `mcp__claude-flow__memory_store` namespace=`ideas`,
   key=`<slug>/horizontal` with the filled matrix.

### Vertical

1. Seed = one paper slug or the active idea's slug.
2. `rows = research_assistant.ideas.build_vertical_lineage(seed, summary_paths)`
   — Claude fills each row's `year` and `relationship` from summaries.
3. Render `rows` into a Markdown table — there is no
   `render_vertical_lineage` helper for the legacy mode; the skill prompt
   composes the table directly from the row dicts. Write the result to
   `outputs/idea-checks/<slug>/lineage.md`.
4. `mcp__claude-flow__memory_store` namespace=`ideas`,
   key=`<slug>/lineage`.

## Memory keys touched

| Read | Write |
|---|---|
| `project/idea-context.current` (every entry) | `project/idea-context.current` (each stage) |
| `project/past-work/*` (Socratic stage, via past-work-historian) | `project/paper-context.current` (handoff) |
| `papers/*` (scout reads existing summaries) | `papers/<paper-slug>` (scout indexes each found paper) |
| | `ideas/<slug>` (manifest payload) |
| | `ideas/<slug>/socratic` |
| | `ideas/<slug>/scout` |
| | `ideas/<slug>/contrarian` |
| | `ideas/<slug>-contrarian` (sibling manifest, on accept) |
| | `ideas/<slug>/brainstorm` |
| | `ideas/<slug>-<suffix>` (sibling manifest, on brainstorm spawn-sibling) |
| | `ideas/<slug>/evaluation` |
| | `ideas/<slug>/venues` |
| | `ideas/<slug>/knowledge` |
| | `ideas/<slug>/horizontal` (legacy) |
| | `ideas/<slug>/lineage` (legacy) |

## Error policy

| Failure | Behaviour |
|---|---|
| No active cursor on a stage that needs one | Tell the user `Run /idea-check "<your idea>" first.` |
| Slug already exists at Stage 1 | Ask: `已有同名 idea (<slug>) — 复用 / 起新名 / 取消?` |
| arXiv yields zero rows | Don't refuse the stage; warn + offer WebSearch fallback. |
| Score out of `[1, 5]` (rare; Pydantic catches) | Re-prompt with the valid range. |
| User picks a venue not in the registry | Add a transient `Venue` for the run; suggest curating `_venue.md` under `outputs/papers/<venue>/`. |
| `_index.md` parse error during `list` (malformed manifest) | `list_ideas()` already skips broken entries silently; tell the user which slug is malformed. |

## When NOT to use this skill

* The user already has a venue + direction in `outputs/papers/<venue>/<dir>/`
  and just wants to draft text — use `/paper` instead.
* The user wants a one-off comparison of two specific papers without a slug
  — use the legacy `horizontal` mode.
* The user wants to ingest a PDF into the literature index — use `/summarize`.

## File paths Claude should know

* `research_assistant.ideas.slug.slugify`
* `research_assistant.ideas.contrarian.{ContrarianTrace, record_turn, render_contrarian_md, render_scout_appendix, to_agentdb_payload}`
* `research_assistant.ideas.brainstorm.{BrainstormTrace, BrainstormCandidate, BrainstormHandoff, FRAMEWORK_NAMES, record_turn, add_candidate, converge, survivors, render_brainstorm_md, to_agentdb_payload}`
* `research_assistant.ideas.scout.{scout_recent_papers, ScoutGaps, render_scout_md, to_agentdb_payload}`
* `research_assistant.ideas.socratic.{SocraticTrace, Hypothesis, record_turn, render_socratic_md, to_experiment_hypothesis_seed}`
* `research_assistant.ideas.evaluate.{IdeaEvaluation, IdeaRisk, PreRegistration, render_evaluate_md, to_experiment_metrics_seed, VALUE_AXES, FEASIBILITY_AXES}`
* `research_assistant.ideas.venues.{VENUE_REGISTRY, suggest_venues, render_venues_md, VenueMatch}`
* `research_assistant.ideas.knowledge.{KnowledgeIndex, KnowledgeItem, render_knowledge_md, to_agentdb_payload}`
* `research_assistant.ideas.status.{stage_status, render_status_md}`
* `research_assistant.ideas.registry.{IdeaManifest, save_idea, load_idea, update_idea, list_ideas, render_index_md, to_agentdb_payload, reindex_from_disk, create_variant_idea}`
* `research_assistant.lit.sourcing.{PaperRef, search_arxiv, search_openreview, search_for_direction}` (Stage 2 only uses `search_arxiv` directly; `search_for_direction` is the venue-aware dispatcher used by `/paper scout` and `/scout-swarm`.)
