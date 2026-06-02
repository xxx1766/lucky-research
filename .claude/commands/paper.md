---
name: paper
description: Multi-stage paper-output workflow — venue, direction, scout, focus, motivate, write, render, status
---

# /paper

Invoke the `paper-architect` skill in the stage matching `$ARGUMENTS`.

## Subcommands

- `/paper venue <slug>` — create or edit the venue folder + `_venue.md` (论文特点和要求).
- `/paper venue refs add <pdf-or-arxiv>...` — ingest reference papers from the target
  venue, extract per-paper writing conventions into `_venue-refs/<slug>.md`, then
  auto-distill the `## Writing conventions` block of `_venue.md`. Idempotent on slug.
- `/paper venue refs list` — table of currently-ingested venue refs and whether the
  conventions block has been distilled.
- `/paper venue refs distill` — rebuild the `## Writing conventions` block of
  `_venue.md` from current `_venue-refs/` contents without re-ingesting anything.
- `/paper direction <slug>` — open or scope a sub-direction under the current venue.
  Past-work-historian agent seeds the discussion; Claude drafts a starter `expert.md`
  and registers an optional `code_repo:` pointer to the experiment-code GitHub repo.
- `/paper bind <experiment-slug>` — move `outputs/papers/<v>/<d>/` into the bound
  experiment's git repo (`outputs/experiments/<slug>/repo/paper/<v>/<d>/`),
  replace the local path with a symlink, copy venue files, write `.gitignore`,
  record the binding in `expert.md`. Idempotent. Pass `--force` to re-bind from
  a different experiment.
- `/paper unbind [--keep-files]` — remove the symlink. With `--keep-files`, also
  copy the experiment repo's contents back to a real local directory.
- `/paper sync [-m "<msg>"]` — stage just `paper/<v>/<d>/` paths, fetch (no
  auto-merge), commit, and push. Auto-generates a message of form
  `paper(<v>/<d>): <verb> <files>` unless `-m` is given. Refuses with a hint to
  `git pull --rebase` if the upstream is ahead.
- `/paper restore [<venue>/<direction>] [--all]` — re-create the local symlinks
  from cloned experiment repos (cross-machine bootstrap path).
- `/paper scout` — source related papers from the venue + arXiv into the current
  direction's `related-papers/`.
- `/paper focus` — narrow to a focused problem; write `focused-problem.md`.
- `/paper motivate` — design motivation experiments + benchmark plan.
- `/paper write [section]` — draft the outline (Markdown) or a specific section
  (LaTeX `.tex`). Auto-renders `main.pdf` at the end of each section write.
- `/paper render` — re-render `main.pdf` from the current direction without writing
  anything new. Useful after manual `.tex` edits or to retry a failed build.
- `/paper humanize [<section>] [--dry-run]` — post-draft pass that strips AI-tone
  from `sections/*.tex` using the "去 AI 味" prompt adapted from
  awesome-ai-research-writing. Default operates on every section; pass a section
  name (synonyms resolved) to scope it. `--dry-run` writes
  `sections/<name>.humanized.tex` instead of overwriting. Files the model judges
  already natural (Part 3 = `[检测通过]`) are skipped. Auto-renders `main.pdf` at
  the end. Audit log lands in `<direction>/reviews/humanize-<YYYY-MM-DD>.md`.
- `/paper review [--target <venue-slug>]` — reviewer-perspective audit of the
  rendered `main.pdf` (typeset output, not raw `.tex`). Adapted from the
  awesome-ai-research-writing "Reviewer 视角" prompt. Produces a two-part report
  (review opinion + strategic advice) under
  `<direction>/reviews/review-<YYYY-MM-DD>.md`. Use before submission, rebuttal,
  or advisor sync. `--target` overrides the venue used in the prompt (default =
  current cursor venue).
- `/paper status [<venue>/<direction>] [--all]` — print the progress board for the
  current direction (also persisted to `<direction>/status.md`). Pass an explicit
  `<venue>/<direction>` to target a specific folder and adopt it as the new cursor
  (recovery path for in-flight projects). Pass `--all` to walk every venue/direction
  and refresh each `status.md`. Auto soft-restores missing symlinks if their
  experiment repos are present locally.
- `/paper archive [<venue>/<direction>] [--abandoned]` — move a finished paper
  out of the active `outputs/papers/` tree into
  `inputs/past-work/<slug>/paper/`, and auto-create (or merge into) a
  `inputs/past-work/<slug>.md` past-work entry. Refuses if the direction is a
  symlink (run `/paper unbind` first). The venue-level `_venue.md`,
  `_template/`, `_venue-refs/` siblings are NOT moved — they stay shared
  across the venue. Clears the paper-context cursor if it pointed at the
  archived paper. Pass `--abandoned` to mark the past-work entry as
  `status: abandoned` rather than `published`.
- `/paper unarchive <slug>` — reverse `/paper archive`: move
  `inputs/past-work/<slug>/paper/` back to `outputs/papers/<venue>/<direction>/`.
  Reads venue/direction from the archived `expert.md` frontmatter (or falls
  back to the `archived-from:` link in the past-work .md). The past-work
  `<slug>.md` is left in place — the user can keep or delete it manually.
- `/paper archive list` — table of every archived paper under
  `inputs/past-work/*/paper/` (slug, venue, direction, archived-on, has-pdf).

## Action

1. Load the `paper-architect` skill (`.claude/skills/paper-architect/SKILL.md`).
2. Parse `$ARGUMENTS` into `<subcommand> <args>`; run the matching workflow stage.
3. Read + update the venue/direction context in AgentDB `project/paper-context`.
4. Write artifacts under `outputs/papers/<venue>/<direction>/`.
5. End every subcommand by printing
   `research_assistant.papers.render_progress_footer(venue, direction, status)` so
   the user always knows which stage they're at and what's next.
