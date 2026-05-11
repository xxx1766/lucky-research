---
name: idea-check
description: Validate a research idea via horizontal comparison or vertical lineage trace
---

# /idea-check

Invoke the `idea-validate` skill.

## Args

- `$ARGUMENTS` — free-text idea description. May be prefixed:
  - `horizontal: <idea>` — build a related-work matrix across N papers.
  - `vertical: <idea or paper-slug>` — trace lineage over time.
  - (no prefix) — ask the user which mode to run.

## Action

1. Load the `idea-validate` skill (`.claude/skills/idea-validate/SKILL.md`).
2. Follow the Workflow for the chosen mode.
3. Write the result to `outputs/idea-checks/` and index in AgentDB `ideas/`.
