# lucky-research

A Claude Code research-assistant plugin. Five slash commands cover the full paper-writing
loop — read papers, validate ideas, draft sections, manage references, and track your
research trajectory over time.

## Five MVP capabilities

| Slash command | Skill | What it does |
|---|---|---|
| `/summarize`  | `lit-summarize`    | Summarize papers (`inputs/papers/*.pdf` or arXiv URLs) into structured markdown; index in AgentDB `papers/`. |
| `/idea-check` | `idea-validate`    | Validate an idea via horizontal comparison (related-work matrix) or vertical lineage trace. |
| `/draft`      | `paper-architect`  | Outline a paper or draft a specific section using your project context + cited summaries. |
| `/cite`       | `ref-manager`      | Resolve `[@cite:slug]` placeholders, emit BibTeX, manage `outputs/references/*.bib`. |
| `/convert`    | `ref-manager`      | Convert Markdown ↔ LaTeX ↔ docx via pandoc. |
| `/mentor`     | `research-mentor`  | Weekly check-in: compare recent activity against your stated research goals and surface path corrections. |

> Post-MVP (not yet implemented): 科研绘图, 实验设计, 实验执行/分析.

## Quickstart

```bash
git clone git@github.com:xxx1766/lucky-research.git
cd lucky-research

# install Python helpers (PDF parsing, BibTeX, pandoc shell-outs)
pip install -e ".[dev]"

# (optional) confirm
pytest

# install pandoc system-wide if you plan to use /convert
# macOS:    brew install pandoc
# Ubuntu:   sudo apt install pandoc
```

Open the repo in Claude Code. The slash commands and skills are auto-discovered from
`.claude/` — no extra config needed.

## How a typical session works

```
1. Drop PDFs into inputs/papers/   (or pass an arXiv URL inline)
2. /summarize                      → outputs/summaries/<slug>.md  + AgentDB papers/<slug>
3. /idea-check horizontal: <idea>  → outputs/idea-checks/<idea>-horizontal.md
4. /draft outline: <idea>          → outputs/drafts/<paper>/outline.md
5. /draft section: <paper> intro   → outputs/drafts/<paper>/intro.md
6. /cite                           → outputs/references/<paper>.bib + resolved citation keys
7. /convert outputs/drafts/<paper>/full.md --to=tex
8. /mentor                         → weekly trajectory check-in
```

## What's gitignored vs. shared

| Shared (in git)            | Private per user (gitignored) |
|---|---|
| `.claude/skills/`, `.claude/commands/`, `.claude/agents/` (the plugin) | `inputs/` — your PDFs |
| `src/research_assistant/` (Python helpers) | `outputs/` — your generated summaries, drafts, bibs |
| `pyproject.toml`, `README.md`, `CLAUDE.md` | `ruvector.db` — your AgentDB memory |
| `.claude-flow/CAPABILITIES.md`, `config.yaml` | `.swarm/` — your local swarm runtime state |

## Sharing with friends

Friends clone the repo and follow the Quickstart. Their `inputs/`, `outputs/`, and
`ruvector.db` stay local. To share a paper or idea, commit it to a shared location
elsewhere or copy the `outputs/summaries/<slug>.md` into the repo manually.

## Runtime under the hood

Lucky-research rides on **RuFlo V3** (hierarchical-mesh swarm, AgentDB with HNSW vector
search, ONNX embeddings). Skills read/write AgentDB via the `claude-flow` MCP server
(`memory_store`, `memory_search`). See `.claude-flow/CAPABILITIES.md` for the full
runtime contract.

## Status

**v0.0.1** — scaffold + stub skills. Each `SKILL.md` has the workflow but the prompts
are still TBD. Real skill bodies land feature-by-feature, starting with `lit-summarize`.
