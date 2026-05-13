---
name: past-work
description: Curate past projects — list, add, or sync entries under inputs/past-work/ so the past-work-historian agent can recall them
---

# /past-work

Invoke the `past-work-historian` agent in the mode matching `$ARGUMENTS`.

## Subcommands

- `/past-work` or `/past-work list` — list entries currently in `inputs/past-work/`
  (status / year / venue per row).
- `/past-work add` — interactive capture; Claude prompts for the fields, writes
  `inputs/past-work/<slug>.md` from `docs/past-work-template.md`, and indexes the
  entry in AgentDB `project/past-work/<slug>`.
- `/past-work sync` — re-walk `inputs/past-work/*.md` and upsert each entry into
  AgentDB.

## Action

1. Load the `past-work-historian` agent (`.claude/agents/past-work-historian.md`).
2. Run the matching workflow (Recall / Add / Sync) using helpers from
   `research_assistant.mentor.past_work`.
3. Source of truth on disk: `inputs/past-work/*.md` (gitignored, per-user).
   Shared template: `docs/past-work-template.md`.
