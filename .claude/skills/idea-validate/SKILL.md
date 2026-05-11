---
name: idea-validate
description: Validate a research idea by (a) horizontal comparison — build a related-work matrix across N papers on fixed axes (problem, method, dataset, metric, gap), or (b) vertical deep-dive — trace the idea's lineage over time. Use when the user says "is this idea novel", "compare these N papers", "where does this idea come from".
---

# idea-validate

> **STATUS**: stub. Frontmatter + section headers only. Real skill body TBD.

## When to use

- User asks "is this idea novel / already done / a delta from X?"
- User wants a horizontal compare of related work.
- User wants the lineage of a specific idea over time (vertical).

## Workflow

### Horizontal mode

1. Pull candidate papers from `outputs/summaries/` + AgentDB `papers/` namespace via
   `mcp__claude-flow__memory_search` with the idea description.
2. Define the comparison axes (default: problem, method, dataset, metric, gap-they-claim).
3. Build a markdown table; Claude fills cells from each paper's summary.
4. Write `outputs/idea-checks/<idea-slug>-horizontal.md`.
5. Store the matrix as an AgentDB entry in namespace `ideas/` with the idea slug.

### Vertical mode

1. Seed = one paper or one stated idea.
2. Walk the citation/related-work graph using summaries already in `papers/`.
3. Order chronologically; annotate each step with "what new claim does this add".
4. Write `outputs/idea-checks/<idea-slug>-lineage.md`.
5. Store lineage in AgentDB `ideas/<idea-slug>/lineage`.

## Outputs

- `outputs/idea-checks/<idea-slug>-horizontal.md` or `-lineage.md`.
- AgentDB entry under namespace `ideas/`.

## Memory keys touched

- `papers/*` — read (semantic search for related papers)
- `ideas/<idea-slug>` — write
- `ideas/<idea-slug>/lineage` — write (vertical mode)

## Open TODOs before this skill is real

- [ ] Decide axes per venue family (NLP / CV / systems / theory).
- [ ] Decide how to bound the lineage walk (depth limit / year window).
