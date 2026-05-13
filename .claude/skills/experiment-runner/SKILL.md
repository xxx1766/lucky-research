---
name: experiment-runner
description: Design and run experiments bound to a GitHub repo. Tracks the bound repo's URL + SHA, records versioned execution attempts (semver), and mirrors structured results locally so /paper can consume them when writing. Use when the user wants to design, log, sync, or analyze experiments. Triggered by /experiment.
---

# experiment-runner

> **STATUS**: stub. Workflow contracts only — real bodies land stage-by-stage.

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

**Inputs**
- Current `slug`; `references.md` if present.

**Workflow**
1. If `latest_design(slug)` returns nothing → first run, target = `d1.0`.
   Otherwise prompt the user (plain text Y/N per `feedback_decision_ui`):
   minor revision (`next_design_version(slug, "minor")`) or major redesign
   (`next_design_version(slug, "major")`).
2. Interactive narrowing — ask the user:
   - What's the specific research question?
   - What's your hypothesis?
   - Which baselines from `references.md` will you re-run yourself?
   - What's the smallest result that would confirm/falsify the hypothesis?
3. Render `docs/experiment-design-template.md` from the answers, populating the
   YAML frontmatter (`design_version`, `created_at`, `derived_from`,
   `feasibility_source: null`, `adopted_suggestions: []`); write to
   `design_version_path(slug, version)`.
4. Print `render_progress_footer(slug, stage_status(slug))`.

## Stage 3.5 — `/experiment feasibility`

**Inputs**
- Current `slug`; `latest_design_path(slug)`; `references.md` (optional);
  merged fleet snapshot (auto + manual).

**Workflow**
1. Build the merged fleet picture:
   - `auto = infer_fleet_from_versions()` — walks every experiment's
     `versions/*.md` for `host:` + `gpu:` frontmatter; dedupes by hostname.
   - `manual` — parse `inputs/fleet.md` if it exists (inline YAML read in
     this skill body; `parse_fleet` Python stub deferred).
   - Merge: user-supplied takes precedence on hostname collisions.
2. **Gap detection**. Ask the user (plain text — no AskUserQuestion) if:
   - `auto + manual` is empty;
   - any machine the user mentions during the chat is not in the snapshot;
   - GPU info is missing for a machine the design will likely target.
   Each user answer is persisted **immediately** to `inputs/fleet.md`
   (rewrite the full file, preserving previously-known machines) before
   the LLM assessment runs. The fleet manifest is the durable ground truth.
3. Compose the LLM prompt context: the latest design body + the merged fleet
   + (optionally) `references.md`.
4. LLM produces:
   - `verdict: feasible | tight | infeasible`
   - `blockers: list[str]` — concrete hardware-vs-design conflicts.
   - `suggestions: list[FeasibilitySuggestion]` — each one purpose-preserving:
     `id` (1, 2, 3 ...), `axis` (one of model-size, baseline-pruning, batching,
     sharding, dataset-subset, sequential, lighter-eval, mixed-precision,
     gradient-checkpointing, other), `change`, `rationale`, `cost`.
5. Render and write the report file to
   `feasibility_path(slug, today)` (collision-safe; same-day reruns get `-2`,
   `-3`, ...). The frontmatter shape matches `FeasibilityReport`. Body sections:
   `## Verdict`, `## Blockers`, `## Suggestions` (one `### S<id>` per
   suggestion), `## Fleet snapshot (used for this assessment)`, `## Next step`.
6. Refresh `_index.md` (add `last_feasibility_check`). Refresh `status.md`.
7. Print the report summary + footer.

**No mutation to design files in this stage** — purely advisory.

## Stage 3.6 — `/experiment feasibility apply [<feasibility-file>]`

Adopt selected suggestions → bump the design version.

**Workflow**
1. Resolve the target file: explicit arg, else `latest_feasibility(slug)`.
2. Read its frontmatter `suggestions:` list; pretty-print to the user with IDs.
3. **Plain-text prompt**: "Which suggestions to adopt? (e.g. `1,3` or `none`
   or `all`)". Accept any subset; `none` aborts.
4. **Plain-text prompt** for bump kind: "Minor revision (default;
   `next_design_version("minor")`) or major redesign?".
5. Compose the new design body:
   - Read `latest_design_path(slug)`.
   - Apply each adopted suggestion's `change` to the relevant section
     (whichever the `axis` corresponds to — Baselines / Traces / Platforms /
     Metrics; `other` maps to Risks notes).
   - **Preserve verbatim** the `## Research question`, `## Hypothesis`, and
     `## Success criteria` sections — they define the experiment's purpose.
     This is a hard contract; don't paraphrase.
6. Write to `design_version_path(slug, new_version)` with frontmatter:
   - `derived_from: <predecessor design_version>`
   - `feasibility_source: <feasibility filename>`
   - `adopted_suggestions: [<chosen ids>]`
7. Refresh `_index.md`, `status.md`. Print a short diff summary
   (which sections changed) + footer.

The audit trail (frontmatter chain `derived_from` + `feasibility_source` +
`adopted_suggestions`) lets paper-readers reconstruct why an experiment was
scaled / pruned / redesigned.

## Stage 4 — `/experiment sync` and `/experiment clone`

**`/experiment sync`** (network-only — the only `/experiment` command that touches the
network):
1. Read `manifest.repo.{url, branch, last_known_sha}`.
2. Call `check_repo_updates(url, branch, last_known_sha)` — returns
   `{remote_sha, local_sha, drift, error}`. Never raises; on git/network failure the
   `error` key is populated and other fields are nulled.
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
2. Refresh `_index.md`. Print the footer.

## Stage 6 — `/experiment data add` / `/experiment data list`

**`/experiment data add`** appends a section to `data/index.md`. Required:
`--category` (one of `trace`, `dataset`, `checkpoint`, `log`, `plot`, `other`),
`--path` (URI inside the bound repo, S3, etc.). Optional: `--size`, `--sha256`,
`--produced-by <vN.M>`, `--produced-on <host>`, `--description`.

**`/experiment data list [--category <c>]`** reads `data/index.md`, filters by
category if given, prints a table.

## Stage 7 — `/experiment analyze`

**Inputs**
- Current `slug`; mirrored result files under `results/<vN.M>/`.
- Optional positional list of versions to compare; default = all.

**Workflow**
1. Read each version's mirrored result file (`results/<vN.M>/*`); also read
   `design.md` for the metric definitions.
2. LLM renders a cross-version comparison: how metrics moved, where the variance
   comes from, what next version should try.
3. Optionally write `analysis.md` (plain-text Y/N — user opts in; not auto).
4. Print the footer.

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

Both written by `init`, `design`, and every `version add`. Per-version AgentDB
indexing is deferred (see Open TODOs).

## Memory keys touched

- `project/experiment-context` — read/write (cursor: `{slug}`).
- `project/experiments/<slug>` — write (on `init`, `design`, `version add`,
  `feasibility apply`).
- `papers/<paper-slug>` — read (during `scout`, via `memory_retrieve`).

## Open TODOs

- [ ] Real frontmatter parser (lands plugin-wide; unblocks `parse_experiment`,
      `parse_version`, `parse_data_index`).
- [ ] Per-version AgentDB indexing (`project/experiments/<slug>/versions/<vN.M>`)
      so semantic search can find "the run that hit rouge-L > 0.4".
- [ ] `/paper scout` querying `project/experiments/` for experiments bound to the
      current `(venue, direction)`.
- [ ] `/paper write results` reading `outputs/experiments/<slug>/results/<latest>/`
      directly.
- [ ] `/mentor` surfacing experiments with no new version in N weeks.
- [ ] `/experiment sync` SSH-agent / HTTPS-credential pre-flight check before
      hitting `git ls-remote` (currently relies on the helper's timeout +
      error-sentinel return).
