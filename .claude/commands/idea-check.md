---
name: idea-check
description: Socratic research-direction tool — find a paper direction by Q&A, scout last 3 years, evaluate, suggest venues, emit a brain-library index, hand off to /paper. Also retains horizontal-matrix and vertical-lineage legacy modes.
---

# /idea-check

Invoke the `idea-validate` skill (`.claude/skills/idea-validate/SKILL.md`).

## Args (`$ARGUMENTS`)

The first token may be a subcommand; anything after it is the argument.

| Form | Meaning |
|---|---|
| `/idea-check` (no args) | Print `_index.md` (the vault) + status of the active idea, if any. |
| `/idea-check "<free-text>"` | Start Stage 1 (Socratic) for a new idea. Walks through subsequent stages with plain-text confirmations between each. |
| `/idea-check socratic` | Re-enter Stage 1 for the active idea (refine the statement). |
| `/idea-check scout` | Stage 2 — last-3-years arXiv + WebSearch fallback. |
| `/idea-check evaluate` | Stage 3 — value + feasibility rubric. |
| `/idea-check venues` | Stage 4 — suggest target venues. |
| `/idea-check knowledge` | Stage 5 — brain-library index. |
| `/idea-check handoff` | Stage 6 — confirm + invoke `/paper`. |
| `/idea-check status` | Print the 6-stage checkbox for the active idea. |
| `/idea-check list` | Print the global registry (`outputs/idea-checks/_index.md`). |
| `/idea-check show <slug>` | Print the manifest + status board for one idea. |
| `/idea-check horizontal: <free-text>` | Legacy mode — related-work matrix. |
| `/idea-check vertical: <slug>` | Legacy mode — lineage trace. |

## Cursor

The "active idea" is tracked in AgentDB `project/idea-context.current`. Every
stage-bearing subcommand reads it on entry; Stage 1 writes it. `list` and
`show <slug>` do not require an active cursor.

## Action

1. Load `.claude/skills/idea-validate/SKILL.md`.
2. Read the cursor (`mcp__claude-flow__memory_retrieve` namespace=`project`,
   key=`idea-context.current`).
3. Dispatch on the subcommand. Follow the matching stage section of the skill
   exactly — multi-turn, plain text, no `AskUserQuestion`.
4. Every state-changing stage MUST call `registry.update_idea(slug, ...)` so the
   on-disk manifest, the global `_index.md`, and the AgentDB payload stay in
   sync.
5. End with the next-step hint shown by the skill (e.g.
   `Next: /idea-check scout`).

## Where artifacts land

```
outputs/idea-checks/
  _index.md                       # vault registry (auto-rebuilt)
  <slug>/
    idea.md                       # YAML manifest — source of truth on disk
    socratic.md
    scout.md
    evaluate.md
    venues.md
    knowledge.md
    status.md
    horizontal.md   (legacy)
    lineage.md      (legacy)
```

AgentDB mirrors: `ideas/<slug>`, `ideas/<slug>/{socratic,scout,evaluation,venues,knowledge,horizontal,lineage}`.
