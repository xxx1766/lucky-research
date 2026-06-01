---
name: research-mentor
description: Long-running research mentor (科研导师 / 发展规划). Tracks stated goals, weekly check-ins, blockers, and decisions in AgentDB `project/` namespace; compares recent activity against goals; surfaces trajectory drift and suggests path corrections. Use when the user says "check in", "what should I be working on this week", "am I on track", "回顾本周进度".
---

# research-mentor

> **STATUS**: active. `mentor.diff_goals` + `mentor.weekly_checkin_template` are real; AgentDB writes go through the MCP `memory_store` tool.

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

## Outputs

- `outputs/mentor/checkin-YYYY-MM-DD.md`
- AgentDB entries under namespace `project/`.

## Memory keys touched

- `project/goals` — read/write
- `project/checkins/*` — read/write
- `project/decisions/*` — write
- `papers/*`, `ideas/*`, `drafts/*` — read (recent-activity signal)

## Open TODOs before this skill is real

- [ ] Decide check-in cadence (default: every 7 days, configurable).
- [ ] Decide what counts as "activity" — file mtimes? AgentDB write timestamps?
- [ ] Decide retro format (planned vs. actual table).
