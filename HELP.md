# lucky-research — Slash command reference

This file is the authoritative list of every slash command, every subcommand, and
what each one does. Use it as a cheat sheet inside Claude Code.

Format:
```
/<verb> <subcommand> [args]              # purpose
   ↳ backed by  src/research_assistant/<module>:<symbol>
   ↳ writes     <output path>
   ↳ AgentDB    <namespace>
```

Glossary:
- **cursor** — `(venue, direction)` for paper work, `slug` for experiment work,
  stored in AgentDB `project/paper-context.current` and
  `project/experiment-context.current`.
- **direction** — `outputs/papers/<venue>/<direction>/`.
- **slug** — kebab-case identifier; slug regex enforced inside helpers.

---

## 📄 `/summarize` — read papers (skill: `lit-summarize`)

| Form | Purpose |
|---|---|
| `/summarize` | Summarize every PDF under `inputs/papers/` not yet in `outputs/summaries/`. |
| `/summarize <arXiv URL \| arXiv id \| DOI \| PDF path>` | Summarize one source. arXiv inputs are downloaded into `inputs/papers/` first. |

- Backed by `lit/__init__.py:extract_pdf_text + parse_metadata`, and `lit/__init__.py:fetch_arxiv` for arXiv.
- When the input is a DOI (or a PDF carries one in its metadata), also calls
  `lit/publisher_bibtex.py:fetch_bibtex_from_publisher(doi)` to fetch canonical
  BibTeX — CrossRef → doi.org content negotiation → CloakBrowser fallback.
  The BibTeX is stashed in the AgentDB payload so `/cite` doesn't need a
  second network round-trip later.
- Writes `outputs/summaries/<slug>.md`.
- AgentDB `papers/<slug>` (text + metadata, optional BibTeX in `metadata.bibtex`).
- Structured-markdown render is done Claude-side, not in Python.

---

## 💡 `/idea-check` — validate an idea (skill: `idea-validate`)

A 6-stage Socratic flow (`socratic → scout → evaluate → venues → knowledge →
handoff`) plus two interstitial micro-flows (`brainstorm` 1.5 and `contrarian`
2.5). State is mirrored on disk **and** in AgentDB.

| Subcommand | Purpose |
|---|---|
| `/idea-check` | Show the vault `_index.md` + status of the active idea. |
| `/idea-check "<free-text>"` | **Stage 1** — Socratic capture. Creates the idea folder + manifest. |
| `/idea-check socratic` | Re-enter Stage 1 for the active idea. |
| `/idea-check brainstorm [<situation>]` | **Stage 1.5** — F1–F11 ideation frameworks; may spawn variant ideas. |
| `/idea-check scout` | **Stage 2** — last-3-years arXiv scout + gap consolidation. Auto-triggers 2.5. |
| `/idea-check contrarian [<slug>]` | **Stage 2.5** — 4-question contrarian micro-flow; may spawn `<slug>-contrarian`. |
| `/idea-check evaluate` | **Stage 3** — value/feasibility rubric + pre-registration. |
| `/idea-check venues` | **Stage 4** — venue ranking by fit score. |
| `/idea-check knowledge` | **Stage 5** — brain-library study plan. |
| `/idea-check handoff` | **Stage 6** — confirm + set the `/paper` cursor. |
| `/idea-check status` | Render the 6-stage board for the active idea. |
| `/idea-check list` | Print `outputs/idea-checks/_index.md`. |
| `/idea-check show <slug>` | Print one manifest + status. |
| `/idea-check horizontal <free-text>` | Legacy horizontal comparison matrix (no colon — space-separated). |
| `/idea-check vertical <slug>` | Legacy vertical lineage trace (no colon — space-separated). |

- Per-idea folder: `outputs/idea-checks/<slug>/{idea.md, socratic.md, brainstorm.md, scout.md, contrarian.md, evaluate.md, venues.md, knowledge.md, status.md}`.
- AgentDB: `ideas/<slug>`, `ideas/<slug>/{socratic,brainstorm,scout,contrarian,evaluation,venues,knowledge}`, cursor `project/idea-context.current`, handoff `project/paper-context.current`.
- Helpers: `ideas/{socratic, brainstorm, scout, contrarian, evaluate, venues, knowledge, registry, slug, status}.py`.


---

## 🐝 `/scout-swarm` — parallel paper scout (skill: `research-swarm`)

| Form | Purpose |
|---|---|
| `/scout-swarm <topic>` | Decompose topic into 3–6 sub-areas, fan out `researcher` agents. |
| `/scout-swarm` | Same flow using the current `(venue, direction)` cursor. |

- Gracefully degrades to "use `/paper scout`" when ruflo swarm tools are unavailable.
- Backed by `lit/sourcing.py:search_for_direction` (venue-aware: arXiv + OpenReview).
- Writes per-paper summaries under `<direction>/related-papers/<slug>.md`.
- AgentDB `papers/<slug>`.

---

## 📝 `/paper` — venue-rooted paper flow (skill: `paper-architect`)

The biggest command surface. All paths are `outputs/papers/<venue>/<direction>/`.

| Subcommand | Purpose |
|---|---|
| `/paper venue <slug>` | Create/edit venue folder + `_venue.md`. Optional: bootstrap from `docs/venues/<CONF>/<YEAR>/_template/`. |
| `/paper venue refs add <pdf-or-arxiv>...` | Ingest reference papers from the venue → `_venue-refs/<slug>.md`. |
| `/paper venue refs list` | Table of ingested refs. |
| `/paper venue refs distill` | Re-distill the `## Writing conventions` block in `_venue.md`. |
| `/paper direction <slug>` | Scope a new direction; draft `expert.md`. |
| `/paper bind <experiment-slug> [--force]` | Move direction into the bound experiment's git repo + symlink back. |
| `/paper unbind [--keep-files]` | Remove the bind symlink. |
| `/paper sync [-m "<msg>"]` | `git add+commit+push` inside the bound experiment repo. |
| `/paper restore [<v>/<d>] [--all]` | Recreate symlinks from already-cloned experiment repos. |
| `/paper scout` | Source related papers + surface bound experiments. |
| `/paper focus` | Narrow to a focused problem (`focused-problem.md`). |
| `/paper motivate` | Design motivation experiment + benchmark. |
| `/paper write [section]` | Draft `outline.md` or `sections/<section>.tex`; auto-renders `main.pdf`. |
| `/paper render` | Re-render `main.pdf` only. |
| `/paper humanize [<section>] [--dry-run]` | Strip AI-tone from `.tex`; saves audit to `reviews/`. |
| `/paper review [--target <venue>]` | Reviewer-perspective audit of `main.pdf` → `reviews/`. |
| `/paper status [<v>/<d>] [--all]` | Print + persist 7-stage progress board to `status.md`. |
| `/paper archive [<v>/<d>] [--abandoned]` | Move finished paper to `inputs/past-work/<slug>/paper/`. |
| `/paper unarchive <slug>` | Reverse archive. |
| `/paper archive list` | Table of archived papers. |

- Per-direction artifacts: `expert.md, focused-problem.md, related-papers/, experiments/{motivation,benchmark}.md, outline.md, main.tex, sections/*.tex, refs.bib, main.pdf, status.md, reviews/`.
- Helpers: `papers/{__init__, _sync, binding, archive, _archive_extract, venue_refs, venue_merge, venue_conventions, venue_family, related_experiments}.py`.
- AgentDB: `papers/venue-style/<venue>/<paper>`, `drafts/<venue>/<direction>`, cursor `project/paper-context.current`, bindings `project/paper-bindings.<v>__<d>`.
- LaTeX render via `refs/__init__.py:render_latex` (tectonic → latexmk → xelatex → pdflatex).

---

## 📚 `/cite` — BibTeX resolution (skill: `ref-manager`)

| Form | Purpose |
|---|---|
| `/cite` (paper cursor set) | Scan `main.tex + sections/*.tex` for `\cite{slug}` keys and merge entries into `<direction>/refs.bib`. |
| `/cite <venue>/<direction>` | Adopt that cursor first, then proceed as above. |

- Backed by `refs/__init__.py:scan_tex_cite_keys + merge_bibtex`.
- Reads AgentDB `papers/<slug>` for arXiv id / DOI / authors / year.
- **DOI fallback for missing slugs**: when a `\cite{slug}` has no AgentDB
  entry but a DOI is known, calls
  `lit/publisher_bibtex.py:fetch_bibtex_from_publisher(doi)` which tries
  CrossRef → doi.org content negotiation → CloakBrowser stealth fallback
  (last tier needs `pip install -e ".[crawl]"`). The fetched entry is then
  cached back into AgentDB `papers/<slug>` for next time.

---

## 🔁 `/convert` — pandoc conversion (skill: `ref-manager`)

| Form | Purpose |
|---|---|
| `/convert <source-path> --to=<tex\|md\|docx>` | Pandoc-driven conversion; output sits next to source. |

- Backed by `refs/__init__.py:convert_document` (pypandoc).
- Supports any pair from `{markdown, latex, docx}`.

---

## 🧭 `/mentor` — research trajectory (skill: `research-mentor`)

| Subcommand | Purpose |
|---|---|
| `/mentor` | Weekly check-in. Diff goals vs activity → `outputs/mentor/checkin-<date>.md`. |
| `/mentor set-goals` | Interactive (re)write of long-term goals. |
| `/mentor add-past-work [<title>]` | Quick-capture an old project mid-checkin. Bypasses the `past-work-historian` agent. |
| `/mentor project init <title>` | Bootstrap a research-notes triplet (state / log / findings). |
| `/mentor project list` | List all research-notes projects. |
| `/mentor project show [<slug>]` | Print state + last 5 log rows. |
| `/mentor project log <kind>: <summary>` | Append a log row. `<kind>` ∈ `bootstrap, inner-loop, outer-loop, pivot, report, conclude`. |
| `/mentor project finding <section>: <body>` | Append paragraph under a findings section. |
| `/mentor project sync` | Re-walk every `state.yaml`, index into AgentDB. |
| `/mentor boss …` | Delegates to `boss-historian` (see `/boss` below). |

- Helpers: `mentor/{__init__, past_work, past_work_capture, boss_profile, research_notes}.py`.
- AgentDB: `project/checkins/<date>`, `project/research-notes/<slug>`, `project/research-notes-context.current`, `project/goals`.

> ⚠️ Known issues: none material — `/mentor set-goals` is pure prompt-driven (no Python helper needed; SKILL "Goal-setting flow" handles it).

---

## 🗂️ `/past-work` — curate past projects (agent: `past-work-historian`)

| Subcommand | Purpose |
|---|---|
| `/past-work` / `/past-work list` | Table of entries (with bound repo / clone status). |
| `/past-work add` | Interactive long-form capture → `inputs/past-work/<slug>.md`. |
| `/past-work sync` | Re-walk + upsert AgentDB. |
| `/past-work bind <slug> <url> [--branch <b>]` | Bind a GitHub repo to the entry. |
| `/past-work clone [<slug>] [--force]` | Clone the bound repo. |
| `/past-work sync-repo <slug>` | `git ls-remote` only (no pull). |
| `/past-work pull <slug>` | Pull the cloned repo. |
| `/past-work unbind <slug> [--keep-clone]` | Remove the binding. |

- Helpers: `mentor/past_work.py`.
- AgentDB `project/past-work/<slug>`.
- Template: `docs/past-work-template.md`.

---

## 👔 `/boss` — group PI tracking (agent: `boss-historian`)

Alias for `/mentor boss …`. Both routes load the same agent.

| Subcommand | Purpose |
|---|---|
| `/boss` / `/boss show` | Print profile + last 3 meetings. |
| `/boss edit` | Interactive profile capture from `docs/boss-profile-template.md`. |
| `/boss meeting [add]` | Capture meeting log from `docs/boss-meeting-template.md`. |
| `/boss rehearse [<report-slug>]` | Multi-turn mock Q&A against a report. Transcript saved as a rehearsal. |
| `/boss sync` | Re-walk + upsert AgentDB. |

- Helpers: `mentor/boss_profile.py`.
- AgentDB `project/boss/profile`, `project/boss/meetings/<date>`.
- Templates: `docs/boss-{profile,meeting,rehearsal,report}-template.md`.

---

## 🧪 `/experiment` — experiment lifecycle (skill: `experiment-runner`)

All paths under `outputs/experiments/<slug>/`. Cursor `project/experiment-context.current`.

| Subcommand | Purpose |
|---|---|
| `/experiment` | `status` if cursor set, else `list`. |
| `/experiment init <title> [--repo <url>] [--paper <slug>]` | Register new experiment; optional repo bind + clone. |
| `/experiment list` | Refresh `_index.md`. |
| `/experiment show <slug>` | Adopt cursor + print preview. |
| `/experiment scout` | Pre-fill `references.md` from bound papers' AgentDB summaries. |
| `/experiment design` | Interactive narrowing → `designs/d<N.M>.md`. Seeded from `/idea-check` hypothesis + metrics. |
| `/experiment feasibility` | Advisory pre-flight → `feasibility-<date>.md` + `inputs/fleet.md`. |
| `/experiment feasibility apply [<file>]` | Adopt suggestion subset → new design version. |
| `/experiment sync` | `git ls-remote` only (network-light). |
| `/experiment clone [<slug>]` | `git clone --depth 1` into `repo/`. |
| `/experiment version add <vN.M> --description "..." [--kind] [--result] [--config] [--seeds] [--metrics] [--notes]` | Register a versioned run; capture env + pip freeze + commit SHA; mirror result file. |
| `/experiment version list` | Semver-sorted table. |
| `/experiment data add <slug> --category --path [...]` | Register a data artifact in `data/index.md`. |
| `/experiment data list [--category]` | Table of registered data. |
| `/experiment artifacts list` | Print `external-artifacts.md`. |
| `/experiment artifacts register --name ... --path ... [--glob --source --repo --revision --size --fetch-cmd]` | Append one external-artifact record. |
| `/experiment artifacts scan [--threshold BYTES]` | Walk experiment files; prompt-register every unregistered ≥ threshold file. |
| `/experiment analyze [<vN.M>...]` | Produce `\paragraph{}` block → `results/<latest>/analysis.{tex,md}`. |
| `/experiment status [<slug>]` | Full 5-stage board → `status.md`. |
| `/experiment index [--slug]` | Backfill AgentDB across versions. |

- Helpers: `experiments/{paths, models, parsers, status, repo, registration, env_probe}.py`; `migrate/cli_artifacts.py` for `artifacts ...`.
- AgentDB: cursor `project/experiment-context.current`, per-version payloads `experiments/<slug>/<vN.M>`.
- Templates: `docs/experiment-{design,manifest,references,version}-template.md`.

---

## 🎨 `/figure` — research figures (skill: `figure-tool`)

Scoped to current `(venue, direction)` OR experiment slug. Helpers in `figures/`.

| Subcommand | Purpose |
|---|---|
| `/figure` / `/figure list` | Table of figures in the current scope. |
| `/figure new <slug>` | Interactive 6-step flow (intent → kind → refs → size → palette → render). Adds an optional Step 0 (scope) when the cursor is ambiguous. |
| `/figure recommend` | Read-only chart-type recommender. |
| `/figure render <slug>` | Re-export PDF + PNG (or re-run plot script). |
| `/figure render --all` | Batch render every figure in scope. |
| `/figure edit <slug>` | Print absolute path of `<slug>.{svg\|py}` for editing. |
| `/figure export <slug> --format jpeg --quality N` | JPEG export. |
| `/figure ref add [<file>\|--url <URL>]` | Capture a reference image into the figure-ref library. |
| `/figure ref list [--kind] [--tag]` | Table of reference figures. |
| `/figure ref sync` | Re-walk `inputs/figure-refs/` and index into AgentDB. |
| `/figure ref show <slug>` | Print note + image path of one ref. |

- Per-figure files (structural / SVG): `<scope>/figures/<slug>.{svg,pdf,png}` + `<slug>.note.md`.
- Per-figure files (matplotlib data plots): `<scope>/figures/<slug>.{py,pdf,png}` + `<slug>.note.md` (no `.svg`).
- Reference library: `inputs/figure-refs/<slug>/` + `figure-refs/_index.md`.
- AgentDB `project/figure-refs/<slug>`.
- Backends: structural SVG (or D2-scaffolded SVG) for architecture/pipeline/concept figures; matplotlib for data plots.

---

## 🧮 `/pseudocode` — LaTeX algorithm pseudocode (skill: `pseudocode-tool`)

Same cursor model as `/figure`. Helpers in `pseudocode/`.

| Subcommand | Purpose |
|---|---|
| `/pseudocode` / `/pseudocode list` | Table of algorithms in the current scope. |
| `/pseudocode new <slug>` | Interactive 5-step flow (intent → kind → I/O → draft+lint → render+note). Adds an optional Step 0 (scope) when the cursor is ambiguous. |
| `/pseudocode render <slug>` | Compile `<slug>.tex` → `<slug>.pdf`. |
| `/pseudocode render --all` | Batch render all. |
| `/pseudocode check <slug>` | Lint `<slug>.tex` (notation / convention checks). |
| `/pseudocode check --all` | Batch lint. |
| `/pseudocode notation [--grep <term>]` | Print the notation cheat sheet (optionally grepped). |

- Per-algorithm files: `<scope>/algorithms/<slug>.{tex,pdf,note.md}` (paper scope; experiment scope adds a version dimension).
- Notation reference: `.claude/skills/pseudocode-tool/references/notation.md`.
- Engines: `algorithm` + `algpseudocode` (default) or `algorithm2e`.

---

## 📦 `/migrate` — cross-machine state transfer (skill: `migrate-tool`)

All archives live in `outputs/migrate/`.

| Subcommand | Purpose |
|---|---|
| `/migrate export [--out DIR] [--include …] [--threshold BYTES] [--dry-run] [--non-interactive] [--encrypt] [--passphrase-env VAR]` | Scan repo, classify files, interactively register large unregistered experiment files, write `migrate-<host>-<ts>.zip`. AES via pyzipper if `--encrypt`. |
| `/migrate import <archive.zip> [--dry-run] [--passphrase-env VAR]` | Restore. Never overwrites — collisions get `.from-migrate-<ts>.<ext>` suffix; non-empty DBs become `.from-migrate.db`. |
| `/migrate reindex [--namespace NS] [--summary]` | Walk on-disk truth (past-work, experiments, versions, ideas, boss, research-notes) and emit JSONL `{namespace,key,value,metadata}` to stdout for skill-side `memory_store`. |
| `/migrate artifacts list --slug <SLUG>` | Print `external-artifacts.md` for one experiment. |
| `/migrate artifacts register --slug <SLUG> --name ... --path ... [--glob --source --repo --revision --size --fetch-cmd]` | Append one external-artifact record non-interactively. |
| `/migrate artifacts scan --slug <SLUG> [--threshold BYTES]` | Walk one experiment, prompt-register every unregistered ≥ threshold file. |

- Helpers: `migrate/{cli, cli_artifacts, archive, manifest, merge, scan, reindex}.py` (the `_synthesize_fetch_cmd` + `_resolve_passphrase` helpers live inside `cli.py`).
- Output: `outputs/migrate/migrate-<host>-<ts>.zip`; reports under `outputs/migrate/imports/<stem>.report.md`.
- Encryption note: filenames remain plaintext in the central directory (pyzipper limitation).

> ⚠️ Known issues:
> - `/migrate status` is documented in the SKILL but isn't a CLI verb (subparser `required=True`). The skill prompt lists archives itself by reading `outputs/migrate/`.
> - `/migrate reindex` covers `project/past-work`, `project/experiments/<slug>/versions`, `ideas/<slug>` (top-level only), `project/boss/{profile,meetings}`, `project/research-notes`, and `project/checkins`. It does **NOT** rebuild `papers/<slug>` (re-run `/summarize`), the per-stage `ideas/<slug>/{socratic,scout,evaluation,...}` sub-keys (skill-driven), or `project/figure-refs` (re-run `/figure ref sync`).
> - Example: `python -m research_assistant.migrate reindex --namespace project/research-notes --summary` rebuilds just one namespace and prints a one-line count.

---

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
                                                        review → status → archive)
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

---

## Cursors at a glance

| AgentDB key | What it points at | Set by | Read by |
|---|---|---|---|
| `project/paper-context.current` | `{venue, direction}` | `/paper venue`, `/paper direction`, `/idea-check handoff`, `/paper status <target>` | `/paper *`, `/cite`, `/figure`, `/pseudocode`, `/scout-swarm` |
| `project/experiment-context.current` | `{slug}` | `/experiment init`, `/experiment show` | `/experiment *`, `/figure`, `/pseudocode` |
| `project/idea-context.current` | `{slug}` | `/idea-check "<text>"`, `/idea-check show` | `/idea-check *` |
| `project/research-notes-context.current` | `{slug}` | `/mentor project init`, `/mentor project show` | `/mentor project *` |
