---
name: experiment
description: Design + run experiments bound to a GitHub repo — init, scout, design, sync, version add, data add, analyze, status
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
- `/experiment design` — interactive narrowing → write `design.md` (RQ, hypothesis,
  baselines, traces, platforms, metrics, success criteria).
- `/experiment sync` — `git ls-remote` the bound repo's branch, compare to
  `manifest.last_known_sha`, update on confirmation. The only `/experiment` command
  that touches the network.
- `/experiment clone [<slug>]` — `git clone --branch <branch> --depth 1` into
  `outputs/experiments/<slug>/repo/`. Idempotent: refuses if `repo/` already exists.
- `/experiment version add <vN.M> --description "..." [--kind major|minor]
  [--result <path-in-bound-repo>] [--config <path>] [--seeds ...]
  [--metrics k=v,...] [--notes "..."]` — capture env (host/OS/python/cuda/gpu/
  libraries), bound-repo commit SHA, optional config snapshot, and (if `--result`
  given) mirror the result file into `results/<vN.M>/`. Refuses overwrite — suggests
  the next semver.
- `/experiment version list` — semver-sorted table with status + metrics + commit_sha.
- `/experiment data add <data-slug> --category <c> --path <p>
  [--size <s>] [--sha256 <h>] [--produced-by <vN.M>] [--produced-on <host>]
  [--description "..."]` — append a section to `data/index.md`. `category` is one of
  `trace | dataset | checkpoint | log | plot | other`.
- `/experiment data list [--category <c>]` — filtered table from `data/index.md`.
- `/experiment analyze [<vN.M>...]` — cross-version comparison from the mirrored
  `results/` directories. Optionally writes `analysis.md` (user opts in).
- `/experiment status [<slug>]` — board for the current/given experiment, persisted
  to `<slug>/status.md`. Adopts `<slug>` as the cursor if given.
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
