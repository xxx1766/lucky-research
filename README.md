# lucky-research

A Claude Code research-assistant plugin covering the whole paper loop — read papers,
validate ideas, design + run experiments, draft sections, manage refs/figures/pseudocode,
track your trajectory over time, and migrate the whole workspace across machines.

> **Full slash-command surface (every subcommand, every flag): see [`HELP.md`](./HELP.md).**

## Capabilities at a glance

| Slash | Skill / agent | What it does |
|---|---|---|
| `/summarize`   | `lit-summarize`            | Summarize PDFs (`inputs/papers/*.pdf`) or arXiv URLs into structured markdown; index in AgentDB `papers/`. |
| `/idea-check`  | `idea-validate`            | 6-stage Socratic flow (`socratic → scout → evaluate → venues → knowledge → handoff`) plus two micro-flows (`brainstorm` at 1.5, `contrarian` at 2.5). Legacy `horizontal` / `vertical` modes still supported. |
| `/scout-swarm` | `research-swarm` (optional)| Optional ruflo accelerator — parallelize `/paper scout` with a researcher swarm. Degrades to "use `/paper scout`" when swarm tools are absent. |
| `/paper`       | `paper-architect`          | Venue-rooted, multi-stage paper flow (`venue → direction → bind → scout → focus → motivate → write → render → humanize → review → verify → status → archive`) under `outputs/papers/<venue>/<direction>/`. `verify` runs a 3-pass evidence-closure audit (Evidence → Argument → Style) and builds a typed debt ledger surfaced on the status board. |
| `/cite`        | `ref-manager`              | Scan LaTeX `\cite{...}` keys and merge BibTeX into `<direction>/refs.bib`. |
| `/convert`     | `ref-manager`              | Markdown ↔ LaTeX ↔ docx via pandoc. |
| `/mentor`      | `research-mentor`          | Weekly check-in vs goals · per-project research-notes triplet (state / log / findings) · past-work + boss subroutes. |
| `/past-work`   | `past-work-historian`      | Curate past projects under `inputs/past-work/<slug>.md`; bind/clone the source repo for `/paper direction` recall. |
| `/boss`        | `boss-historian`           | Group-PI profile + per-meeting notes + pre-report rehearsals under `inputs/boss-profile/`. Alias for `/mentor boss …`. |
| `/experiment`  | `experiment-runner`        | Bind each experiment to one GitHub repo (URL + branch + SHA), record semver versions (env · pip freeze · commit · result mirror), register external artifacts, run advisory feasibility, analyze results. |
| `/figure`      | `figure-tool`              | Structural SVG (architecture / pipeline / concept) or matplotlib data plots, scoped to current paper or experiment. Read-only `/figure recommend` chart-type picker; a curated reference-figure library; evidence-first (never plot fabricated data, unconfirmed architecture nodes flagged `[VERIFY_ARCH]`) + a data-plot QA checklist (no rainbow colormaps, grayscale-safe, error-bar type stated). |
| `/pseudocode`  | `pseudocode-tool`          | LaTeX algorithm pseudocode (`algorithm + algpseudocode`, or `algorithm2e`) with notation linting, scoped like `/figure`. |
| `/migrate`     | `migrate-tool`             | Bundle per-user state (`inputs/`, `outputs/`, `ruvector.db`, `.swarm/memory.db`, `.claude`) into a zip; AES-encrypt optional; never overwrites on import. `reindex` rebuilds AgentDB from on-disk truth. |

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
1.  Drop PDFs into inputs/papers/   (or pass arXiv URL inline)
2.  /summarize                      → outputs/summaries/<slug>.md + AgentDB papers/
3.  /idea-check "<free-text>"       → Socratic → brainstorm → scout → contrarian →
                                       evaluate → venues → knowledge → handoff
                                       (sets the /paper cursor)
4.  /paper venue OSDI-2027          → outputs/papers/OSDI-2027/_venue.md
                                       (optionally `cp -r docs/venues/OSDI/2027/* .`
                                       for the conference _template/ — OSDI/2027/
                                       is the only venue template that ships in-repo;
                                       use any `<CONF>-<YEAR>` slug for venues you
                                       maintain yourself)
5.  /paper direction <slug>         → expert.md + status.md
6.  /experiment init                → outputs/experiments/<slug>/manifest.md
                                       (or /paper bind to an existing experiment)
7.  /paper scout                    → <direction>/related-papers/*.md
8.  /experiment design + feasibility + version add + analyze
                                    → versions/<vN.M>.md + results/<latest>/analysis.{tex,md}
9.  /paper focus → motivate         → focused-problem.md + experiments/{motivation,benchmark}.md
10. /figure new <slug>              → <scope>/figures/<slug>.{svg,pdf,note.md}
                                       (matplotlib data plots: <slug>.{py,pdf,png,note.md})
11. /pseudocode new <slug>          → <scope>/algorithms/<slug>.{tex,pdf,note.md}
12. /paper write [section]          → outline.md (no section) OR sections/<section>.tex
                                       + auto-rendered main.pdf
13. /cite                           → <direction>/refs.bib
14. /paper humanize + review + verify → reviews/{humanize,review,verify-*}-<date>.md
                                       (verify computes a pass/fail/blocked verdict
                                        from open hard debts; a 3-round cap)
15. /paper archive                  → inputs/past-work/<slug>/paper/  (when done)
16. /mentor                         → weekly check-in vs goals
17. /migrate export                 → outputs/migrate/migrate-<host>-<ts>.zip
                                       (restore on a new machine with /migrate import)
```

> Every `/paper` subcommand ends with a one-line progress footer
> (`── <venue> / <direction>  [######-] 6/7  ⚠ 2 debts  next: /paper render ──`); run
> `/paper status` for the full multi-line board (also persisted to
> `<direction>/status.md`). The `⚠ N debts` marker rolls up open evidence-first
> placeholders + unresolved `\cite{}` keys; `/paper status` breaks them down by
> class on a `debts:` line (citation / figure / evidence / consistency / prose).

### Evidence-first discipline (the anti-fabrication spine)

`/paper write`, `/paper verify`, and `/figure` share one rule: **never fabricate
a citation, a number, a result, or an architecture edge.** When support is not
yet on hand, the draft carries an explicit placeholder token
(`[REF_NEEDED]` / `[FIGURE_NEEDED]` / `[DATA_NEEDED]` / `[CLAIM_UNVERIFIED]`;
figures use `[VERIFY_ARCH]`) instead of an invented fact. Each gap is tracked as
a **debt** that a later stage closes:

- **`/paper write` is gated** — a preflight check blocks drafting until its
  prerequisites exist (`_venue.md`, `focused-problem.md`; scouted literature for
  intro/related-work), with a `--force` escape.
- **`/paper verify`** runs three ordered passes (Evidence → Argument → Style,
  no skipping), including a claim-strength audit that flags over-strong wording
  (significant / robust / SOTA / …) lacking the evidence it implies. It writes a
  typed `VerificationReport` whose verdict (`passed` / `failed` / `blocked`) is
  computed from the open hard debts, with a 3-round cap.
- **`/paper venue`** tags every requirement fact with provenance
  (`(src: <url> @ <date>)` / `unverified` / `unknown`) so a guessed deadline can
  never masquerade as confirmed.

## How the commands chain together

```
inputs/papers/*.pdf  ──┐
arXiv URL / DOI      ──┴──▶ /summarize ──▶ outputs/summaries/<slug>.md  + AgentDB papers/
                                                       │
                                                       ▼
                                          /idea-check  (socratic → brainstorm → scout →
                                                        contrarian → evaluate → venues →
                                                        knowledge → handoff)
                                                       │
                                                       ▼
                                          /paper       (venue → direction → bind →
                                                        scout → focus → motivate →
                                                        write → render → humanize →
                                                        review → verify → status →
                                                        archive)
                                                       │
                                                       │     ╔════════════════════╗
                                                       ├────▶║ /experiment        ║
                                                       │     ║ init → design →    ║
                                                       │     ║ feasibility →      ║
                                                       │     ║ version add →      ║
                                                       │     ║ analyze            ║
                                                       │     ╚════════════════════╝
                                                       │              │
                                                       │              ▼
                                                       │     /figure new, /pseudocode new
                                                       │              │
                                                       ▼              ▼
                                          /cite + /convert   (used by /paper write+render)
                                                       │
                                                       ▼
                                          /mentor      (weekly checkin · research-notes ·
                                                        past-work · /boss prep)
                                                       │
                                                       ▼
                                          /migrate     (cross-machine transfer)
```

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
| `.claude/skills/`, `.claude/commands/`, `.claude/agents/` (the plugin) | `inputs/` — your PDFs, past-work, boss-profile, figure-refs |
| `src/research_assistant/` (Python helpers) | `outputs/` — your summaries, drafts, papers, experiments, figures, migrate zips |
| `pyproject.toml`, `README.md`, `HELP.md`, `CLAUDE.md` | `ruvector.db` — your AgentDB memory |
| `docs/` — templates, venue library, design specs | `.swarm/` — your local swarm runtime state |
| `.claude-flow/CAPABILITIES.md`, `config.yaml` | `.claude-flow/logs/`, `sessions/`, `metrics/` |

Cross-machine transfer is handled by `/migrate`: zip the private side on one machine,
unzip on the next — collisions never overwrite (renamed to `*.from-migrate-<ts>.*`).
Most AgentDB namespaces are rebuilt from on-disk truth via `/migrate reindex` after
import; `papers/<slug>` rebuilds via `/summarize` and `project/figure-refs` via
`/figure ref sync`. AES-256 encryption is opt-in (`--encrypt --passphrase-env VAR`).

## Sharing with friends

Friends clone the repo and follow the Quickstart. Their `inputs/`, `outputs/`, and
`ruvector.db` stay local. To share a paper or idea, commit it to a shared location
elsewhere or copy the `outputs/summaries/<slug>.md` into the repo manually.

## Runtime under the hood

Lucky-research rides on **RuFlo V3** (hierarchical-mesh swarm, AgentDB with HNSW vector
search, ONNX embeddings). Skills read/write AgentDB via the `claude-flow` MCP server
(`memory_store`, `memory_search`). See `.claude-flow/CAPABILITIES.md` for the full
runtime contract.

### What's project-specific vs. framework

A clean way to read `.claude/` when first cloning:

| Location | Who owns it | Count |
|---|---|---|
| `.claude/commands/*.md` (top-level) | **project** — 13 slash entry points | 13 |
| `.claude/commands/{analysis,automation,github,hooks,monitoring,optimization,sparc}/` | framework — RuFlo V3 defaults | ~80 |
| `.claude/skills/{lit-summarize,idea-validate,research-swarm,paper-architect,ref-manager,research-mentor,experiment-runner,figure-tool,pseudocode-tool,migrate-tool}/` | **project** — 10 skills behind the slash commands | 10 |
| `.claude/skills/<everything else>/` (agentdb-*, github-*, sparc-*, swarm-*, v3-*, …) | framework — RuFlo V3 defaults | ~30 |
| `.claude/agents/{boss-historian,past-work-historian}.md` (top-level) | **project** — 2 domain agents the research-mentor and past-work skills hand off to | 2 |
| `.claude/agents/<subdirs>/` (analysis/, swarm/, v3/, …) | framework — RuFlo V3 defaults | ~50+ |

If you're reading code to understand "what does lucky-research do", focus on the
**project** rows. The framework rows are general-purpose plumbing the runtime
ships with — they're available for anyone who wants them but they're not part of
the research-assistant per se.

## Status

All 13 slash commands have working skill bodies and deterministic Python helpers
with test coverage. The plugin is in daily use; the audit log lives at the top of
`CLAUDE.md` and in commit history. Known sharp edges and advertised-but-unimplemented
subcommands are flagged inline in [`HELP.md`](./HELP.md) (look for the ⚠️ marks).
