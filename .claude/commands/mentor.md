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
  - `project init <title>` — bootstrap a project-level research-notes triplet
    (`state.yaml` + `findings.md` + `log.md`) under `outputs/research-notes/<slug>/`.
  - `project list` — table of all research-notes projects.
  - `project show [<slug>]` — print state summary + findings preview + last 5 log rows.
  - `project log <kind>: <summary>` — append one row to `log.md`
    (`<kind>` ∈ `bootstrap` / `inner-loop` / `outer-loop` / `pivot` / `report` / `conclude`).
  - `project finding <section>: <body>` — append a paragraph under the named
    findings.md section.
  - `project sync` — index every project's state.yaml into AgentDB
    namespace `project/research-notes/`.

## Action

1. Load the `research-mentor` skill (`.claude/skills/research-mentor/SKILL.md`).
2. Run the matching workflow.
3. Write the check-in/retro to `outputs/mentor/` and AgentDB `project/checkins/`.
