# Stage 1.5 — Brainstorm workflow detail

Load when actually running the brainstorm escape hatch. Main SKILL has the
high-level trigger (Socratic stalls, idea feels incremental, two-sentence
test fails); this file has the per-phase flow.

The 11 ideation frameworks (`F1`…`F11`), the Selection Guide table, and the
convergence filters live in **`ideation-frameworks.md`** — load that
**alongside** this file as the prompt prelude. Adapted from
Orchestra-Research/AI-Research-SKILLs (MIT) `21-research-ideation/`.

## Workflow

### 1. Resolve scope

Require an active idea cursor; refuse with `Run /idea-check "<your idea>"
first` if absent. Load the manifest via `registry.load_idea(slug)`.

### 2. Phase 1 — diagnose

Ask the user one sentence on why they're reaching for brainstorm (plain
text — no `AskUserQuestion`):

> `什么让你卡住了？(参考 Selection Guide 的左列)`

Match the answer against the Selection Guide table in
`ideation-frameworks.md` and pick **2–3 framework codes**. Build a
`BrainstormTrace(parent_slug, parent_statement, user_situation,
frameworks=[<codes>])`.

### 3. Phase 2 — diverge (3–6 turns per framework, total ≤ 12 turns)

For each chosen framework, run a Q→A→Q sequence using the framework's
workflow from the reference file. Append every turn with
`brainstorm.record_turn(trace, framework, q, a)`. Capture raw ideas as
`brainstorm.add_candidate(trace, framework, pitch)` — aim for 10–20
raw candidates total. **Do not filter yet.**

### 4. Phase 3 — converge

Show the user the candidate list. Apply the filters from the reference
file (explain-it test / problem-first / simplicity / stakeholder check /
feasibility). Plain-text prompt:

> `留哪些？(e.g. "1, 3, 5" or "all" or "none")`

Call `brainstorm.converge(trace, keep=[<indices>], kill_reasons={...})`
with one-line reasons for the killed candidates.

### 5. Phase 4 — refine

For the 1–3 survivors, run the **two-sentence test (F10)** and ask the
user what to do:

- **`spawn-sibling`** → call `registry.create_variant_idea(
    parent_slug=<active>, suffix=<sibling_suffix>,
    new_statement=<two-sentence pitch>)`. Update `trace.handoff =
    BrainstormHandoff(kind="spawn-sibling", statement=<pitch>,
    sibling_suffix=<suffix>)`. Offer to switch the cursor to the new
    slug (Y/N) — default keeps cursor on parent.
- **`refine-active`** → store the refined statement in
    `trace.handoff.statement` and tell the user to run
    `/idea-check socratic` to re-enter Stage 1 with the new framing.
- **`park`** → keep the trace but take no follow-up action. Useful when
    the survivors are worth remembering for later.
- **`none`** → user ended early; the trace records as far as Phase 3.

### 6. Save

- Write `outputs/idea-checks/<slug>/brainstorm.md` via
  `brainstorm.render_brainstorm_md(trace)`.
- `mcp__claude-flow__memory_store` namespace=`ideas`,
  key=`<slug>/brainstorm` with `brainstorm.to_agentdb_payload(trace)`.
- If `kind == "spawn-sibling"`, also write the sibling's own files (the
  helper does the slug allocation; the skill writes the sibling
  `idea.md` + AgentDB entry exactly as Stage 2.5 Contrarian does).

### 7. Print summary + next step

- `spawn-sibling` → `Sibling idea: <new-slug>. Switch cursor? Y/N`.
- `refine-active` → `Refined statement captured. Next: /idea-check
  socratic` to re-enter Stage 1.
- `park` / `none` → `Brainstorm parked. Next: /idea-check scout`.

## Re-entry

`/idea-check brainstorm` is safe to call multiple times on the same idea
— each session writes a new `brainstorm.md` (overwrites the prior
render; AgentDB key is single per parent). Use when results from Stage 2
surface unexpected gaps and you want a fresh angle before committing to
evaluate.
