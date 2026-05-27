---
name: scout-swarm
description: OPTIONAL · requires ruflo — parallelize paper scouting with a ruflo swarm of researcher agents. Writes the same artifacts as `/paper scout` (related-papers/<slug>.md + AgentDB papers/). Degrades gracefully to `/paper scout` when ruflo is absent.
---

# /scout-swarm

Invoke the `research-swarm` skill to fan paper scouting across a ruflo swarm.

This is an **add-on accelerator**, not a replacement. If you don't have ruflo, ignore
this command entirely and use `/paper scout` — everything else works the same.

## Subcommands

- `/scout-swarm <topic>` — decompose `<topic>` (or the current direction) into sub-areas
  and spawn parallel `researcher` agents. Results land in
  `outputs/papers/<venue>/<direction>/related-papers/<slug>.md` + AgentDB `papers/`.
- `/scout-swarm` (bare) — use the current `(venue, direction)` cursor as the topic.

## Action

1. Load the `research-swarm` skill (`.claude/skills/research-swarm/SKILL.md`).
2. **Probe first**: `ToolSearch("swarm_init agent_spawn")`. If swarm tools are absent,
   print the "use /paper scout instead" notice and stop — do not error.
3. Resolve the `(venue, direction)` cursor (`project/paper-context.current`); if unset,
   ask the user or have them run `/paper venue` + `/paper direction` first.
4. Run the skill's swarm workflow: `swarm_init` (hierarchical) + parallel `researcher`
   spawn in ONE message; after spawning, STOP and let agents return.
5. End with the scouted-papers table + `render_progress_footer(...)`, then point the user
   to `/paper focus`.

See `docs/ruflo-integration.md` for how this composes with the rest of the plugin.
