---
name: mentor
description: Research mentor check-in — compare recent activity against stated goals and surface path corrections
---

# /mentor

Invoke the `research-mentor` skill.

## Args

- `$ARGUMENTS` — one of:
  - empty — run a weekly check-in.
  - `set-goals` — interactively (re)write `project/goals` in AgentDB.
  - `retro: <since-date>` — generate a retro since the given date.

## Action

1. Load the `research-mentor` skill (`.claude/skills/research-mentor/SKILL.md`).
2. Run the matching workflow.
3. Write the check-in/retro to `outputs/mentor/` and AgentDB `project/checkins/`.
