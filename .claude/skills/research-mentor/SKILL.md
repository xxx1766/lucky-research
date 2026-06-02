---
name: research-mentor
description: Long-running research mentor + boss-prep (科研导师 / 发展规划 / 老板汇报). Tracks self-trajectory (stated goals, weekly check-ins, decisions, drift) AND boss context (profile, meeting log, rehearsal) in AgentDB `project/` namespace. Use when the user says "check in", "what should I be working on this week", "am I on track", "回顾本周进度", or "/mentor boss …" / "/boss …" for boss-prep flows.
---

# research-mentor

> **STATUS**: active. `mentor.diff_goals` + `mentor.weekly_checkin_template` are real;
> the project-level research-notes triplet (`state.yaml` + `findings.md` + `log.md`)
> is implemented in `research_assistant.mentor.research_notes`; AgentDB writes go
> through the MCP `memory_store` tool. Boss subcommands delegate to the
> `boss-historian` agent at `.claude/agents/boss-historian.md`.

## When to use

- Weekly / biweekly check-ins.
- User asks "what should I be working on", "is my project on track", "should I pivot".
- User wants a retro at the end of a sprint / paper / quarter.
- User runs `/mentor boss …` (or the `/boss …` alias) for boss-prep flows.

## Boss flow (delegation)

When `$ARGUMENTS` starts with `boss`, **strip the leading `boss` token** and
hand off to the `boss-historian` agent at
`.claude/agents/boss-historian.md`. That agent owns the workflows for `show`,
`edit`, `meeting`, `rehearse`, `sync`, and reads/writes
`inputs/boss-profile/{profile,meetings,reports,rehearsals}` plus AgentDB
namespace `project/boss/`.

This is a delegation, not a re-implementation — keep all the boss-specific
prompt logic in the agent file so `/boss` (the alias) and `/mentor boss`
land in exactly the same place.

## Workflow

### State model (AgentDB namespace `project/`)

```
project/goals               → list of long-term goals + their priorities
project/checkins/YYYY-MM-DD → weekly snapshot (done / blocked / decisions / mood)
project/decisions/<slug>    → architecture-style records for project decisions
project/backlog             → idea backlog, ranked
```

### Check-in flow

1. Read `project/goals` + the last 3–4 `project/checkins/*`.
2. Read recent activity signals: new files in `outputs/summaries/`, new
   `outputs/drafts/<slug>/...`, new `ideas/*` entries.
3. Call `research_assistant.mentor.diff_goals(goals, recent_activity)`.
4. Call `research_assistant.mentor.stale_experiments(min_age_days=14)` —
   returns `active` experiments whose latest `versions/<vN.M>.md` (or
   `manifest.md` if no version exists yet) hasn't been touched in 14+ days.
   Surface them under a ⏳ "Stale experiments" bucket alongside the
   goal-vs-activity diff. Each row: `slug · latest_version · N days idle`.
   An experiment can look on-track via the goals diff while quietly stalling
   here — that's the drift signal this catches.
5. Surface: ✅ on-track / ⚠️ drifting / ❌ stalled / ⏳ stale-experiments.
   Suggest 1–3 path corrections.
6. Write a check-in entry: `outputs/mentor/checkin-YYYY-MM-DD.md` AND
   `mcp__claude-flow__memory_store` into `project/checkins/YYYY-MM-DD`.

### Goal-setting flow

1. Interactive: ask user for 1–3 long-term goals + their definitions of success.
2. Persist to `project/goals`.

### Quick capture flow (`/mentor add-past-work [<title>]`)

Optimized for "I just remembered an old project, log it before I forget."
Stays inside the mentor turn — minimal Q&A, smart defaults, return to the
check-in.

1. If no `<title>` in args, ask once (plain text, no AskUserQuestion per
   the `feedback_decision_ui` memory): `"Title for this past-work entry?"`
2. Compute defaults: `d = mentor.past_work.quick_capture_defaults(title)`.
   This already runs `next_available_slug`, so the slug is collision-safe.
3. Plain-text optional probes — ask only one round, accept blank to skip:
   - `"GitHub repo URL (optional, blank to skip):"` — if given, validate
     it looks like a git URL and stash it for step 5.
   - `"One-line abstract (optional):"` — into `d["abstract"]`.
   - `"Status [in-progress / published / unpublished / abandoned, default
     in-progress]:"` — override `d["status"]` if non-blank.
4. `path = mentor.past_work.compose_past_work_entry(**d)` writes the
   entry to `inputs/past-work/<slug>.md` with `_TODO_` placeholders for
   anything still empty so the user knows what's left to fill in.
5. If a GitHub URL was given in step 3:
   - `mentor.past_work.bind_repo(slug, url)` writes the `repo:` frontmatter.
   - Plain-text Y/N: `"Clone the repo locally now? [y/N]"`. On `y`, call
     `mentor.past_work.clone_repo(slug)`. On `N`, leave it `tracked`.
6. `mcp__claude-flow__memory_store(namespace="project/past-work", key=slug,
   value=mentor.past_work.to_agentdb_payload(parse_entry(path)))` so the
   `past-work-historian` agent can recall it during `/paper direction` etc.
7. Print one line: `"captured: <slug> → inputs/past-work/<slug>.md"`. Hand
   back to the prior mentor flow if one was in progress.

### Project-level research notes (`/mentor project ...`)

A *project* sits one level above individual experiments and papers — it's
"the research thread the user is pulling on for the next 3–18 months." Adapted
from Orchestra-Research/AI-Research-SKILLs (MIT) `0-autoresearch-skill`.

Each project lives at `outputs/research-notes/<slug>/` and owns three files
(all helpers in `research_assistant.mentor.research_notes`):

- `state.yaml` — `ResearchNotesState` (project meta, literature shortlist,
  hypothesis tree, experiments registry, outer-loop cycle counter).
- `findings.md` — running synthesis. Read this at the start of every session.
- `log.md` — append-only chronological decision timeline.

The "current project" is a slug stored in AgentDB
`project/research-notes-context.current` (parallel to `paper-context` and
`experiment-context`). Set on `init` and `show`.

**Subcommand router:**

| Subcommand | Action |
|---|---|
| `project init <title>` | `slug = research_notes.slugify(title)`; ask for a 1-sentence research question (plain text); `research_notes.init_project(slug, title, question)`; set the cursor. |
| `project list` | `research_notes.list_projects()` → table. |
| `project show [<slug>]` | Resolve slug (arg → cursor); print state.yaml summary + findings.md "Current understanding" section + last 5 log rows via `research_notes.parse_log(slug)`. |
| `project log <kind>: <summary>` | `research_notes.append_log(slug, kind, summary)`. `<kind>` ∈ `bootstrap` / `inner-loop` / `outer-loop` / `pivot` / `report` / `conclude`. |
| `project finding <section>: <body>` | `research_notes.append_finding(slug, section, body)`. Section is one of `Current understanding` / `Key results` / `Patterns and insights` / `Lessons and constraints` / `Open questions`, but any heading is accepted. |
| `project sync` | Re-read every `outputs/research-notes/*/state.yaml`; `mcp__claude-flow__memory_store` each via `research_notes.to_agentdb_payload(state)` into namespace `project/research-notes`. |

**When this surfaces during a check-in.** During the weekly check-in flow,
after the goals-vs-activity diff, also:

1. Read `project/research-notes-context.current`. If unset, skip.
2. Read `findings.md` (last "Current understanding" + "Open questions" sections).
3. Surface in the check-in: "since last week, has anything in your current
   understanding changed? Any open questions resolved?". Encourage the user
   to drop a finding via `/mentor project finding ...`.
4. The Orchestra "outer loop direction" decision (deepen / broaden / pivot /
   conclude) is what to ask the user when `findings.md` looks ready.

The project-notes triplet is human-in-loop; lucky-research does NOT run
Orchestra's `/loop 20m` heartbeat. The synthesis cadence is the weekly check-in,
not a 20-minute timer.

## Outputs

- `outputs/mentor/checkin-YYYY-MM-DD.md`
- `outputs/research-notes/<slug>/{state.yaml, findings.md, log.md}`
- AgentDB entries under namespaces `project/` and `project/research-notes/`.

## Memory keys touched

- `project/goals` — read/write
- `project/checkins/*` — read/write
- `project/decisions/*` — write
- `project/research-notes-context.current` — read/write (cursor `{slug}`)
- `project/research-notes/<slug>` — write (on `init` and `sync`)
- `papers/*`, `ideas/*`, `drafts/*` — read (recent-activity signal)

## Conventions (settled defaults)

- **Check-in cadence**: every 7 days. The skill never auto-fires; `/mentor`
  is user-initiated. The cadence is what the check-in template promises ("last
  week's") and what `stale_experiments(min_age_days=14)` uses as a sensible
  multiple.
- **Activity signal**: file mtimes under `outputs/summaries/`,
  `outputs/drafts/`, `outputs/papers/`, `outputs/idea-checks/`, and
  `outputs/experiments/*/versions/*.md` (used by `stale_experiments`). AgentDB
  write timestamps are NOT used — the on-disk truth is the canonical record
  and survives migrations / AgentDB rebuilds.
