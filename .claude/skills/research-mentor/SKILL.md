---
name: research-mentor
description: Long-running research mentor (科研导师 / 发展规划). Tracks stated goals, weekly check-ins, blockers, and decisions in AgentDB `project/` namespace; compares recent activity against goals; surfaces trajectory drift and suggests path corrections. Use when the user says "check in", "what should I be working on this week", "am I on track", "回顾本周进度".
---

# research-mentor

> **STATUS**: active. `mentor.diff_goals` + `mentor.weekly_checkin_template` are real;
> the project-level research-notes triplet (`state.yaml` + `findings.md` + `log.md`)
> is implemented in `research_assistant.mentor.research_notes`; AgentDB writes go
> through the MCP `memory_store` tool.

## When to use

- Weekly / biweekly check-ins.
- User asks "what should I be working on", "is my project on track", "should I pivot".
- User wants a retro at the end of a sprint / paper / quarter.

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
4. Surface: ✅ on-track / ⚠️ drifting / ❌ stalled. Suggest 1–3 path corrections.
5. Write a check-in entry: `outputs/mentor/checkin-YYYY-MM-DD.md` AND
   `mcp__claude-flow__memory_store` into `project/checkins/YYYY-MM-DD`.

### Goal-setting flow

1. Interactive: ask user for 1–3 long-term goals + their definitions of success.
2. Persist to `project/goals`.

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

## Open TODOs before this skill is real

- [ ] Decide check-in cadence (default: every 7 days, configurable).
- [ ] Decide what counts as "activity" — file mtimes? AgentDB write timestamps?
- [ ] Decide retro format (planned vs. actual table).
