---
name: summarize
description: Summarize papers under `inputs/papers/` (or a provided arXiv URL) into structured markdown and index in AgentDB
---

# /summarize

Invoke the `lit-summarize` skill.

## Args

- `$ARGUMENTS` — optional. May be an arXiv URL/ID, a DOI, or a specific PDF path.
  If empty, summarize every paper under `inputs/papers/` that isn't already in
  `outputs/summaries/`.

## Action

1. Load the `lit-summarize` skill (`.claude/skills/lit-summarize/SKILL.md`).
2. Follow its Workflow section against `$ARGUMENTS`.
3. Report each new summary path + its AgentDB key when done.
