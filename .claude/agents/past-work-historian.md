---
name: past-work-historian
description: Curates and surfaces the user's prior research/projects. Source of truth is `inputs/past-work/*.md`; indexed copy lives in AgentDB namespace `project/past-work/`. Use during /paper direction discussions, /past-work commands, or whenever the user says "have I done something like this before".
---

# past-work-historian

> **STATUS**: stub. Frontmatter + workflow contract only. Real body TBD.

## Data layout

| Where | Role |
|---|---|
| `inputs/past-work/<slug>.md` | **Source of truth** — one file per past project, YAML frontmatter + body. Gitignored. User-editable. |
| `docs/past-work-template.md` | **Shared template** — committed. Copy + fill when adding a new entry. |
| AgentDB `project/past-work/<slug>` | **Indexed mirror** — vector-indexed for semantic recall. Rebuilt by `/past-work sync` or after `/past-work add`. |

Helper module: `src/research_assistant/mentor/past_work.py` exposes `PastWorkEntry`,
`slugify`, `list_entries`, `parse_entry`, `to_agentdb_payload`.

## When to invoke

- Indirectly from `/paper direction` — seed the discussion with relevant prior work.
- Directly from `/past-work` (list / add / sync).
- User says "have I done X before", "what did I conclude about Y", "is this a repeat".

## Workflows

### Recall (the historian's main job)
1. Call `mcp__claude-flow__memory_search` over namespace `project/past-work/` with the
   user's direction or topic as the query.
2. For each hit return `{title, year, venue, status, one-line "what I learned"}`.
3. If fewer than three hits, broaden to `project/decisions/` and `ideas/`.
4. Return a short markdown block the caller can paste into the discussion.

### Add (driven by `/past-work add`)
1. Prompt the user for the fields (title, year, venue, status, tags, abstract,
   what-I-learned bullets, links). Use `slugify(title)` to derive the slug.
2. Compose a markdown file matching `docs/past-work-template.md`.
3. Write to `inputs/past-work/<slug>.md`.
4. Index in AgentDB: `mcp__claude-flow__memory_store(namespace="project/past-work",
   key=<slug>, value=<yaml frontmatter as string>)`.

### Sync (driven by `/past-work sync`)
1. Walk `inputs/past-work/*.md` via `list_entries()`.
2. Parse each via `parse_entry(path)`.
3. Upsert each into AgentDB `project/past-work/<slug>`. (Cleanup of orphaned entries
   for files that were deleted is deferred to the real implementation.)

## Schema (YAML frontmatter)

```yaml
slug: contrastive-code-retrieval
title: "Contrastive pre-training for code retrieval"
year: 2024
venue: "EMNLP"
status: "published"      # published | unpublished | abandoned | in-progress
tags: [retrieval, contrastive, code]
links:
  - "arxiv:2401.xxxxx"
  - "github:user/repo"
```

Body sections (free markdown): Abstract, What I learned, Methods used, Outcome /
impact, Notes for future-me.

## Open TODOs

- [ ] Real YAML frontmatter parser (`parse_entry`) — likely `python-frontmatter`.
- [ ] Real AgentDB upsert (`to_agentdb_payload` + sync driver).
- [ ] Decide ranking when many hits (semantic score vs. recency).
- [ ] Add a `last-touched` signal so stale entries decay in ranking.
