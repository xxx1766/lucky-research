---
name: boss-historian
description: Curates the user's "big boss" (大老板 / group PI) profile and meeting log so the user can prep before each report. Source of truth is `inputs/boss-profile/profile.md` + `inputs/boss-profile/meetings/YYYY-MM-DD.md`; indexed copy lives in AgentDB namespace `project/boss/`. Invoked under `/mentor boss …` (canonical) or the `/boss …` alias, or whenever the user says "我下周要跟老板汇报", "what does the boss care about", "我上次汇报他说了啥".
---

# boss-historian

## Data layout

| Where | Role |
|---|---|
| `inputs/boss-profile/profile.md` | **Source of truth** — singleton profile, YAML frontmatter + body. Gitignored. User-editable. |
| `inputs/boss-profile/meetings/YYYY-MM-DD.md` | **Source of truth** — one file per report meeting. Gitignored. |
| `inputs/boss-profile/reports/<slug>.md` | **Source of truth** — pre-report material you drop in to drive `/boss rehearse`. Gitignored. |
| `inputs/boss-profile/rehearsals/<YYYY-MM-DD>-<slug>.md` | **Auto-written** transcript of one `/boss rehearse` session. Gitignored. |
| `docs/boss-profile-template.md` | **Shared template** — committed. Copy + fill on first `/boss edit`. |
| `docs/boss-meeting-template.md` | **Shared template** — committed. Copy + fill on every `/boss meeting`. |
| `docs/boss-report-template.md` | **Shared template** — committed. Reference shape for files under `reports/`. |
| `docs/boss-rehearsal-template.md` | **Shared template** — committed. Output shape for files under `rehearsals/`. |
| AgentDB `project/boss/profile` | **Indexed mirror** of the profile. Rebuilt by `/boss sync`. |
| AgentDB `project/boss/meetings/<date>` | **Indexed mirror** of each meeting. Rebuilt by `/boss sync`. |

Helper module: `src/research_assistant/mentor/boss_profile.py` exposes `BossProfile`,
`BossMeeting`, `meeting_slug`, `list_meetings`, `recent_meetings`, `list_reports`,
`latest_report`, `report_path`, `rehearsal_slug`, `rehearsal_path`, `parse_profile`,
`parse_meeting`, `to_agentdb_payload`.

## When to invoke

- Directly from `/mentor boss …` (canonical) or the `/boss …` alias —
  subcommands `show / edit / meeting / rehearse / sync` are identical
  in both forms.
- User says "我下周要跟老板汇报 / I have a meeting with the boss".
- User says "老板上次说啥来着 / what did the boss say last time".
- User says "老板最关心什么 / what does the boss care about".
- User says "陪我演练一下 / 模拟一下汇报 / let's rehearse / mock meeting".

## Workflows

### Show (the historian's main job — pre-report prep)

Triggered by `/boss` or `/boss show`.

1. `Read` `inputs/boss-profile/profile.md`. If absent, tell the user to run
   `/boss edit` first and stop.
2. Compute recent meetings via `recent_meetings(n=3)` from
   `research_assistant.mentor.boss_profile`.
3. Print one block:
   - The full profile body.
   - For each recent meeting (newest first): date header + body.
4. No writes to disk; no AgentDB hit needed.

### Edit (profile authoring)

Triggered by `/boss edit`.

1. If `inputs/boss-profile/profile.md` does **not** exist:
   - Read `docs/boss-profile-template.md`.
   - Walk the user through each frontmatter field (name, role, research_interests,
     recent_papers, collaborators, communication_style, hot_buttons, sore_spots,
     preferred_format).
   - Walk the body sections (Background / What he cares about / Hot buttons /
     Sore spots / How he gives feedback / Recurring asks).
   - Write the file.
2. If it **does** exist:
   - Show current values; ask which fields to update.
   - Rewrite the file with merged content.
3. After write, hint that `/boss sync` will index it into AgentDB once the
   indexing layer lands.

### Meeting (capture one meeting)

Triggered by `/boss meeting` or `/boss meeting add`.

1. Default date to today (YYYY-MM-DD via `meeting_slug(date.today())`); confirm with
   user.
2. If `inputs/boss-profile/meetings/<date>.md` already exists, append `-2`, `-3`, etc.
3. Read `docs/boss-meeting-template.md`.
4. Walk the frontmatter fields (topic, mode, duration_min, mood) and body sections
   (What I reported / His feedback / Action items / Followup signals).
5. Write the file.
6. If the user gave any "Followup signals", remind them to fold those back into
   `profile.md` next time they run `/boss edit`.

### Rehearse (mock meeting Q&A — drill the user before the real report)

Triggered by `/boss rehearse [<report-slug>]`.

1. **Preflight**.
   - If `inputs/boss-profile/profile.md` is absent, tell the user to run
     `/boss edit` first and stop.
   - If `BOSS_REPORTS_DIR` is empty or absent, tell the user:
     "Drop your report material into `inputs/boss-profile/reports/<topic>.md`
     first (template at `docs/boss-report-template.md`)." Stop.
2. **Resolve report.**
   - With slug arg: `report_path(slug)` — raises on path traversal; surface that
     as a clean error.
   - Without arg: `latest_report()`. Print which file you picked
     (e.g. "Picked `q2-progress.md` (most recently modified). Pass an explicit
     slug to override.") so the user can `Ctrl-C` if it's the wrong one.
3. **Load grounding (read-only).** `Read` the profile, the chosen report file,
   and each path returned by `recent_meetings(n=3)`. No AgentDB calls — this
   stage is filesystem-only and works before `/boss sync` is wired up.
4. **Brief the user (one block).** Print:
   - Who you're playing (profile `name` / `role`).
   - Which material you loaded (report slug + topic from its H1).
   - Top hot button (lead with this) and top sore spot (he'll grill on this).
   - Preferred format reminder if set.
   - Controls: reply `pass` to skip the current question, `end` / `结束` /
     `done` to wrap up and save the transcript.
5. **Live Q&A loop (default ~10 turns, hard cap 15).** Each turn:
   - Pick the next question weighted by, in order:
     (a) **profile signals** — `hot_buttons` (lead with), `sore_spots`
         (grill on), `recurring_asks` from the body, `communication_style`
         (e.g. "terse, numbers-first" → demand the headline number first);
     (b) **gaps in the report content** — vague claims without numbers,
         missing baseline, unclear contribution, no compute/cost budget,
         hand-wavy "next steps";
     (c) **echoes from recent meetings** — if past `His feedback` sections
         show he pushed back on X, ask about X again.
   - Phrase the question in his voice — tone matches `communication_style`;
     reuse recurring phrases visible in past meetings where appropriate.
   - Wait for the user's reply.
   - React in one line: either a brief judgment ("good — but he'd push back:
     <one-sentence pushback>") or a single follow-up drill if the answer
     dodged. Do not deliver paragraphs; the boss is busy.
   - Maintain an internal turn count and a rough mood gauge
     (`positive` / `neutral` / `concerned`) based on whether answers landed.
6. **End** when the user types `end` / `结束` / `done`, or after ~10 turns by
   default. Confirm briefly ("Wrapping up — saving transcript.").
7. **Write the transcript.** Compute the output path via
   `rehearsal_path(date.today(), <report-slug-without-.md>)` — this handles
   the `-2`, `-3` same-day collision suffix automatically. Write Markdown
   matching `docs/boss-rehearsal-template.md`:
   - Frontmatter: `date`, `report`, `topic` (inferred from report H1),
     `turns` (actual count), `mood` (final gauge).
   - **Q&A transcript** — one `### Q<i>: <question>` per turn, followed by
     the user's answer as a blockquote, followed by your one-line reaction.
   - **Fix before the real meeting** — checklist of weak spots the
     simulation uncovered (missing numbers, dodged questions, sore-spot
     hits).
   - **Likely follow-ups** — 2–4 questions the boss is still likely to ask
     that you didn't reach this session.
8. **Post-write hint.** Print the path that was written and remind the user
   that running `/boss meeting` after the real meeting makes the rehearsal
   vs. reality comparison easy.

### Sync (re-index disk → AgentDB)

Triggered by `/boss sync`.

1. Walk `inputs/boss-profile/profile.md` and `list_meetings()`.
2. Parse each via `parse_profile` / `parse_meeting`.
3. Upsert each into AgentDB under `project/boss/profile` and
   `project/boss/meetings/<date>` via `mcp__claude-flow__memory_store`.

## Schemas (YAML frontmatter)

### profile.md

```yaml
name: "Prof. XXX"
role: "PI"
research_interests:
  - "AI for systems"
  - "compilers"
recent_papers:
  - "arxiv:2401.xxxxx"
collaborators:
  - "Prof. YYY"
communication_style: "terse, numbers-first"
hot_buttons:
  - "real systems measurement, not just benchmarks"
sore_spots:
  - "over-claiming"
preferred_format: "written memo, then meeting"
```

### meetings/YYYY-MM-DD.md

```yaml
date: 2026-05-12
topic: "Q2 progress + paper plan"
mode: "1:1"
duration_min: 30
mood: "neutral"
```

Body sections (free markdown): **What I reported**, **His feedback**, **Action items**
(checklist), **Followup signals** (what to fold back into the profile).

