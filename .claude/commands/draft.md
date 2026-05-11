---
name: draft
description: Outline a paper or draft a specific section, using project context + validated idea + related-work summaries
---

# /draft

Invoke the `paper-architect` skill.

## Args

- `$ARGUMENTS` — one of:
  - `outline: <paper title or idea-slug>` — generate the full outline.
  - `section: <paper-slug> <section-name>` — draft a single section.

## Action

1. Load the `paper-architect` skill (`.claude/skills/paper-architect/SKILL.md`).
2. Pull context from AgentDB (`project/`, `ideas/`, `papers/`).
3. Write outputs under `outputs/drafts/<paper-slug>/`.
