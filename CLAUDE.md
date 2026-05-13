# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Mission

**lucky-research** is a personal **research-assistant Claude Code plugin**, shared with a
small group of friends via a single GitHub repo (`git@github.com:xxx1766/lucky-research.git`).

Five MVP capabilities, each exposed as a Skill + slash command:

| Slash | Skill | Capability |
|---|---|---|
| `/summarize`  | `lit-summarize`    | 文献总结 — PDFs/arXiv → structured markdown summaries, indexed in AgentDB `papers/`. |
| `/idea-check` | `idea-validate`    | idea 确认 — horizontal comparison matrix OR vertical lineage trace. |
| `/paper`      | `paper-architect`  | 论文架构 + 写作 — venue-rooted, multi-stage flow (`venue → direction → scout → focus → motivate → write`) under `outputs/papers/<venue>/<direction>/`. |
| `/cite`, `/convert` | `ref-manager`      | 参考文献 + 格式 — BibTeX merge, cite-as-you-write resolution, Markdown/LaTeX/docx via pandoc. |
| `/mentor`     | `research-mentor`  | 科研导师 / 发展规划 — long-running trajectory tracking, weekly check-ins, path corrections. |
| `/past-work`  | `past-work-historian` (agent) | 往期工作 — capture / list / sync past projects under `inputs/past-work/`; powers recall during `/paper direction` discussions. |
| `/boss`       | `boss-historian` (agent) | 大老板形象 — capture profile + per-meeting notes under `inputs/boss-profile/`; `/boss show` prints profile + last 3 meetings as pre-report prep. |
| `/experiment` | `experiment-runner` | 实验设计 + 实验执行/分析 — bind to one GitHub repo per experiment (URL + SHA tracking, optional clone), record versioned execution attempts (semver) with full env capture, mirror result files locally so `/paper` can pull them at write time. |

Post-MVP (not yet scaffolded): 科研绘图.

## Repository Layout

```
src/research_assistant/   Python helpers (PDF parse, BibTeX, pandoc shell-outs, mentor diff)
  lit/                    PDF + arXiv ingestion (+ sourcing.py for venue-aware scout)
  ideas/                  Idea matrix + lineage helpers
  refs/                   BibTeX merge + pandoc convert
  mentor/                 Trajectory diff + check-in template + past-work + boss-profile
  papers/                 Venue/direction path resolution + stage-status helpers
  experiments/            Slug + semver + repo-state + env-capture + version-registration
  common/io.py            Single source of truth for inputs/outputs paths

.claude/skills/           Six MVP skills (lit-summarize, idea-validate, paper-architect,
                          ref-manager, research-mentor, experiment-runner) —
                          Claude-Code-discoverable
.claude/commands/         Nine slash entry points (/summarize, /idea-check, /paper,
                          /cite, /convert, /mentor, /past-work, /boss, /experiment)
.claude/agents/           RuFlo V3 framework agents (89 included) + domain agents
                          (past-work-historian, boss-historian)

docs/                     Shared templates + per-feature docs (committed):
                          past-work-template.md, direction-template.md,
                          boss-profile-template.md, boss-meeting-template.md
inputs/                   User-supplied content (gitignored):
                          inputs/papers/        — PDFs to summarize
                          inputs/past-work/     — one md per past project; powers the
                                                  past-work-historian agent
                          inputs/boss-profile/  — profile.md + meetings/YYYY-MM-DD.md;
                                                  powers the boss-historian agent
outputs/                  Generated summaries / drafts / bibs / figures (gitignored)
outputs/papers/<venue>/   Venue-rooted paper-output tree:
  _venue.md                       论文特点和要求
  _template/                      user-supplied conference .sty / .cls / .bst
  <direction>/
    expert.md                     小方向专家角色 (YAML frontmatter + body)
    related-papers/<slug>.md      对比论文
    focused-problem.md            聚焦问题
    experiments/                  对比实验和benchmark
    outline.md                    写作思路和架构 (Markdown, planning)
    main.tex, sections/*.tex      paper prose (LaTeX-native)
    refs.bib                      per-direction BibTeX
    main.pdf                      auto-rendered preview / submission PDF
    status.md                     auto-updated stage tracker
outputs/experiments/      Per-experiment tree (gitignored, cross-machine sync via the bound repo):
  _index.md                       registry: slug · status · versions · last_sync
  <slug>/
    manifest.md                   YAML frontmatter (repo URL/branch/SHA, papers, status)
    design.md                     RQ + hypothesis + baselines + traces + platforms + metrics
    references.md                 comparison matrix from /experiment scout
    versions/<vN.M>.md            per-version env snapshot + metrics + result pointer
    results/<vN.M>/...            mirrored result files for /paper to consume
    data/index.md                 data artifact registry (categorized + sha256)
    configs/<vN.M>.requirements.txt  full pip freeze at run time
    repo/                         optional local clone of the bound GitHub repo
    status.md                     auto-generated 5-stage progress board
docs/                     Per-feature docs (currently empty)
tests/                    pytest

ruvector.db               Per-user AgentDB memory (gitignored)
.swarm/                   Per-user swarm runtime state (gitignored)
.claude-flow/             RuFlo V3 runtime config + workers (config.yaml shared,
                          logs/sessions/metrics gitignored)
```

## How a Session Works

```
inputs/papers/*.pdf  ──┐
arXiv URL / DOI     ──┴──▶ /summarize ──▶ outputs/summaries/<slug>.md
                                            + AgentDB memory_store(namespace="papers")
                                                       │
                                                       ▼
                                          /idea-check  (horizontal | vertical)
                                                       │
                                                       ▼
                                          /paper       (venue | direction | scout |
                                                        focus | motivate | write |
                                                        status)
                                                       │
                                                       ▼
                                          /cite + /convert
                                                       │
                                                       ▼
                                          /mentor      (weekly drift check)
```

Skills read/write AgentDB via the `claude-flow` MCP server:
- `mcp__claude-flow__memory_store` — index summaries / ideas / check-ins.
- `mcp__claude-flow__memory_search` — semantic search across `papers/`, `ideas/`, `project/`.
- Namespaces by convention: `papers/`, `ideas/`, `drafts/`, `project/`, plus
  `project/paper-context` (current `(venue, direction)` cursor) and
  `project/past-work/` (prior projects surfaced by `past-work-historian`).

## Build & Test

```bash
# Install Python helpers (PyMuPDF, arxiv, bibtexparser, pypandoc, pydantic)
pip install -e ".[dev]"

# Run the smoke test
pytest

# Lint
ruff check src tests
```

- ALWAYS run `pytest` after touching anything under `src/research_assistant/`.
- If a skill needs a new helper, add the function in `src/research_assistant/<feature>/`
  rather than in the skill prompt — keeps the prompt thin.

## Working in this repo (behavioral rules)

- Do what has been asked; nothing more, nothing less.
- NEVER create files unless absolutely necessary for the goal.
- ALWAYS prefer editing an existing file to creating a new one.
- NEVER proactively create documentation files (`*.md`) or README files unless explicitly requested.
- NEVER save working files, tests, or scratch markdown to the root folder — use the
  directories above.
- ALWAYS read a file before editing it.
- NEVER commit secrets, credentials, or `.env` files.

## File Organization

| Put it in | Type of file |
|---|---|
| `src/research_assistant/` | Python source for deterministic helpers |
| `tests/`                  | pytest tests |
| `.claude/skills/<name>/SKILL.md` | A new feature's skill prompt |
| `.claude/commands/<verb>.md`     | A new slash command (wraps a skill) |
| `docs/`                   | Per-feature documentation |
| `inputs/papers/`          | User PDFs (gitignored) |
| `outputs/`                | Generated artifacts (gitignored) |

## Project Architecture rules

- Follow Domain-Driven Design: each MVP capability is its own bounded subpackage under
  `src/research_assistant/` (`lit/`, `ideas/`, `refs/`, `mentor/`, `papers/`, `experiments/`).
- Keep files under 500 lines.
- Use typed interfaces (Pydantic models or `@dataclass`) for any cross-module data shape
  — paper summaries, idea graph nodes, project state.
- Prefer TDD London School (mock filesystem and AgentDB) for new code.
- Validate user-supplied paths at boundaries (`inputs/papers/<x>` must resolve inside
  `inputs/papers/`) — no directory traversal.

## Sharing with Collaborators

```bash
git clone git@github.com:xxx1766/lucky-research.git
cd lucky-research
pip install -e ".[dev]"
# drop papers into inputs/papers/
# open in Claude Code; the 6 slash commands appear automatically
```

Per-user state (`inputs/`, `outputs/`, `ruvector.db`, `.swarm/`) is gitignored. Only the
plugin (skills + commands + Python helpers) is shared.

## Security Rules

- NEVER hardcode API keys, secrets, or credentials in source files.
- NEVER commit `.env` files or anything in `inputs/` (may contain copyrighted PDFs).
- Validate user input at system boundaries (especially paths into `inputs/` / `outputs/`).
- Sanitize anything Claude writes back to disk under `outputs/`.
- For security scans of the plugin code:
  `npx @claude-flow/cli@latest security scan`

---

# RuFlo V3 Runtime (the agent platform this project uses)

The sections below are the standing framework guidance for the **RuFlo V3** runtime that
hosts this plugin. They apply to how Claude orchestrates multi-agent work inside Claude
Code — they are not the research-assistant's domain rules. Edit cautiously.

### Project Config

- **Topology**: hierarchical-mesh
- **Max Agents**: 15
- **Memory**: hybrid (AgentDB + HNSW + Claude Code bridge)
- **HNSW**: Enabled
- **Neural**: Enabled

## Concurrency: 1 MESSAGE = ALL RELATED OPERATIONS

- All operations MUST be concurrent/parallel in a single message.
- Use Claude Code's Agent tool for spawning agents (not MCP-only).
- ALWAYS spawn ALL agents in ONE message with full instructions.
- ALWAYS batch ALL file reads/writes/edits in ONE message.
- ALWAYS batch ALL Bash commands in ONE message.

## Swarm Orchestration

- MUST initialize the swarm using CLI tools when starting complex tasks.
- MUST spawn concurrent agents using Claude Code's Agent tool.
- Never use CLI tools alone for execution — Agent-tool agents do the actual work.
- MUST call CLI tools AND Agent tool in ONE message for complex work.

### 3-Tier Model Routing (ADR-026)

| Tier | Handler | Latency | Cost | Use Cases |
|------|---------|---------|------|-----------|
| **1** | Agent Booster (WASM) | <1ms | $0 | Simple transforms (var→const, add types) — Skip LLM |
| **2** | Haiku | ~500ms | $0.0002 | Simple tasks, low complexity (<30%) |
| **3** | Sonnet/Opus | 2–5s | $0.003–0.015 | Complex reasoning, architecture, security (>30%) |

- For Tier 1 simple transforms, use Edit directly — no LLM agent needed.

## Swarm Configuration & Anti-Drift

- ALWAYS use hierarchical topology for coding swarms.
- Keep maxAgents at 6–8 for tight coordination.
- Use specialized strategy for clear role boundaries.
- Use `raft` consensus for hive-mind (leader maintains authoritative state).
- Run frequent checkpoints via `post-task` hooks.
- Keep shared memory namespace for all agents.

```bash
npx @claude-flow/cli@latest swarm init --topology hierarchical --max-agents 8 --strategy specialized
```

## Swarm Execution Rules

- ALWAYS use `run_in_background: true` for Agent tool calls.
- ALWAYS put ALL Agent calls in ONE message for parallel execution.
- After spawning, STOP — do NOT add more tool calls or check status.
- Never poll agent status repeatedly — trust agents to return.
- When agent results arrive, review ALL results before proceeding.

## V3 CLI Commands

| Command | Subcommands | Description |
|---------|-------------|-------------|
| `init` | 4 | Project initialization |
| `agent` | 8 | Agent lifecycle management |
| `swarm` | 6 | Multi-agent swarm coordination |
| `memory` | 11 | AgentDB memory with HNSW search |
| `task` | 6 | Task creation and lifecycle |
| `session` | 7 | Session state management |
| `hooks` | 17 | Self-learning hooks + 12 workers |
| `hive-mind` | 6 | Byzantine fault-tolerant consensus |

```bash
npx @claude-flow/cli@latest init --wizard
npx @claude-flow/cli@latest memory search --query "papers about contrastive learning"
npx @claude-flow/cli@latest doctor --fix
```

## Available Agents (16 typed roles + custom)

`coder`, `reviewer`, `tester`, `planner`, `researcher`,
`security-architect`, `security-auditor`, `memory-specialist`, `performance-engineer`,
`hierarchical-coordinator`, `mesh-coordinator`, `adaptive-coordinator`,
`pr-manager`, `code-review-swarm`, `issue-tracker`, `release-manager`.

Any string can be a custom agent type — these are the typed roles with specialized
behavior.

## Memory & Vector Search (MCP tools)

| Tool | Description |
|------|-------------|
| `memory_store` | Store with ONNX 384-dim vector embedding |
| `memory_search` | Semantic vector search by query |
| `memory_retrieve` | Get entry by key |
| `memory_list` | List entries in namespace |
| `memory_delete` | Delete entry |
| `memory_import_claude` | Import Claude Code memories into AgentDB |
| `memory_search_unified` | Search across ALL namespaces |
| `memory_bridge_status` | Show bridge health, vectors, SONA, intelligence |

The five MVP skills use these tools directly. Namespaces by convention: `papers/`,
`ideas/`, `drafts/`, `project/`.

## Discovering more MCP tools

```
ToolSearch("memory search")     → memory_store, memory_search, memory_search_unified
ToolSearch("swarm")             → swarm_init, swarm_status, swarm_health
ToolSearch("hive consensus")    → hive-mind_consensus, hive-mind_status
ToolSearch("+aidefence")        → aidefence_scan, aidefence_is_safe
```

## Quick Setup (RuFlo V3 daemon)

```bash
claude mcp add claude-flow -- npx -y @claude-flow/cli@latest
npx @claude-flow/cli@latest daemon start
npx @claude-flow/cli@latest doctor --fix
```

## Claude Code vs MCP Tools

- **Claude Code Agent tool** handles execution: agents, file ops, code generation, git.
- **MCP tools** (via ToolSearch) handle coordination: swarm, memory, hooks, routing,
  hive-mind.
- **CLI commands** (via Bash) are the same tools with terminal output.

## Support

- Documentation: https://github.com/ruvnet/ruflo
- Issues: https://github.com/ruvnet/ruflo/issues
