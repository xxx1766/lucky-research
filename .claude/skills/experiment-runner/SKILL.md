---
name: experiment-runner
description: Design and run experiments bound to a GitHub repo. Tracks the bound repo's URL + SHA, records versioned execution attempts (semver), and mirrors structured results locally so /paper can consume them when writing. Use when the user wants to design, log, sync, or analyze experiments. Triggered by /experiment.
---

# experiment-runner

> **STATUS**: active. All stage work shipped. `## Open TODOs` at the bottom of this file is currently empty — add new items there as scope shows up.

## Mental model

Each experiment lives at `outputs/experiments/<slug>/`, gitignored. The bound GitHub
repo is the cross-machine truth for code and large data; this plugin is the **control
center** that records what was tried, on what hardware, with what result. Stages can
be revisited in any order, but later stages assume earlier ones are non-empty.

```
init → scout → design → feasibility ↔ feasibility apply → version add (loops) → analyze
                                                      │
                                      ┌── sync / clone (orthogonal: repo state)
                                      └── data add / data list (orthogonal: artifact registry)
```

`feasibility` is advisory — it writes a dated `feasibility-<date>.md` with a
suggestion list. `feasibility apply` is the only path that mutates the design,
and it does so by writing a **new** `designs/d<N.M>.md` (the prior design is
preserved). So the loop `design → feasibility → feasibility apply → design'`
accumulates an audit trail of plan revisions.

The "current experiment" is a single `slug` stored in AgentDB
`project/experiment-context`. Every stage reads it; `init` and `show` write it.

## References (load on demand)

Stable, detail-heavy content lives in `references/` so this SKILL stays scan-
nable. Each entry below names the file, what it contains, and the stage that
pulls it in:

| File | Contents | Loaded by |
|---|---|---|
| `references/design-workflow.md` | Stage 3 full step-by-step: target-version pick, idea-handoff pre-fill (hypothesis tree via `socratic.to_experiment_hypothesis_seed`, pre-registration via `evaluate.to_experiment_metrics_seed`), interactive narrowing prompts, template rendering, optional hypothesis tree convention. | Stage 3 (`/experiment design`) |
| `references/feasibility-workflow.md` | Stage 3.5 + 3.6 step-by-step: merged fleet snapshot (auto `infer_fleet_from_versions` + manual `inputs/fleet.md`), gap-detection prompts that persist to `inputs/fleet.md`, LLM verdict / blockers / suggestions schema, report file shape; plus 3.6's adopt-bump-write flow with the `derived_from`/`feasibility_source`/`adopted_suggestions` audit-trail contract and the preserve-verbatim invariant on Research-Question / Hypothesis / Success-criteria. | Stages 3.5 & 3.6 (`/experiment feasibility[ apply]`) |
| `references/artifacts-workflow.md` | Stage 6.5 full step-by-step: list / register / scan CLI shapes, the `--fetch-cmd` synthesis ladder per `--source` (hf, http, git-lfs, s3, other), the shell-out target (`python -m research_assistant.migrate artifacts ...`), composition with `/migrate export`'s exclude-and-record-fetch-cmd flow. | Stage 6.5 (`/experiment artifacts {list,register,scan}`) |
| `references/analyze-prompt.md` | Verbatim "实验分析" prompt prelude (adapted from awesome-ai-research-writing). Two-part response format (`Part 1 [LaTeX]` with `\paragraph{Title Case Conclusion}` blocks, no `\textbf`/`\emph`; `Part 2 [Translation]` Chinese). | Stage 7 (`/experiment analyze`) |

## Progress display

Every `/experiment` subcommand ends by printing a **one-line progress footer** so the
user always knows which stage they're at. `/experiment status` prints the full
multi-line **board** and persists it to `<slug>/status.md`.

Both visualizations come from pure helpers in `research_assistant.experiments` — they
take `(slug, ExperimentStatus)` and return a Markdown string. The skill body just
prints what they return.

```
# footer (after any /experiment subcommand)
── llm-finetune-eval   [####-] 4/5   next: /experiment analyze ──

# board (from /experiment status)
llm-finetune-eval
[####-] 4/5 stages

  [x] 1. init       manifest.md ok · repo set · cloned
  [x] 2. scout      references.md filled
  [x] 3. design     design.md ok
  [x] 4. version    3 version(s) · latest v2.0
  [ ] 5. analyze    need ≥2 versions

Last sync: 2026-05-13T08:12:04
Suggested next: /experiment analyze
```

The 5-stage bar counts `init / scout / design / version / analyze`. Use `[x]` done /
`[.]` partial / `[ ]` empty. **Scout auto-completes when no papers are bound** — the
references matrix only makes sense when there are papers to compare against.

`feasibility` is orthogonal to the bar (like `sync` and `clone`), but `stage_status`
populates `last_feasibility_check` from the newest `feasibility-<date>.md`'s mtime;
the board prints it under "Last feasibility:". `next_suggested` inserts
`/experiment feasibility` between design-done and first-version-add when no
feasibility report exists yet.

Helpers (all in `research_assistant.experiments`):

- `stage_status(slug) -> ExperimentStatus` — inspect a slug's folder.
- `render_progress_footer(slug, status) -> str` — one-line footer.
- `render_progress_board(slug, status) -> str` — full Markdown board.
- `next_suggested(status) -> str` — the next-step command shown in both renders.

## Directory layout this skill owns

```
outputs/experiments/
  _index.md                            ← auto-rebuilt registry (slug | status | versions | last_sync | last_feasibility)
  <slug>/
    manifest.md                        ← YAML frontmatter + body (see docs/experiment-manifest-template.md)
    designs/<dN.M>.md                  ← versioned design plans (d1.0, d1.1, d2.0 ...; latest is current)
    references.md                      ← comparison matrix from /experiment scout
    feasibility-<YYYY-MM-DD>.md        ← dated, collision-suffixed feasibility reports
    status.md                          ← auto-generated progress board
    versions/<vN.M>.md                 ← per-version record (YAML frontmatter + body)
    results/<vN.M>/...                 ← mirrored result files from the bound repo
    data/index.md                      ← data artifact registry
    configs/<vN.M>.requirements.txt    ← full pip freeze, written on version add
    repo/                              ← OPTIONAL, gitignored, only if user opted in to clone

inputs/fleet.md                        ← user-maintained fleet manifest (template: docs/fleet-template.md)
```

## Stage 1 — `/experiment init <title>`

**Inputs**
- `<title>` from user (e.g. `"LoRA finetune evaluation"`).
- Optional: `--repo <git-url>` + `--paper <paper-slug>` (repeatable) flags.

**Workflow**
1. `slug = slugify_experiment(title)`; if `outputs/experiments/<slug>/` already exists,
   call `next_available_slug(slug)` (collision-suffix `-2`, `-3`, ...).
2. If `--repo` not given, ask the user for the bound GitHub repo URL + branch
   (plain text, no AskUserQuestion — per the `feedback_decision_ui` memory).
3. **Plain-text Y/N: "Clone the repo locally now? [y/N]"**. If yes, call
   `clone_repo(slug, url, branch)`; set `manifest.repo.clone_status = "cloned"`.
   If no, leave at `"tracked"` and remind the user `/experiment clone <slug>` is the
   later opt-in.
4. Render `docs/experiment-manifest-template.md` with the user's title + repo +
   papers + today's date; write to `outputs/experiments/<slug>/manifest.md`.
5. Set the cursor:
   `mcp__claude-flow__memory_store(namespace="project/experiment-context",
   key="current", value={slug: <slug>})`.
6. Refresh `outputs/experiments/_index.md`.
7. Print `render_progress_footer(slug, stage_status(slug))`.

## Stage 2 — `/experiment scout`

**Inputs**
- Current `slug`; bound paper slugs from `manifest.papers`.

**Workflow**
1. For each bound paper slug:
   - `mcp__claude-flow__memory_retrieve(namespace="papers", key=<slug>)`.
2. Ask the LLM to extract `(trace, platform, metrics, code-availability, notes)` for
   each paper from its summary.
3. Render `docs/experiment-references-template.md`; pre-fill one row per paper;
   write to `outputs/experiments/<slug>/references.md`. Tell the user to edit freely.
4. Print `render_progress_footer(slug, stage_status(slug))`.

## Stage 3 — `/experiment design`

**Inputs**: current `slug`; `references.md` if present; optionally a bound
paper-cursor (`project/paper-context.current`) whose `direction` is an idea
slug (set by `/idea-check handoff`).

**Workflow** — full detail in `references/design-workflow.md`. High-level:

1. Resolve target design version (first run → `d1.0`; otherwise prompt user
   for minor vs major, mapping to `next_design_version(slug, kind)`).
2. **Pre-fill from a bound idea, if one exists.** Read `ideas/<direction>/{socratic,evaluation}`
   and seed `## Hypothesis` via `socratic.to_experiment_hypothesis_seed(trace)`
   and `## Metrics`/`## Success criteria` via
   `evaluate.to_experiment_metrics_seed(ev)`. Either may be `None`/empty —
   fall through to the interactive prompts.
3. **Interactive narrowing** for whatever wasn't pre-filled — RQ (always
   ask, narrower than the idea's question), hypothesis, baselines from
   `references.md`, metric + success criteria.
4. Render `docs/experiment-design-template.md` and write to
   `design_version_path(slug, version)` with frontmatter (`design_version`,
   `created_at`, `derived_from`, `feasibility_source: null`,
   `adopted_suggestions: []`).
5. **Optional hypothesis tree** — `H1 / H1.1 / H1.2` shape if it decomposes
   naturally. Notational only; `/experiment feasibility` treats `## Hypothesis`
   as one preserved block regardless of internal structure.
6. Print `render_progress_footer(slug, stage_status(slug))`.

## Stage 3.5 — `/experiment feasibility`

Advisory-only — **no mutation to design files in this stage.** Writes a
dated `feasibility-<date>.md` carrying an LLM verdict + suggestion list
that the user can sleep on before adopting.

**Inputs**: current `slug`; `latest_design_path(slug)`; `references.md`
(optional); merged fleet snapshot.

**Workflow** — full detail in `references/feasibility-workflow.md`.
High-level:

1. Build the merged fleet picture: `infer_fleet_from_versions()` (auto)
   ∪ `parsers.parse_fleet(inputs/fleet.md)` (manual). Manual wins on
   hostname collisions.
2. **Gap detection** — plain-text prompts when fleet is empty / a machine
   mentioned in chat is absent / GPU info missing. Persist every answer
   **immediately** to `inputs/fleet.md` before the LLM call.
3. LLM produces `verdict ∈ {feasible, tight, infeasible}` + `blockers` +
   `suggestions` (each with `id` / `axis` / `change` / `rationale` /
   `cost` — see references for the full `axis` enum).
4. Write `feasibility_path(slug, today)` (collision-safe). Body sections:
   `## Verdict`, `## Blockers`, `## Suggestions` (one `### S<id>` each),
   `## Fleet snapshot`, `## Next step`.
5. Refresh `_index.md` + `status.md`. Print summary + footer.

## Stage 3.6 — `/experiment feasibility apply [<feasibility-file>]`

The mutating step — adopt selected suggestions and bump the design
version. Full detail in `references/feasibility-workflow.md`. High-level:

1. Resolve target file (explicit arg, else `latest_feasibility(slug)`).
2. Pretty-print `suggestions:` with IDs.
3. Plain-text prompt: which suggestions to adopt (`1,3` / `none` / `all`).
4. Plain-text prompt for bump kind (minor vs major).
5. Compose the new design body — apply adopted suggestions to the
   matching section per `axis` (Baselines / Traces / Platforms / Metrics;
   `other` → Risks). **Preserve verbatim** the `## Research question` /
   `## Hypothesis` / `## Success criteria` sections — hard contract.
6. Write `design_version_path(slug, new_version)` with audit-trail
   frontmatter: `derived_from`, `feasibility_source`, `adopted_suggestions`.
7. Refresh `_index.md` + `status.md`. Print diff summary + footer.

The audit trail (`derived_from` + `feasibility_source` +
`adopted_suggestions` + the preserve-verbatim invariant) lets paper-readers
reconstruct why an experiment was scaled / pruned / redesigned.

## Stage 4 — `/experiment sync` and `/experiment clone`

**`/experiment sync`** (network-only — the only `/experiment` command that touches the
network):
1. Read `manifest.repo.{url, branch, last_known_sha}`.
2. Call `check_repo_updates(url, branch, last_known_sha)` — returns
   `{remote_sha, local_sha, drift, error}`. Never raises; on git/network failure the
   `error` key is populated and other fields are nulled. For SSH-style URLs
   the helper runs a fast pre-flight (`SSH_AUTH_SOCK` + `ssh-add -l`) so the
   user sees an actionable hint (`Run: ssh-add ~/.ssh/id_rsa`) instead of a
   generic 15-second timeout. HTTPS URLs run with `GIT_TERMINAL_PROMPT=0` so
   missing-credential errors surface immediately too.
3. If `drift is True`: tell the user the SHA changed and offer to update
   `manifest.last_known_sha` (plain-text Y/N).
4. Refresh `status.md`, `_index.md`. Print the footer.

**`/experiment clone [<slug>]`**:
1. Resolve slug (from arg or cursor); read `manifest.repo.url` + `branch`.
2. Call `clone_repo(slug, url, branch)` — `git clone --branch <branch> --depth 1`.
3. Update `manifest.repo.clone_status = "cloned"`; refresh `_index.md`.
4. Print the footer.

## Stage 5 — `/experiment version add`

**Inputs**
- `<vN.M>` — semver version slug. Suggest via `next_version(slug, kind)`; user may
  pass an explicit number to deliberately skip (e.g. `v1.3` → `v3.0`).
- `--description "..."` — required user-supplied label.
- `--kind major|minor` — informational.
- `--result <path-in-bound-repo>` — relative path to the structured result file;
  mirrored into `results/<vN.M>/`.
- `--config <path>` — config snapshot path (relative to experiment folder).
- `--seeds`, `--metrics`, `--notes` — optional.

**Workflow**
1. Call `register_version(slug, version, description, ...)`. The helper:
   - captures env via `capture_env()` (host / OS / arch / python / cuda / gpu /
     filtered library subset);
   - reads bound-repo HEAD via `current_commit_sha(slug)` (if cloned);
   - mirrors `--result` into `results/<vN.M>/` via `mirror_results(...)` with
     `boundary_root=repo_clone_path(slug)` (refuses traversal; refuses files > 100 MB
     unless `force=True`);
   - writes the full `pip freeze` to `configs/<vN.M>.requirements.txt`;
   - composes the YAML frontmatter using `docs/experiment-version-template.md`'s
     shape;
   - **refuses to overwrite** an existing `versions/<vN.M>.md` — the raised
     `FileExistsError` surfaces the suggested next semver.
2. Index the new version into AgentDB so semantic search can find it later
   (e.g. "the run that hit rouge-L > 0.4"):
   - `payload = version_indexing_payload(slug, version)`.
   - `mcp__claude-flow__memory_store(**payload)` — stores at
     namespace `project/experiments/<slug>/versions`, key `<vN.M>`, with the
     composed search text as `value` and the flat metrics/commit/result-file
     dict as `metadata`.
3. Refresh `_index.md`. Print the footer.

**`/experiment index [--slug <slug>]`** — backfill helper for after
`ruvector.db` is rebuilt (markdown survives; the index does not):
1. Call `iter_version_indexing_payloads(slug)` (omit `slug` to sweep every
   experiment).
2. For each payload returned, call `mcp__claude-flow__memory_store(**payload)`.
3. Print a one-line count summary (e.g. `indexed 12 versions across 4 experiments`).

## Stage 6 — `/experiment data add` / `/experiment data list`

**`/experiment data add`** appends a section to `data/index.md`. Required:
`--category` (one of `trace`, `dataset`, `checkpoint`, `log`, `plot`, `other`),
`--path` (URI inside the bound repo, S3, etc.). Optional: `--size`, `--sha256`,
`--produced-by <vN.M>`, `--produced-on <host>`, `--description`.

**`/experiment data list [--category <c>]`** reads `data/index.md`, filters by
category if given, prints a table.

## Stage 6.5 — `/experiment artifacts list|register|scan`

External artifacts (HuggingFace base-model shards, downloaded datasets, …)
that are reproducible from outside sources are recorded in
`outputs/experiments/<slug>/external-artifacts.md` so `/migrate export`
can exclude them and record their re-fetch commands in the archive's
`MANIFEST.json`. The three subcommands all shell out to
`python -m research_assistant.migrate artifacts <op> --slug <slug>` (the
cursor is resolved by the skill body, not the CLI).

Full detail (CLI shapes, the `--fetch-cmd` synthesis ladder per
`--source`, composition with `/migrate export`) in
`references/artifacts-workflow.md`. High-level:

- **`list`** — read `external-artifacts.md` and pretty-print each record.
  No-op if the file is absent.
- **`register`** — shell out with the user's `--name` / `--path` (both
  required) plus optional source / repo / revision / glob / size /
  fetch-cmd. Skill body interactively collects any missing required
  fields (plain-text Q&A). If `--fetch-cmd` isn't given, it's synthesized
  from `--source` + `--repo` (huggingface-cli / curl / git-lfs / aws-s3
  shapes; `other` writes a `# TODO: fetch …` placeholder).
- **`scan [--threshold <bytes>]`** — walk the experiment dir, prompt the
  user about every file ≥ threshold (default 1 GiB) not already covered
  by an entry. Same prompt as `/migrate export`'s flow, reachable
  proactively.

Composition: registering artifacts once via `scan` means future
`/migrate export` calls silently exclude them and embed the fetch
commands in the archive manifest; `/migrate import` then prints a
re-fetch checklist on the destination machine.

## Stage 7 — `/experiment analyze [<vN.M>...]`

Turn the mirrored result files into a **LaTeX analysis paragraph** that
`/paper write results` can drop straight into the prose. The prompt comes
from `references/analyze-prompt.md` — adapted from the
[awesome-ai-research-writing](https://github.com/Leey21/awesome-ai-research-writing)
"实验分析" entry.

**Inputs**
- Current `slug` from the cursor; mirrored result files under `results/<vN.M>/`.
- Optional positional list of versions to compare (e.g. `v1.0 v1.1 v2.0`);
  default = all versions present under `versions/`.

**Workflow**
1. Resolve the version list (positional args or all under `versions/`). Reject
   with a hint if `results/<vN.M>/` is empty for the requested versions —
   nothing to analyze.
2. **Read** the inputs:
   - Each version's mirrored result files under `results/<vN.M>/` (verbatim;
     don't pre-summarize — the prompt forbids hallucinated numbers and the
     model must see the raw rows to follow the "数据真实性" rule).
   - `latest_design_path(slug)` — for metric definitions, RQ, success criteria.
   - `references.md` if present — baseline numbers from comparison papers,
     which is what lets the model frame the SOTA comparison concretely.
3. **Load** the analyze prompt prelude from `references/analyze-prompt.md`.
4. **Stitch** the result rows + design context as the `# Input` block — free
   text, no pre-processing. Paste numbers verbatim.
5. **Apply** the prompt and parse the two-part response:
   - `Part 1 [LaTeX]` — one or more `\paragraph{Title Case Conclusion}` blocks
     with the analysis prose. No `\textbf` / `\emph` (prompt forbids them).
   - `Part 2 [Translation]` — Chinese direct translation for spot-checking.
6. **Write** outputs under the **latest** analyzed version's directory:
   - `results/<latest>/analysis.tex` — Part 1 verbatim. Consumed by
     `/paper write results`.
   - `results/<latest>/analysis.md` — full Part 1 + Part 2 as the audit log
     (so the user can verify the model didn't fabricate any number).
7. Refresh `_index.md`. Print a one-line summary
   ("analyzed N versions → results/<latest>/analysis.tex") + the footer.

**Output files**
- `outputs/experiments/<slug>/results/<latest>/analysis.tex`
- `outputs/experiments/<slug>/results/<latest>/analysis.md`

**Cross-skill integration.** `/paper write results` reads
`results/<latest>/analysis.tex` directly when the current paper is bound to
this experiment (via `expert.md` `experiment:` frontmatter or
`experiments:`). The `.tex` is meant to be self-contained — paste it under
`\section{Results}` and it compiles, with no `\textbf` to strip and the
`\paragraph{}` titles already in Title Case.

## Stage 8 — `/experiment status` / `/experiment list` / `/experiment show`

**`/experiment status [<slug>]`**:
1. Resolve slug from arg or cursor; if unset, print the no-experiment footer.
2. Compute `stage_status(slug)`; print `render_progress_board(...)`; persist to
   `<slug>/status.md` (overwrite).
3. Print the footer.

**`/experiment list`**: rebuild `_index.md` from `list_experiments()`; print it.

**`/experiment show <slug>`**: adopt the slug as the cursor; print manifest +
design preview + latest version metrics.

**Bare `/experiment`**: → `status` if cursor exists, else `list`.

## Outputs

Every artifact named above lives under `outputs/experiments/<slug>/`. AgentDB side:

- `project/experiment-context` — cursor `{slug}`.
- `project/experiments/<slug>` — searchable payload (title + tags + papers + design
  preview).
- `project/experiments/<slug>/versions` — one entry per `<vN.M>` with the
  composed search text (description + metrics + commit + notes excerpt) as
  the embedded value, plus flat metadata. Written by every `version add`;
  backfillable via `/experiment index`.

## Memory keys touched

- `project/experiment-context` — read/write (cursor: `{slug}`).
- `project/experiments/<slug>` — write (on `init`, `design`, `version add`,
  `feasibility apply`).
- `project/experiments/<slug>/versions` — write (on `version add` and
  `/experiment index` backfill).
- `papers/<paper-slug>` — read (during `scout`, via `memory_retrieve`).

## Optional commit-style convention

When the user commits *inside the bound GitHub repo* (not this plugin's repo),
they can adopt the `research(...)` semantic prefix from
Orchestra-Research/AI-Research-SKILLs (MIT) `0-autoresearch-skill`. The point
is a lightweight pre-registration: the **protocol commit must precede the
results commit**, so git history proves the plan existed before the data.

| When | Suggested message |
|---|---|
| Design / protocol locked for a new version | `research(protocol): <hypothesis-id> — <one-line>` |
| Results in for a version | `research(results): <hypothesis-id> — <outcome>` |
| Outer-loop reflection / direction change | `research(reflect): <direction> — <reason>` |
| Paper draft cut | `research(paper): <title>` |

This is **purely a suggestion**. lucky-research does not enforce it, parse it,
or fail a stage when commits use other conventions (`feat(...)` / `fix(...)` /
free-form are all fine). Skip it entirely if the user's lab uses a different
git workflow. The plugin's own commits stay on conventional commits.

## Open TODOs

_All previously-tracked items shipped. Add new ones here as scope shows up._
