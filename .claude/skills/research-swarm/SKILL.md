---
name: research-swarm
description: OPTIONAL ruflo accelerator — parallelize paper scouting with a ruflo swarm of researcher agents, writing the SAME artifacts as `/paper scout` (related-papers/<slug>.md + AgentDB papers/<slug>). Use ONLY when ruflo swarm tools are available; degrades gracefully to suggesting `/paper scout` when they are not. Triggered by /scout-swarm.
---

# research-swarm

A **purely additive** accelerator. It does not replace or modify any existing skill.
It speeds up the `scout` stage of `/paper` by fanning a topic across several `researcher`
agents in parallel, then writes their findings into the **exact same place** `/paper scout`
writes — so `/paper focus`, `/paper write`, and `/paper status` consume the results with
zero awareness that a swarm produced them.

> **Dependency boundary.** This skill needs the ruflo / claude-flow MCP swarm tools
> (`swarm_init`, `agent_spawn`) and the Claude Code `Agent` tool. Collaborators without
> ruflo simply never invoke `/scout-swarm`; every other skill keeps working unchanged.
> See `docs/ruflo-integration.md` for the full picture.

## Contract with `/paper scout` (do not break)

This skill MUST produce artifacts identical in shape to paper-architect Stage 3:

- One markdown file per paper at `<direction>/related-papers/<slug>.md`, using the
  `lit-summarize` structure (problem / method / results / contribution / limitations).
- One AgentDB entry per paper: `memory_store(namespace="papers", key="<slug>")`.
- Resolve the direction dir via `research_assistant.papers.direction_path(venue_slug, direction_slug)`
  — never hand-build paths.

## Workflow

### Step 0 — Probe for swarm capability (graceful degradation)

Run `ToolSearch("swarm_init agent_spawn")`. If the swarm tools are **not** available
(no ruflo), STOP and print exactly:

```
⚠ ruflo swarm tools not detected — this is the optional accelerator.
  Run `/paper scout` for the built-in sequential scout (no ruflo required).
```

Do not error, do not retry, do not fall through. This is the expected path for users
without ruflo.

### Step 1 — Resolve scope

1. Read the cursor: `mcp__claude-flow__memory_retrieve(namespace="project", key="paper-context.current")` (same shape `/paper venue` and `/paper direction` write).
2. If a `(venue, direction)` cursor exists, use it. Otherwise ask the user for a venue +
   direction (or a free-form topic) in plain text, and set the cursor via
   `/paper venue` / `/paper direction` first if they want persistence.
3. Resolve `direction_dir = research_assistant.papers.direction_path(venue, direction)`.
4. Gather direction keywords from `expert.md` (if present) or ask the user.

### Step 2 — Decompose the topic into N sub-areas

Split the direction into 3–6 distinct sub-areas (e.g. by method family, by application,
by baseline lineage). Each sub-area becomes one researcher agent's beat. Keep N ≤ 6 for
tight coordination (per the repo's swarm anti-drift rules).

### Step 3 — Spawn the swarm (ONE message)

In a **single message**, call:

1. `swarm_init` with `topology=hierarchical`, `maxAgents=N` (6–8 cap), `strategy=specialized`.
2. N `Agent` calls (`subagent_type: researcher`, `run_in_background: true`), each with:
   - Its assigned sub-area + the shared direction keywords.
   - Instructions to call `research_assistant.lit.sourcing.search_for_direction(venue, keywords)`,
     summarize each `PaperRef` in the `lit-summarize` structure, and write
     `<direction>/related-papers/<slug>.md`.
   - Instructions to `memory_store(namespace="papers", key="<slug>")` for each paper.
   - A reminder NOT to touch any other skill's artifacts.

After spawning, **STOP** — do not poll agent status. Trust agents to return.

### Step 4 — Aggregate

When all agents return:

1. De-duplicate by slug (two agents may surface the same paper — keep one file).
2. Print a comparison table of all scouted papers (title · sub-area · key contribution).
3. Print `research_assistant.papers.render_progress_footer(venue, direction, stage_status(direction_dir))`
   so the user sees the same progress board `/paper scout` would show.
4. Tell the user to continue with `/paper focus`.

## Non-goals

- Does NOT modify `paper-architect`, `lit-summarize`, or any other skill.
- Does NOT introduce new AgentDB namespaces — only the existing `papers/`.
- Does NOT add new Python helpers — reuses `research_assistant.papers` and
  `research_assistant.lit.sourcing`.

## Memory keys touched

- `project` — read cursor (key `paper-context.current`).
- `papers/<slug>` — write (one per scouted paper, same key `/paper scout` uses).
