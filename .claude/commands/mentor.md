---
name: mentor
description: Research mentor + boss-prep. Weekly check-in vs goals, past-work / research-notes bookkeeping, plus boss profile / meeting log / rehearsal under `/mentor boss`.
---

# /mentor

Invoke the `research-mentor` skill. The skill covers self-tracking (goals,
check-ins, past-work, research-notes) and boss-tracking (profile, meetings,
rehearsals) as one unified surface, since both are "research-project context
about people" — your own trajectory and your advisor's expectations.

## Self-tracking subcommands

- `/mentor` (empty) — run a weekly check-in. Includes a ⏳ "Stale experiments"
  bucket populated from `mentor.stale_experiments(min_age_days=14)` so the user
  sees experiments that have quietly stalled even when the goals-vs-activity
  diff looks healthy.
- `/mentor set-goals` — interactively (re)write `project/goals` in AgentDB.
- `/mentor add-past-work [<title>]` — quick-capture an old project as a
  past-work entry without leaving the mentor flow. Asks only for the title
  (if not given), defaults year/venue/status sensibly, writes
  `inputs/past-work/<slug>.md` from `mentor.past_work.compose_past_work_entry`,
  and (if a GitHub URL is supplied) binds + offers to clone the repo. Returns
  the user to the mentor flow with a one-line confirmation. Use the full
  `/past-work add` flow when you want a long-form capture with all fields
  filled.
### Project-level research notes

- `/mentor project init <title>` — bootstrap a project-level research-notes
  triplet (`state.yaml` + `findings.md` + `log.md`) under
  `outputs/research-notes/<slug>/`.
- `/mentor project list` — table of all research-notes projects.
- `/mentor project show [<slug>]` — print state summary + findings preview +
  last 5 log rows.
- `/mentor project log <kind>: <summary>` — append one row to `log.md`
  (`<kind>` ∈ `bootstrap` / `inner-loop` / `outer-loop` / `pivot` / `report` /
  `conclude`).
- `/mentor project finding <section>: <body>` — append a paragraph under the
  named findings.md section.
- `/mentor project sync` — index every project's `state.yaml` into AgentDB
  namespace `project/research-notes/`.

## Boss subcommands (delegated to the `boss-historian` agent)

The bare `/boss …` slash is a thin alias for `/mentor boss …`. Both are
documented at `.claude/agents/boss-historian.md`; the canonical form going
forward is `/mentor boss …`.

- `/mentor boss` or `/mentor boss show` — read `inputs/boss-profile/profile.md`
  and the last 3 files under `inputs/boss-profile/meetings/`, print as one
  prep block. No writes. Run this before each report meeting.
- `/mentor boss edit` — interactive capture/update of `profile.md` from
  `docs/boss-profile-template.md`.
- `/mentor boss meeting` (alias `/mentor boss meeting add`) — capture a new
  meeting log into `inputs/boss-profile/meetings/<YYYY-MM-DD>.md` from
  `docs/boss-meeting-template.md`. Date defaults to today; appends `-2`,
  `-3`, … on same-day collisions.
- `/mentor boss rehearse [<report-slug>]` — multi-turn mock Q&A. The boss
  persona reads your report material plus profile + last 3 meetings, then
  drills you with questions in his style. Transcript saved to
  `inputs/boss-profile/rehearsals/<YYYY-MM-DD>-<slug>.md`.
- `/mentor boss sync` — re-walk `inputs/boss-profile/{profile.md,meetings/*.md}`
  and upsert each entry into AgentDB `project/boss/`.

## Action

1. Load the `research-mentor` skill (`.claude/skills/research-mentor/SKILL.md`).
2. If `$ARGUMENTS` starts with `boss`, delegate to the `boss-historian` agent
   (`.claude/agents/boss-historian.md`) with the remaining args; otherwise run
   the matching self-tracking workflow.
3. Write the check-in/retro to `outputs/mentor/` and AgentDB
   `project/checkins/`; boss artifacts land under `inputs/boss-profile/` and
   AgentDB `project/boss/`.
