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

## Always do this first (cursor read)

At every `/idea-check ...` invocation that isn't `list` or `show <slug>`:

* `mcp__claude-flow__memory_retrieve` namespace=`project`, key=`idea-context.current`
  → expect `{"slug": "...", "area_tags": [...], "venue": "...", "stage": "..."}` or absent.
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

**Plain-text questions, one turn at a time** (per `feedback_decision_ui` memory
— never use `AskUserQuestion` for research picks). Build a
`research_assistant.ideas.socratic.SocraticTrace`, append every Q/A with
`record_turn(trace, q, a)`.

Round 1 — problem:
> "用一句话说说你想解决什么问题?"

Round 2 — why now:
> "为什么这个问题现在值得做? 谁会从答案里受益?"

Round 3 — gap + claim (hypothesis tree):
> "你认为现有方法的关键不足是什么? 你假设的突破点在哪儿?"

This round collects a **hypothesis tree** rather than a single statement —
adapted from Orchestra-Research/AI-Research-SKILLs (MIT)
`0-autoresearch-skill` Bootstrap step 3. The model captures:

* The root hypothesis `H1` (the user's distilled claim).
* Optional sub-hypotheses `H1.1`, `H1.2` — only when the user naturally
  spawns follow-ups ("and if H1 holds, then X should also hold").
* Optional independent roots `H2`, `H3` — only when the user explicitly
  raises a second claim worth testing in parallel.
* For each hypothesis: a one-line `prediction` (what observation would
  confirm or falsify it). Predictions stay optional — if the user can't
  yet name one, leave blank rather than fabricate.

Persist as `socratic.Hypothesis` instances appended to
`trace.hypotheses`. The id convention is dotted: `H1.1` is a child of `H1`;
`socratic.Hypothesis` derives `parent` and `depth` from the id (don't
store parent twice). Keep the tree shallow — `H1.1.1` typically means
"this is a new root, lift it to H2". The captured tree flows downstream:
`/experiment design` Stage 3 step 2 reads `ideas/<current>/socratic` via
`socratic.to_experiment_hypothesis_seed(trace)` and pre-fills the design's
`## Hypothesis` section.

Round 4 — failure mode:
> "如果失败,最可能的原因是什么?"

Round 5 — past-work recall (optional but recommended):
> Invoke the `past-work-historian` agent via the Agent tool to surface
> relevant prior projects from `project/past-work/`. If matches come back,
> ask: "这跟你之前的 `<prior-title>` 有什么继承或区别?" — record one or two
> turn into `trace.past_work_refs` (use `[[prior-slug]]` form).

Round 6 — distill + confirm:
1. Draft a 1–2 sentence idea statement; pick area tags (subset of
   `{ml, nlp, cv, sys, db, sec, theory, hci, ir}`); generate the slug via
   `research_assistant.ideas.slug.slugify(statement)`. Show the user the
   triple `(slug, area_tags, statement)`.
2. Ask plain text: `这个表述对吗? Y / 编辑后重写`. If the user revises, set
   `trace.idea_statement` to the corrected text and re-derive the slug only
   if the user explicitly asks.

On confirm:
1. Build `manifest = IdeaManifest(slug, created=today, updated=today,
   statement, area_tags, body=<one-paragraph context>)`.
2. `research_assistant.ideas.registry.save_idea(manifest)` — writes
   `outputs/idea-checks/<slug>/idea.md` AND refreshes `_index.md`.
3. `mcp__claude-flow__memory_store` namespace=`ideas`, key=`<slug>` with
   `registry.to_agentdb_payload(manifest)`.
4. Write `outputs/idea-checks/<slug>/socratic.md` via
   `socratic.render_socratic_md(trace)`.
5. `mcp__claude-flow__memory_store` namespace=`ideas`, key=`<slug>/socratic`
   with `trace.model_dump()`.
6. `mcp__claude-flow__memory_store` namespace=`project`,
   key=`idea-context.current` with
   `{"slug": <slug>, "area_tags": [...], "stage": "captured"}`.
7. Tell the user: `Idea captured at outputs/idea-checks/<slug>/. Run
   /idea-check scout to find recent papers.` Then ask: `要现在就继续 scout 吗? Y/N`.

If the user stops here, the idea is durable. They can resume any time via
`/idea-check show <slug>`.

## Stage 1.5 — Brainstorm (escape hatch)

**Goal:** when Socratic stalls — the idea feels incremental, the user can't
fill the two-sentence test, or the same shape keeps coming back — pick 2–3
ideation frameworks and walk a structured diverge → converge → refine
session. Adapted from Orchestra-Research/AI-Research-SKILLs (MIT)
`21-research-ideation/`. Orchestra keeps brainstorming as a sibling skill
to its autoresearch orchestrator; we mirror that by keeping it as a
sibling subcommand to Socratic rather than embedding it in Stage 1.

Read `references/ideation-frameworks.md` as the prompt prelude. The 11
framework codes `F1`…`F11` are stable slugs — quote them by code in
prompts and the trace.

**Workflow:**

1. **Resolve scope.** Require an active idea cursor; refuse with
   `Run /idea-check "<your idea>" first` if absent. Load the manifest via
   `registry.load_idea(slug)`.
2. **Phase 1 — diagnose.** Ask the user one sentence on why they're
   reaching for brainstorm (plain text — no `AskUserQuestion`):
   `什么让你卡住了？(参考 Selection Guide 的左列)`. Match the answer
   against the Selection Guide table and pick 2–3 framework codes. Build
   a `BrainstormTrace(parent_slug, parent_statement, user_situation,
   frameworks=[<codes>])`.
3. **Phase 2 — diverge** (3–6 turns per framework, total ≤ 12 turns).
   For each chosen framework, run a Q→A→Q sequence using the framework's
   workflow from the reference file. Append every turn with
   `brainstorm.record_turn(trace, framework, q, a)`. Capture raw ideas as
   `brainstorm.add_candidate(trace, framework, pitch)` — aim for 10–20
   raw candidates total. **Do not filter yet.**
4. **Phase 3 — converge.** Show the user the candidate list. Apply the
   filters from the reference file (explain-it test / problem-first /
   simplicity / stakeholder check / feasibility). Plain-text prompt:
   `留哪些？(e.g. "1, 3, 5" or "all" or "none")`. Call
   `brainstorm.converge(trace, keep=[<indices>], kill_reasons={...})`
   with one-line reasons for the killed candidates.
5. **Phase 4 — refine.** For the 1–3 survivors, run the two-sentence
   test (F10) and ask the user what to do:
   - `spawn-sibling` → call
     `registry.create_variant_idea(parent_slug=<active>,
     suffix=<sibling_suffix>, new_statement=<two-sentence pitch>)`.
     Update `trace.handoff = BrainstormHandoff(kind="spawn-sibling",
     statement=<pitch>, sibling_suffix=<suffix>)`. Offer to switch the
     cursor to the new slug (Y/N) — default keeps cursor on parent.
   - `refine-active` → store the refined statement in
     `trace.handoff.statement` and tell the user to run
     `/idea-check socratic` to re-enter Stage 1 with the new framing.
   - `park` → keep the trace but take no follow-up action. Useful when
     the survivors are worth remembering for later.
   - `none` → user ended early; the trace records as far as Phase 3.
6. **Save.**
   - Write `outputs/idea-checks/<slug>/brainstorm.md` via
     `brainstorm.render_brainstorm_md(trace)`.
   - `mcp__claude-flow__memory_store` namespace=`ideas`,
     key=`<slug>/brainstorm` with `brainstorm.to_agentdb_payload(trace)`.
   - If `kind == "spawn-sibling"`, also write the sibling's own files
     (the helper does the slug allocation; the skill writes the sibling
     `idea.md` + AgentDB entry exactly as Stage 2.5 Contrarian does).
7. Print a one-line summary and the natural next step:
   - `spawn-sibling` → `Sibling idea: <new-slug>. Switch cursor? Y/N`.
   - `refine-active` → `Refined statement captured. Next: /idea-check
     socratic` to re-enter Stage 1.
   - `park` / `none` → `Brainstorm parked. Next: /idea-check scout`.

**Re-entry.** `/idea-check brainstorm` is safe to call multiple times on
the same idea — each session writes a new `brainstorm.md` (overwrites
the prior render; AgentDB key is single per parent). Use when results
from Stage 2 surface unexpected gaps and you want a fresh angle before
committing to evaluate.

## Stage 2 — Scout (近三年)

**Goal:** ground the discussion in real, recent literature.

1. Load the active idea (`registry.load_idea(slug)`). Confirm with the user:
   `Search query default: <slug+statement keywords>. Year range default:
   <last-3-years-inclusive>. Override?` Accept plain-text edits.
2. Primary source — arXiv: call
   `research_assistant.ideas.scout.scout_recent_papers(query, year_range,
   max_results=25)`. This wraps `lit.sourcing.search_arxiv` (real impl) and
   returns `ScoutResult`.
3. Fallback — non-arXiv venues (OSDI, SOSP, NSDI, USENIX ATC, USENIX Security,
   CHI, SIGMOD, VLDB, etc.): if the idea's area tags include any of
   `{sys, sec, db, hci}` and arXiv yielded fewer than ~5 hits in that area,
   invoke Claude's `WebSearch` tool with queries like
   `<venue> <query> last 3 years site:usenix.org OR site:acm.org`. Wrap
   results as additional `PaperRef`s and append to `result.papers`.
4. **Cluster + relation notes** (Claude's reasoning): group papers by sub-topic,
   then for each paper fill `relation_note` with 2–3 sentences:
   `What they did. How it relates to your idea. Why it doesn't subsume yours
   (or does).` Cite by URL + arXiv ID.
4.5. **Gap consolidation** (Claude's reasoning, adapted from
   Orchestra-Research/AI-Research-SKILLs MIT `0-autoresearch-skill`
   Bootstrap step 2). After the per-paper relation notes are written,
   populate `result.gaps` (a `ScoutGaps` instance) with four buckets:
   - `tried` — one bullet per cluster of approaches the last 3 years
     have explored.
   - `untried` — combinations, regimes, or extensions nobody has
     published yet (the inversions / missing intersections).
   - `where_broken` — concrete failure modes documented in the scouted
     papers (table 5 of paper X, §6.3 of paper Y, etc.).
   - `future_work` — pointers from the scouted papers' Discussion
     sections (cite by URL).
   Empty buckets are fine — `render_scout_md` omits them. Aim for 1–4
   bullets per non-empty bucket; this is a triage, not an exhaustive list.
5. Render with `scout.render_scout_md(result)` → write
   `outputs/idea-checks/<slug>/scout.md`.
6. For every paper, also `mcp__claude-flow__memory_store` namespace=`papers`,
   key=`<paper-slug>` so `/paper scout` later can reuse the index.
   Then `mcp__claude-flow__memory_store` namespace=`ideas`,
   key=`<slug>/scout` with `scout.to_agentdb_payload(result)`.
7. `registry.update_idea(slug, status="scouted")`.
8. Show the cluster overview; ask plain text: `覆盖到了吗? 还要我搜哪个方向?`
   — multi-round refine until the user is satisfied.
9. Offer: `要让 /summarize 把某篇做成完整 summary 吗?` (don't auto-invoke).

### Stage 2.5 — Contrarian micro-flow (反其道而行)

**Goal:** after the user has seen what the last-3-years mainstream is doing,
ask whether inverting the dominant assumption could win — and, if so, capture
the inversion as a sibling idea so both framings live alongside each other.

**Auto-triggered** at the end of Stage 2 (right after step 9). Bail by answering
`skip` / `跳过` to Q1. Re-entry on demand via `/idea-check contrarian` (or
`/idea-check contrarian <slug>` for a specific idea).

Build a
`research_assistant.ideas.contrarian.ContrarianTrace(parent_slug=slug,
parent_statement=manifest.statement)`. Append every Q/A with
`contrarian.record_turn(trace, q, a)`.

Q1 — mainstream pattern:
> `最近 3 年这一波 arxiv 工作里最广泛的做法 / 模式是什么? (回答 \`skip\` / \`跳过\` 可以跳过这一步)`

If the answer is `skip` / `跳过`: set `trace.mainstream_pattern = "<skipped>"`,
`mcp__claude-flow__memory_store` namespace=`ideas`, key=`<slug>/contrarian`
with `contrarian.to_agentdb_payload(trace)` (audit only), DO NOT touch
`scout.md`, skip directly to Stage 3.

Q2 — shared assumption:
> `这些做法共同假设了什么?`

Q3 — inversion:
> `如果反过来 — 否定这个假设 — 会变成什么样?`

Q4 — win condition:
> `反过来这条路要赢, 最起码需要什么证据?`

Distill + confirm:
1. Draft a 1–2 sentence contrarian framing grounded in Q3 + Q4; set
   `trace.final_statement`.
2. Show the triple `(proposed sibling slug = <parent>-contrarian, framing)`
   and ask plain text: `要把这个反向框架立成一个 sibling idea 吗? Y / N / 编辑`.
3. On `编辑`: take the user's correction as the new `final_statement`, re-show,
   re-ask.

On `Y` (accept):
1. `trace.accepted = True`.
2. `new = registry.create_variant_idea(parent_slug=slug, suffix="contrarian",
   new_statement=trace.final_statement)`. Sibling slug collisions resolve to
   `<parent>-contrarian-2`, `-3`, … automatically.
3. Write `outputs/idea-checks/<new.slug>/contrarian.md` via
   `contrarian.render_contrarian_md(trace)`.
4. Append `contrarian.render_scout_appendix(trace)` to the parent's
   `outputs/idea-checks/<slug>/scout.md`. **Idempotent:** if the file already
   contains a `## Contrarian framings` section, splice it out (everything from
   that header to either the next `##` header or EOF) and replace it; never
   duplicate.
5. `mcp__claude-flow__memory_store` namespace=`ideas`, key=`<slug>/contrarian`
   with `contrarian.to_agentdb_payload(trace)`.
6. `mcp__claude-flow__memory_store` namespace=`ideas`, key=`<new.slug>` with
   `registry.to_agentdb_payload(new)`.
7. Print: `Sibling idea: <new.slug>. Switch active idea to it? Y/N`. Only
   update `project/idea-context.current` if the user picks Y; default stays on
   the parent.

On `N` (reject): still set `trace.accepted = False`, run steps 4 + 5 above
(scout.md appendix + AgentDB trace mirror); skip step 2 (no sibling created)
and step 6 (no sibling payload).

Then proceed to Stage 3 on whichever idea the cursor points at.

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
   - `registry.update_idea(slug, venue=<picked>, status="venued")`.
   - `mcp__claude-flow__memory_store` namespace=`ideas`, key=`<slug>/venues`
     with `[m.model_dump() for m in matches]` plus `{"picked": <slug>}`.
   - Refresh `project/idea-context.current` to include `venue: <picked>`.

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
3. Render to `outputs/idea-checks/<slug>/lineage.md`.
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
* `research_assistant.ideas.socratic.{SocraticTrace, record_turn, render_socratic_md}`
* `research_assistant.ideas.contrarian.{ContrarianTrace, record_turn, render_contrarian_md, render_scout_appendix, to_agentdb_payload}`
* `research_assistant.ideas.brainstorm.{BrainstormTrace, BrainstormCandidate, BrainstormHandoff, FRAMEWORK_NAMES, record_turn, add_candidate, converge, survivors, render_brainstorm_md, to_agentdb_payload}`
* `research_assistant.ideas.scout.{scout_recent_papers, ScoutGaps, render_scout_md, to_agentdb_payload}`
* `research_assistant.ideas.socratic.{SocraticTrace, Hypothesis, record_turn, render_socratic_md, to_experiment_hypothesis_seed}`
* `research_assistant.ideas.evaluate.{IdeaEvaluation, IdeaRisk, PreRegistration, render_evaluate_md, to_experiment_metrics_seed, VALUE_AXES, FEASIBILITY_AXES}`
* `research_assistant.ideas.venues.{VENUE_REGISTRY, suggest_venues, render_venues_md, VenueMatch}`
* `research_assistant.ideas.knowledge.{KnowledgeIndex, KnowledgeItem, render_knowledge_md, to_agentdb_payload}`
* `research_assistant.ideas.status.{stage_status, render_status_md}`
* `research_assistant.ideas.registry.{IdeaManifest, save_idea, load_idea, update_idea, list_ideas, render_index_md, to_agentdb_payload, reindex_from_disk, create_variant_idea}`
* `research_assistant.lit.sourcing.{PaperRef, search_arxiv}`
