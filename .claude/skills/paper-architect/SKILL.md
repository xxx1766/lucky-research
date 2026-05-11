---
name: paper-architect
description: Multi-stage paper output flow — venue setup, direction discussion, paper scouting, problem focusing, motivation experiment design, section drafting. Organizes everything under outputs/papers/<venue>/<direction>/. Use when the user is starting or working on a paper for a specific venue. Triggered by /paper.
---

# paper-architect

> **STATUS**: stub. Workflow contracts only — real bodies land stage-by-stage.

## Mental model

A paper lives at `outputs/papers/<venue>/<direction>/`. The flow has seven stages, each
backed by one subcommand of `/paper`. Stages can be revisited in any order, but later
stages assume earlier ones are non-empty.

```
venue → direction → scout → focus → motivate → write ↔ experiments
                                                 │
                                                 └─ status snapshot any time
```

The "current paper" is just a `(venue, direction)` tuple stored in AgentDB
`project/paper-context`. Every stage reads it; the `venue` and `direction` subcommands
write it.

## Directory layout this skill owns

```
outputs/papers/<venue>/
  _venue.md                  论文特点和要求
  <direction>/
    expert.md                小方向专家角色
    related-papers/<slug>.md 对比论文
    focused-problem.md       聚焦问题
    experiments/             对比实验和benchmark
      motivation.md
      benchmark.md
      results/
    outline.md               写作思路和架构
    sections/                drafted prose (intro.md, method.md, ...)
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

## Stage 2 — `/paper direction <slug>`

**Inputs**
- `<slug>` (e.g. `diffusion-finetune`).
- Current venue context.

**Workflow**
1. Invoke the `past-work-historian` agent (via the Agent tool) to surface relevant
   prior work from `project/past-work/`.
2. Discuss direction with the user — what's the angle, why this venue, what would
   make it land. Multi-turn conversation, not single-shot.
3. Draft `expert.md` (voice, taste, anti-patterns, prior takes). Show + edit.
4. Create `outputs/papers/<venue>/<direction>/{expert.md, status.md}`.
5. Update `project/paper-context.current` to include the direction slug.

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

## Stage 4 — `/paper focus`

**Workflow**
1. Read `<direction>/related-papers/*.md` + `expert.md`.
2. Interactive narrowing — ask the user three questions:
   - what's the specific gap?
   - why does it matter now?
   - what's the smallest empirical claim that would close it?
3. Write `<direction>/focused-problem.md`. Sections: Problem, Gap claim, Why now,
   Smallest empirical claim, Out-of-scope.

## Stage 5 — `/paper motivate`

**Workflow**
1. Read `focused-problem.md` + `related-papers/`.
2. Design two artifacts:
   - `experiments/motivation.md` — the small experiment a reviewer would expect to
     see to believe the problem is real.
   - `experiments/benchmark.md` — main comparison + ablations the paper will run.
3. List datasets, metrics, baselines, expected outcome ranges.

## Stage 6 — `/paper write [section]`

**Workflow**
- If no section given, generate `outline.md`: section-by-section plan grounded in
  `expert.md` + `focused-problem.md` + `experiments/`.
- If section given (`intro` / `method` / `results` / `discussion` / etc.):
  1. Read `expert.md`, `focused-problem.md`, `experiments/*`, `related-papers/`.
  2. Draft `<direction>/sections/<section>.md`. Use `[@cite:<paper-slug>]`
     placeholders that `ref-manager` later resolves.
  3. Append a "TODO" footer listing experiments still needed to support the prose.

## Stage 7 — `/paper status`

**Workflow**
1. Walk `outputs/papers/*/` for venues.
2. For each `(venue, direction)`, call `research_assistant.papers.stage_status`.
3. Print + persist `<direction>/status.md` with a checkmark line per stage.

## Outputs

Every artifact named above lives under `outputs/papers/<venue>/<direction>/`. AgentDB
side: `project/paper-context` (cursor), `papers/<slug>` (scouted papers — written by
lit-summarize), `drafts/<venue>/<direction>` (lightweight snapshot of the outline so the
mentor can detect drift).

## Memory keys touched

- `project/paper-context` — read/write (cursor).
- `project/past-work/*` — read (via `past-work-historian`).
- `papers/<slug>` — write (during scout).
- `drafts/<venue>/<direction>` — write (during write).

## Open TODOs

- [ ] Real `search_openreview` + `search_arxiv` implementations.
- [ ] Section-template variants per venue family (NLP / CV / systems).
- [ ] Coupling between `experiments/results/` and external trackers (deferred).
- [ ] `/mentor add-past-work` UX.
