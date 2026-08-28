---
name: idea-check
description: Research-idea validator — decide whether the problem behind an idea is real, general, explainable, and predictive. Five hard gates (failure-case → problem-standalone → mechanism → predictions → minimal-experiment); scout / brainstorm / contrarian / assumptions / evaluate / venues / knowledge are evidence services. Retains horizontal-matrix and vertical-lineage legacy modes.
---

# /idea-check

Invoke the `idea-validate` skill (`.claude/skills/idea-validate/SKILL.md`).

## Args (`$ARGUMENTS`)

First token may be a subcommand; the rest is its argument. `--force` is a
trailing flag accepted by the five gate subcommands only.

### Gates — the progress axis (order is enforced)

| Form | Meaning |
|---|---|
| `/idea-check "<free-text>"` | Capture the idea (lightweight Socratic) then go straight into Gate 1. |
| `/idea-check failure-case [--force]` | Gate 1 — 现有方法到底在什么情况下真的会失效（具体、可复现）。 |
| `/idea-check problem-standalone [--force]` | Gate 2 — 删掉你的方法，这个问题本身还值得研究吗。 |
| `/idea-check mechanism [--force]` | Gate 3 — 原来的方法错在哪、真正起作用的因素是什么。 |
| `/idea-check predictions [--force]` | Gate 4 — 机制能否推出 ≥2 条带低成本验证方式的预测。 |
| `/idea-check minimal-experiment [--force]` | Gate 5 — 最小实验 + pre-registration，之后才允许大规模跑。 |
| `/idea-check gates` | Print the decision ledger (`gates.md`), read-only. |
| `/idea-check handoff` | Hand off to `/paper` — refused (with the blocking gate) unless all five cleared. |

An uncleared gate **hard-blocks** every later gate and `handoff`. `--force`
records the real verdict, lets the pipeline continue, and leaves the override
visible in `gates.md`, `status.md`, `_index.md`, and the manifest's
`forced_gates`.

### Services — evidence, not progress (run any time)

| Form | Meaning |
|---|---|
| `/idea-check socratic` | Re-enter capture; edit the statement / hypothesis tree. |
| `/idea-check brainstorm [<situation>]` | Fresh angles when a gate is red: 2–3 ideation frameworks, diverge → converge → refine. May spawn a sibling idea. |
| `/idea-check scout` | Last-3-years arXiv + WebSearch fallback, 4-bucket gaps (tried / untried / where-broken / future-work). Main evidence source for Gates 1–2. |
| `/idea-check contrarian [<slug>]` | 反其道而行 4-Q micro-flow; may spawn a `-contrarian` sibling. Serves Gate 2. |
| `/idea-check assumptions [<paper\|slug>]` | Mine a paper's unstated assumptions; a generally-false one spawns a new idea at Gate 1. Serves Gate 3. |
| `/idea-check evaluate` | 10-axis value/feasibility scores + risks + pre-registration. Evidence panel for Gates 3–5 — no longer a gate itself. |
| `/idea-check venues` | Rank target venues. Run at least once before `handoff`. |
| `/idea-check knowledge` | Brain-library study index. |
| `/idea-check 2paper [<slug>]` | Story packaging via `.claude/skills/academic-story-packaging/SKILL.md`. |

### Always available

| Form | Meaning |
|---|---|
| `/idea-check` (no args) | Print `_index.md` + the active idea's gate board. |
| `/idea-check status` | Print the gate board + service checklist + forced warnings. |
| `/idea-check list` | Print `outputs/idea-checks/_index.md`. |
| `/idea-check show <slug>` | Print one idea's manifest + board. |
| `/idea-check horizontal <free-text>` | Legacy — related-work matrix. |
| `/idea-check vertical <slug>` | Legacy — lineage trace. |

## Cursor

The active idea lives in AgentDB `project/idea-context.current`. Every gate and
service subcommand reads it on entry; capture writes it. `list` and
`show <slug>` don't need it.

## Action

1. Load `.claude/skills/idea-validate/SKILL.md`.
2. Read the cursor (`mcp__claude-flow__memory_retrieve` namespace=`project`,
   key=`idea-context.current`) and the gate ledger (`ideas/<slug>/gates`,
   falling back to `gates.md`).
3. For a gate subcommand: run `gates.can_enter(ledger, gate)` **first**. If
   blocked, print the blocking gate + what it's missing + how to fix it, and
   stop. Do not walk the user through later gates.
4. Follow the matching section of the skill (details in
   `references/gate-workflow.md`) — multi-turn, plain text, one question at a
   time, never `AskUserQuestion`. Exception: `2paper` dispatches to
   `.claude/skills/academic-story-packaging/SKILL.md`.
5. Every cleared gate MUST write the ledger (`gates.md` + AgentDB
   `ideas/<slug>/gates`) AND call `registry.update_idea(slug, status=...)` so
   the manifest, `_index.md`, and the AgentDB payload stay in sync. Forced
   gates additionally append to `forced_gates`.
6. End with the three-part output: 关卡状态 / 最关键的一个追问 / 下一步行动.

## Where artifacts land

```
outputs/idea-checks/
  _index.md                       # vault registry (auto-rebuilt)
  <slug>/
    idea.md                       # YAML manifest — source of truth on disk
    gates.md                      # gate decision ledger (the progress axis)
    status.md                     # gate board + service checklist
    socratic.md
    brainstorm.md    (service, optional)
    scout.md         (service, optional)
    contrarian.md    (service, optional)
    assumptions.md   (service, optional)
    evaluate.md      (service, optional)
    venues.md        (service, optional)
    knowledge.md     (service, optional)
    story.md         (/idea-check 2paper)
    horizontal.md    (legacy)
    lineage.md       (legacy)
```

AgentDB mirrors: `ideas/<slug>`, `ideas/<slug>/gates`, and
`ideas/<slug>/{socratic,brainstorm,scout,contrarian,assumptions,evaluation,venues,knowledge,story,horizontal,lineage}`.
