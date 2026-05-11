---
name: past-work-historian
description: Surfaces the user's prior research (papers, projects, takes) when discussing a new direction. Reads AgentDB namespace `project/past-work/` and returns relevant past work with a one-line rationale per match. Use during /paper direction discussions or whenever the user says "have I done something like this before".
---

# past-work-historian

> **STATUS**: stub. Frontmatter + workflow contract only. Real body TBD.

## When to invoke

- `/paper direction` discussion — seed the conversation with relevant prior work.
- User says "have I done X before", "what did I conclude about Y", "is this a repeat".

## What it does

1. Call `mcp__claude-flow__memory_search` over namespace `project/past-work/` with the
   user's stated direction or topic as the query.
2. For each hit, return: `{title, year, venue, one-line "what I learned"}`.
3. If fewer than three hits, broaden the search to `project/decisions/` and `ideas/`.
4. Return a short markdown block the caller can paste into the discussion.

## Data shape (AgentDB `project/past-work/<slug>`)

```yaml
title: "Contrastive pre-training for code retrieval"
year: 2024
venue: "EMNLP"
abstract: "..."
what-i-learned: "Bigger batches matter more than longer training for this task."
links:
  - "arxiv:2401.xxxxx"
  - "github:user/repo"
```

## Seeding past work

Until `/mentor add-past-work` lands, users seed entries directly:

```
mcp__claude-flow__memory_store(
  namespace="project/past-work",
  key="<slug>",
  value="<yaml block above>"
)
```

## Open TODOs

- [ ] Decide ranking when many hits (semantic score vs. recency).
- [ ] Add a `last-touched` field so stale work decays.
