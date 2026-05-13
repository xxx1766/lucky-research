# lucky-research

A Claude Code research-assistant plugin. Five slash commands cover the full paper-writing
loop — read papers, validate ideas, draft sections, manage references, and track your
research trajectory over time.

## Five MVP capabilities

| Slash command | Skill | What it does |
|---|---|---|
| `/summarize`  | `lit-summarize`    | Summarize papers (`inputs/papers/*.pdf` or arXiv URLs) into structured markdown; index in AgentDB `papers/`. |
| `/idea-check` | `idea-validate`    | Validate an idea via horizontal comparison (related-work matrix) or vertical lineage trace. |
| `/paper`      | `paper-architect`  | Venue-rooted, multi-stage paper flow (`venue → direction → scout → focus → motivate → write`). Organizes everything under `outputs/papers/<venue>/<direction>/`. |
| `/cite`       | `ref-manager`      | Resolve `[@cite:slug]` placeholders, emit BibTeX, manage `outputs/references/*.bib`. |
| `/convert`    | `ref-manager`      | Convert Markdown ↔ LaTeX ↔ docx via pandoc. |
| `/mentor`     | `research-mentor`  | Weekly check-in: compare recent activity against your stated research goals and surface path corrections. |
| `/past-work`  | `past-work-historian` (agent) | Curate past projects under `inputs/past-work/<slug>.md` (template at `docs/past-work-template.md`). Subcommands: `list`, `add`, `sync`. Surfaces relevant prior work during `/paper direction`. |
| `/boss`       | `boss-historian` (agent) | Track your group PI: profile + per-meeting notes + pre-report rehearsals under `inputs/boss-profile/` (templates at `docs/boss-profile-template.md`, `docs/boss-meeting-template.md`, `docs/boss-report-template.md`, `docs/boss-rehearsal-template.md`). Subcommands: `show`, `edit`, `meeting`, `rehearse`, `sync`. `/boss show` prints profile + last 3 meetings as pre-report prep. `/boss rehearse` runs a multi-turn mock Q&A against report material under `inputs/boss-profile/reports/` and saves the transcript to `inputs/boss-profile/rehearsals/`. |
| `/experiment` | `experiment-runner` | Bind each experiment to a single GitHub repo (URL + branch + SHA tracked, optional `git clone --depth 1`). Record versioned execution attempts (semver — `v1.0`, `v1.1`, `v2.0` ...) with full env snapshot for reproducibility/rebuttal (host · GPU · CUDA · Python · library lockfile · random seeds · bound-repo commit). Mirror the structured result file from the bound repo into local storage so `/paper` can pull it at write time. Subcommands: `init`, `scout`, `design`, `sync`, `clone`, `version add/list`, `data add/list`, `analyze`, `status`, `list`, `show`. Templates under `docs/experiment-*-template.md`; tree under `outputs/experiments/<slug>/`. |

> Post-MVP (not yet implemented): 科研绘图.

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
4. /paper venue NeurIPS-2026       → outputs/papers/NeurIPS-2026/{_venue.md, _template/}
                                     (drop conference .sty/.cls into _template/)
5. /paper direction <slug>         → outputs/papers/<venue>/<direction>/expert.md
6. /paper scout                    → <direction>/related-papers/*.md (+ AgentDB papers/)
7. /paper focus                    → <direction>/focused-problem.md
8. /paper motivate                 → <direction>/experiments/{motivation,benchmark}.md
9. /paper write [section]          → <direction>/outline.md (no section) OR
                                     <direction>/sections/<section>.tex + auto-render
                                     of <direction>/main.pdf via tectonic
9b. /paper render                  → re-render <direction>/main.pdf without writing
10. /cite                          → <direction>/refs.bib (in paper context) OR
                                     outputs/references/<paper>.bib (Markdown drafts)
11. /convert <draft.md> --to=tex
12. /mentor                        → weekly trajectory check-in
```

> Every `/paper` subcommand ends with a one-line progress footer
> (`── <venue> / <direction>  [######-] 6/7  next: /paper render ──`); run
> `/paper status` for the full multi-line board (also persisted to
> `<direction>/status.md`).

## Updating an in-flight project

The progress visualizer and any other plugin update activate purely through
`git pull` — no reinstall, no Claude Code restart:

```bash
git pull                          # pulls new code, skill prompts, slash commands
# pip install -e ".[dev]" only if you've never installed (editable mode picks up
# src/research_assistant/ changes automatically thereafter)
```

Then inside Claude Code:

```
/paper status                            # works immediately if your cursor is fresh
/paper status OSDI-2027/my-direction     # target an existing folder and seed cursor
/paper status --all                      # refresh status.md across every direction
```

If `/paper status` (no args) prints "no current paper" but `outputs/papers/` already
has work in it, your AgentDB cursor is stale — run the second form once. It's
idempotent: it reads files only, writes `<direction>/status.md`, and adopts the
direction as the new cursor without touching `expert.md` or any other artifact.

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
