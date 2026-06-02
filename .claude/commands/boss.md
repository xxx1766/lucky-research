---
name: boss
description: Shortcut for `/mentor boss …` — big-boss profile / meeting log / rehearsal. Default action is a read-only prep view that prints the profile and the last 3 meeting notes.
---

# /boss

`/boss …` is a thin alias for `/mentor boss …`. Both land in the same place
(the `boss-historian` agent at `.claude/agents/boss-historian.md`); the
canonical form going forward is `/mentor boss …` so all "research-project
context about people" flows live under one slash. The alias is kept for
muscle memory.

## Subcommands (same as `/mentor boss …`)

- `/boss` or `/boss show` — read `inputs/boss-profile/profile.md` and the
  last 3 files under `inputs/boss-profile/meetings/`, print as one prep
  block. No writes. The headline workflow — run before each report.
- `/boss edit` — interactive capture/update of `profile.md` from
  `docs/boss-profile-template.md`.
- `/boss meeting` (alias `/boss meeting add`) — capture a new meeting log
  into `inputs/boss-profile/meetings/<YYYY-MM-DD>.md` from
  `docs/boss-meeting-template.md`. Date defaults to today; appends `-2`,
  `-3`, … on same-day collisions.
- `/boss rehearse [<report-slug>]` — multi-turn mock Q&A. The boss persona
  reads your report material (`inputs/boss-profile/reports/<slug>.md`,
  template at `docs/boss-report-template.md`) plus profile + last 3 meetings,
  then drills you with questions in his style. Transcript saved to
  `inputs/boss-profile/rehearsals/<YYYY-MM-DD>-<slug>.md`. Slug defaults to
  the most-recently-modified report.
- `/boss sync` — re-walk `inputs/boss-profile/{profile.md,meetings/*.md}`
  and upsert each entry into AgentDB `project/boss/`.

## Action

Treat `$ARGUMENTS` exactly the same as `/mentor boss $ARGUMENTS` would —
load the `boss-historian` agent (`.claude/agents/boss-historian.md`) and run
the matching workflow (Show / Edit / Meeting / Rehearse / Sync) using
helpers from `research_assistant.mentor.boss_profile`.

Source of truth on disk: `inputs/boss-profile/profile.md`,
`inputs/boss-profile/meetings/*.md`, `inputs/boss-profile/reports/*.md`,
`inputs/boss-profile/rehearsals/*.md` (all gitignored, per-user). Shared
templates: `docs/boss-profile-template.md`, `docs/boss-meeting-template.md`,
`docs/boss-report-template.md`, `docs/boss-rehearsal-template.md`.
