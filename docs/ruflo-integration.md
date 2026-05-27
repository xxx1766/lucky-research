# Using lucky-research together with ruflo (optional)

This plugin runs fine **on its own**. ruflo (the claude-flow swarm runtime) is an
**optional accelerator** — it lets you parallelize heavy stages (mainly paper scouting)
across multiple agents. This doc explains how the two combine **without coupling**: every
integration point is additive, so a collaborator who never installs ruflo loses nothing.

## Principle: additive + graceful degradation

- **The plugin's skills are never modified to require swarm.** `/summarize`, `/idea-check`,
  `/paper`, `/experiment`, `/cite`, `/mentor`, `/figure` behave identically with or without ruflo.
- **swarm is reached only through a separate opt-in command** (`/scout-swarm`). Without
  ruflo, that one command prints "use `/paper scout` instead" and stops — nothing breaks.
- **Interoperation is by convention, not wiring.** The swarm component writes the *same*
  artifacts to the *same* AgentDB namespaces and output paths the normal skills use, so
  downstream stages consume its output without knowing a swarm produced it.

### Honest baseline note

The MVP skills already use the claude-flow MCP `memory_store` / `memory_retrieve` /
`memory_search` tools for cursor persistence and indexing. That memory dependency is the
*existing* baseline — it is separate from swarm. The on-disk manifests under `outputs/` are
the source of truth, and `research_assistant.ideas.registry.reindex_from_disk()` can rebuild
AgentDB if it is wiped. This integration deliberately does **not** widen that dependency:
swarm (`swarm_init` / `agent_spawn`) stays quarantined behind `/scout-swarm`.

## Architecture: three layers, three integration points

```
┌─────────────────────────────────────────────────────────────────────┐
│  User entry:  /summarize   /idea-check   /paper   /experiment   ...    │
│               + (optional)  /scout-swarm                               │
└───────────────────────────────┬───────────────────────────────────────┘
                                 │ triggers
                                 ▼
┌─────────────────────────────────────────────────────────────────────┐
│  SKILL layer (.claude/skills/*)        orchestrator = Claude main loop │
│                                                                       │
│   linear stages ─────────┐         ┌─── parallelizable (point ②)       │
│   venue → direction →     │         │   /paper scout  ←→  /scout-swarm  │
│   focus → write ...       │         │   (same artifacts, your choice)  │
└──────────┬───────────────┘         └──────────────┬────────────────────┘
           │                                         │ swarm_init + spawn
           │                                         │ (ONE message, background)
           │                                         ▼
           │                          ┌──────────────────────────────────┐
           │                          │  SWARM layer (hierarchical, ≤8)   │
           │                          │  researcher  researcher  reviewer │
           │                          └─────┼───────────┼──────────┼──────┘
           │     point ③ (agent → Bash)     │           │          │
           │            ▼                   ▼           ▼          ▼
           │   ┌──────────────────┐  ┌───────────────────────────────────┐
           └──▶│ Python helpers   │◀─┤  every agent can call:            │
               │ src/research_    │  │  direction_path / search_for_     │
               │ assistant/*      │  │  direction / bibtex / env capture │
               └──────────────────┘  └───────────────────────────────────┘

        ┌──────────────────────────────────────────────────────────┐
        │  point ① — AgentDB shared memory (the real glue)           │
        │  papers/   ideas/   drafts/   project/paper-context        │
        │  ▲ skill writes  ▲ skill reads   ▲ swarm writes  ▲ reads    │
        └──────────────────────────────────────────────────────────┘
             ↑ all layers use the same memory_store / memory_search
```

### ① AgentDB shared memory — the glue (no wiring needed)

A swarm `researcher` agent calls `memory_store(namespace="papers", key="<slug>")`; later
`/paper` calls `memory_search` / `memory_retrieve` on the same namespace and finds it. The
only contract is the namespace convention (`papers/ ideas/ drafts/ project/`).

### ② swarm as a sub-routine of one stage

The `scout` stage is the natural fit: scouting many papers is embarrassingly parallel.
Instead of `/paper scout` walking papers sequentially, `/scout-swarm` fans sub-areas across
agents — but both emit the identical `related-papers/<slug>.md` + `papers/<slug>` artifacts.

### ③ Python helpers as the agents' "hard tools"

Deterministic work (path resolution, sourcing, BibTeX, env capture, semver) is delegated to
`src/research_assistant/*` via Bash, so agents don't hallucinate it — matching the repo rule
"helpers live in src, prompts stay thin."

## Option A — the opt-in component: `/scout-swarm`

The packaged accelerator. Skill: `.claude/skills/research-swarm/SKILL.md`;
command: `.claude/commands/scout-swarm.md`.

- **When to use:** you have ruflo and a `(venue, direction)` cursor set, and want to scout a
  broad direction fast.
- **What it does:** probes for swarm tools → reads the cursor → `swarm_init` (hierarchical)
  + parallel `researcher` spawn → each writes `related-papers/<slug>.md` + `papers/<slug>` →
  aggregates into a comparison table → hands back to `/paper focus`.
- **Degradation:** no ruflo → prints "use `/paper scout`" and stops. Non-fatal.

## Option B — the manual recipe (no component, just convention)

If you'd rather not use the command, you can run a swarm by hand and still interoperate, as
long as you honor the contract:

1. `npx @claude-flow/cli@latest swarm init --topology hierarchical --max-agents 6 --strategy specialized`
   (or the `swarm_init` MCP tool).
2. In ONE message, spawn N `researcher` agents (`run_in_background: true`), each told to:
   - scout one sub-area via `research_assistant.lit.sourcing.search_for_direction(venue, keywords)`;
   - write each summary to `<direction>/related-papers/<slug>.md` (resolve the dir with
     `research_assistant.papers.direction_path(venue, direction)`);
   - `memory_store(namespace="papers", key="<slug>")` for each paper.
3. Don't poll; when agents return, dedupe by slug and continue with `/paper focus`.

## Namespace / path contract (honor this for any swarm work)

| Namespace / path | skill writes | skill reads | swarm writes | swarm reads |
|---|:-:|:-:|:-:|:-:|
| `papers/<slug>` | ✓ | ✓ | ✓ | ✓ |
| `ideas/<slug>` | ✓ | ✓ | ✓ | ✓ |
| `project/paper-context.current` (venue/direction cursor) | ✓ | ✓ | — | ✓ |
| `outputs/papers/<venue>/<direction>/related-papers/*.md` | ✓ | ✓ | ✓ | — |
| `src/research_assistant/*` (helpers) | call | call | call | — |

As long as swarm work writes through these names, the normal skills consume it transparently.
