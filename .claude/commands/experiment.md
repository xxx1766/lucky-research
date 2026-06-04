---
name: experiment
description: Design + run experiments bound to a GitHub repo — init, scout, design, feasibility [apply], sync, clone, version add/list, data add/list, artifacts list/register/scan, analyze, status, list, show, index
---

# /experiment

Invoke the `experiment-runner` skill in the stage matching `$ARGUMENTS`.

## Subcommands

- `/experiment init <title> [--repo <url>] [--paper <slug>] ...` — register a new
  experiment under `outputs/experiments/<slug>/`. Asks for the bound GitHub repo URL
  (if not given via `--repo`) and **prompts whether to clone now**. Sets the
  AgentDB cursor `project/experiment-context.current = {slug}`.
- `/experiment scout` — for each paper in `manifest.papers`, fetch its AgentDB
  `papers/<slug>` summary and pre-fill `references.md` with a comparison matrix
  (trace · platform · metrics · code-availability). User edits.
- `/experiment design` — interactive narrowing → write `designs/d<N.M>.md`
  (RQ, hypothesis, baselines, traces, platforms, metrics, success criteria).
  First run writes `d1.0`; re-runs prompt for minor (`d1.1`) vs. major (`d2.0`).
- `/experiment feasibility` — pre-flight check against the user's fleet
  (`inputs/fleet.md` + hosts auto-derived from past `versions/*.md`). Drafts a
  dated `feasibility-<YYYY-MM-DD>.md` with `verdict` + `blockers` +
  `suggestions` that preserve the experiment's purpose. Asks for any missing
  machine info and writes it back to `inputs/fleet.md` immediately. **Network-
  free**, advisory only — never mutates design files.
- `/experiment feasibility apply [<feasibility-file>]` — interactive: shows the
  suggestion list (1, 2, 3, ...), takes a user-chosen subset (e.g. `1,3` or
  `all` or `none`), bumps the design version (minor by default, major on opt-in),
  and writes a new `designs/d<N.M>.md` with `derived_from` + `feasibility_source`
  + `adopted_suggestions` frontmatter. **Research question**, **Hypothesis**,
  and **Success criteria** sections are preserved verbatim from the predecessor.
- `/experiment sync` — `git ls-remote` the bound repo's branch, compare to
  `manifest.last_known_sha`, update on confirmation. The only `/experiment` command
  that touches the network.
- `/experiment clone [<slug>]` — `git clone --branch <branch> --depth 1` into
  `outputs/experiments/<slug>/repo/`. Idempotent: refuses if `repo/` already exists.
- `/experiment version add <vN.M> --description "..." [--kind major|minor]
  [--status planned|running|completed|failed|abandoned] [--result <path-in-bound-repo>]
  [--config <path>] [--seeds ...] [--metrics k=v,...] [--notes "..."]` — capture env
  (host/OS/python/cuda/gpu/libraries), bound-repo commit SHA, optional config snapshot,
  and (if `--result` given) mirror the result file into `results/<vN.M>/`. `--status`
  defaults to `completed`; use it to record a failed/abandoned/in-flight run. Refuses
  overwrite — suggests the next semver.
- `/experiment version list` — semver-sorted table with status + metrics + commit_sha.
- `/experiment data add <data-slug> --category <c> --path <p>
  [--size <s>] [--sha256 <h>] [--produced-by <vN.M>] [--produced-on <host>]
  [--description "..."]` — append a section to `data/index.md`. `category` is one of
  `trace | dataset | checkpoint | log | plot | other`.
- `/experiment data list [--category <c>]` — filtered table from `data/index.md`.
- `/experiment artifacts list` — print this experiment's `external-artifacts.md`
  (records of externally-reproducible files excluded from `/migrate export`).
- `/experiment artifacts register --name <short> --path <path>
  [--source huggingface|http|git-lfs|s3|other] [--repo <ref>]
  [--revision <sha>] [--glob <pat>] [--size <est>] [--fetch-cmd '...']` —
  append one external-artifact record. `--name` and `--path` are required.
  For `--source` other than `other`, a default `fetch-cmd` is synthesized
  from `--source` + `--repo`; `--source other` writes a `# TODO: fetch …`
  placeholder you fill in by hand.
- `/experiment artifacts scan [--threshold <bytes>]` — walk the experiment
  dir for ≥threshold files (default 1 GiB) not already registered and
  interactively prompt the user about each one.
- `/experiment analyze [<vN.M>...]` — turn the mirrored `results/<vN.M>/` files
  into a self-contained LaTeX analysis paragraph using the "实验分析" prompt
  adapted from awesome-ai-research-writing. Writes
  `results/<latest>/analysis.tex` (one or more `\paragraph{Title Case Conclusion}`
  blocks, no `\textbf`/`\emph`) + `results/<latest>/analysis.md` (full response
  with Chinese translation for spot-checking). `/paper write results` consumes
  the `.tex` directly when the paper is bound to this experiment.
- `/experiment status [<slug>]` — board for the current/given experiment, persisted
  to `<slug>/status.md`. Adopts `<slug>` as the cursor if given.
- `/experiment index [--slug <slug>]` — backfill the AgentDB
  `project/experiments/<slug>/versions` namespace from on-disk
  `versions/<vN.M>.md` files. Use after `ruvector.db` is rebuilt; the markdown
  is the source of truth, the index is derived. Omit `--slug` to sweep every
  experiment.
- `/experiment list` — refresh + print `outputs/experiments/_index.md`.
- `/experiment show <slug>` — adopt cursor + print manifest + design preview +
  latest version metrics.
- `/experiment` (bare) — `status` if cursor exists, else `list`.

## Action

1. Load the `experiment-runner` skill (`.claude/skills/experiment-runner/SKILL.md`).
2. Parse `$ARGUMENTS` into `<subcommand> <args>`; run the matching workflow stage.
3. Read + update the cursor in AgentDB `project/experiment-context`.
4. Write artifacts under `outputs/experiments/<slug>/`.
5. End every subcommand by printing
   `research_assistant.experiments.render_progress_footer(slug, status)` so the user
   always knows which stage they're at and what's next.
