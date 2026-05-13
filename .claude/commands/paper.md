---
name: paper
description: Multi-stage paper-output workflow — venue, direction, scout, focus, motivate, write, render, status
---

# /paper

Invoke the `paper-architect` skill in the stage matching `$ARGUMENTS`.

## Subcommands

- `/paper venue <slug>` — create or edit the venue folder + `_venue.md` (论文特点和要求).
- `/paper direction <slug>` — open or scope a sub-direction under the current venue.
  Past-work-historian agent seeds the discussion; Claude drafts a starter `expert.md`
  and registers an optional `code_repo:` pointer to the experiment-code GitHub repo.
- `/paper scout` — source related papers from the venue + arXiv into the current
  direction's `related-papers/`.
- `/paper focus` — narrow to a focused problem; write `focused-problem.md`.
- `/paper motivate` — design motivation experiments + benchmark plan.
- `/paper write [section]` — draft the outline (Markdown) or a specific section
  (LaTeX `.tex`). Auto-renders `main.pdf` at the end of each section write.
- `/paper render` — re-render `main.pdf` from the current direction without writing
  anything new. Useful after manual `.tex` edits or to retry a failed build.
- `/paper status [<venue>/<direction>] [--all]` — print the progress board for the
  current direction (also persisted to `<direction>/status.md`). Pass an explicit
  `<venue>/<direction>` to target a specific folder and adopt it as the new cursor
  (recovery path for in-flight projects). Pass `--all` to walk every venue/direction
  and refresh each `status.md`.

## Action

1. Load the `paper-architect` skill (`.claude/skills/paper-architect/SKILL.md`).
2. Parse `$ARGUMENTS` into `<subcommand> <args>`; run the matching workflow stage.
3. Read + update the venue/direction context in AgentDB `project/paper-context`.
4. Write artifacts under `outputs/papers/<venue>/<direction>/`.
5. End every subcommand by printing
   `research_assistant.papers.render_progress_footer(venue, direction, status)` so
   the user always knows which stage they're at and what's next.
