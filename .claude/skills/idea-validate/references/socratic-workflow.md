# Stage 1 — Socratic workflow detail

Load when actually running Socratic. Main SKILL has the high-level goal and
contract; this file has the per-round prompts and the persistence step.

## Goal

Distill a free-form idea into one persisted manifest with a 1–2 sentence
statement, area tags, and a slug.

## Constraint

Plain-text questions, **one turn at a time** (per `feedback_decision_ui`
memory — never use `AskUserQuestion` for research picks). Build a
`research_assistant.ideas.socratic.SocraticTrace`; append every Q/A with
`record_turn(trace, q, a)`.

## Rounds

### Round 1 — problem
> `用一句话说说你想解决什么问题?`

### Round 2 — why now
> `为什么这个问题现在值得做? 谁会从答案里受益?`

### Round 3 — gap + claim (hypothesis tree)
> `你认为现有方法的关键不足是什么? 你假设的突破点在哪儿?`

This round collects a **hypothesis tree** rather than a single statement
— adapted from Orchestra-Research/AI-Research-SKILLs (MIT)
`0-autoresearch-skill` Bootstrap step 3. The model captures:

- The root hypothesis `H1` (the user's distilled claim).
- Optional sub-hypotheses `H1.1`, `H1.2` — only when the user naturally
  spawns follow-ups ("and if H1 holds, then X should also hold").
- Optional independent roots `H2`, `H3` — only when the user explicitly
  raises a second claim worth testing in parallel.
- For each hypothesis: a one-line `prediction` (what observation would
  confirm or falsify it). Predictions stay optional — if the user can't
  yet name one, leave blank rather than fabricate.

**Persist** as `socratic.Hypothesis` instances appended to
`trace.hypotheses`. The id convention is dotted: `H1.1` is a child of
`H1`; `socratic.Hypothesis` derives `parent` and `depth` from the id
(don't store parent twice). Keep the tree shallow — `H1.1.1` typically
means "this is a new root, lift it to H2".

**Downstream:** `/experiment design` Stage 3 step 2 reads
`ideas/<current>/socratic` via `socratic.to_experiment_hypothesis_seed(trace)`
and pre-fills the design's `## Hypothesis` section.

### Round 4 — failure mode
> `如果失败,最可能的原因是什么?`

### Round 5 — past-work recall (optional but recommended)
> Invoke the `past-work-historian` agent via the `Agent` tool to surface
> relevant prior projects from `project/past-work/`. If matches come
> back, ask: `这跟你之前的 <prior-title> 有什么继承或区别?` — record
> one or two turn into `trace.past_work_refs` (use `[[prior-slug]]` form).

### Round 6 — distill + confirm

1. Draft a 1–2 sentence idea statement; pick area tags (subset of
   `{ml, nlp, cv, sys, db, sec, theory, hci, ir}`); generate the slug
   via `research_assistant.ideas.slug.slugify(statement)`. Show the user
   the triple `(slug, area_tags, statement)`.
2. Ask plain text: `这个表述对吗? Y / 编辑后重写`. If the user revises,
   set `trace.idea_statement` to the corrected text and re-derive the
   slug **only if the user explicitly asks**.

## On confirm

1. Build `manifest = IdeaManifest(slug, created=today, updated=today,
   statement, area_tags, body=<one-paragraph context>)`.
2. `research_assistant.ideas.registry.save_idea(manifest)` — writes
   `outputs/idea-checks/<slug>/idea.md` AND refreshes `_index.md`.
3. `mcp__claude-flow__memory_store` namespace=`ideas`, key=`<slug>` with
   `registry.to_agentdb_payload(manifest)`.
4. Write `outputs/idea-checks/<slug>/socratic.md` via
   `socratic.render_socratic_md(trace)`.
5. `mcp__claude-flow__memory_store` namespace=`ideas`,
   key=`<slug>/socratic` with `trace.model_dump()`.
6. `mcp__claude-flow__memory_store` namespace=`project`,
   key=`idea-context.current` with `{"slug": <slug>, "area_tags": [...],
   "stage": "captured"}`.
7. Tell the user: `Idea captured at outputs/idea-checks/<slug>/. Run
   /idea-check scout to find recent papers.` Then ask: `要现在就继续
   scout 吗? Y/N`.

## Idle exit

If the user stops here, the idea is durable. They can resume any time via
`/idea-check show <slug>`.
