---
name: paper
description: Multi-stage paper-output workflow — venue, direction, scout, focus, motivate, write, status
---

# /paper

Invoke the `paper-architect` skill in the stage matching `$ARGUMENTS`.

## Subcommands

- `/paper venue <slug>` — create or edit the venue folder + `_venue.md` (论文特点和要求).
- `/paper direction <slug>` — open or scope a sub-direction under the current venue.
  Past-work-historian agent seeds the discussion; Claude drafts a starter `expert.md`.
- `/paper scout` — source related papers from the venue + arXiv into the current
  direction's `related-papers/`.
- `/paper focus` — narrow to a focused problem; write `focused-problem.md`.
- `/paper motivate` — design motivation experiments + benchmark plan.
- `/paper write [section]` — draft the outline or a specific section.
- `/paper status` — report current stage for every venue/direction.

## Action

1. Load the `paper-architect` skill (`.claude/skills/paper-architect/SKILL.md`).
2. Parse `$ARGUMENTS` into `<subcommand> <args>`; run the matching workflow stage.
3. Read + update the venue/direction context in AgentDB `project/paper-context`.
4. Write artifacts under `outputs/papers/<venue>/<direction>/`.
