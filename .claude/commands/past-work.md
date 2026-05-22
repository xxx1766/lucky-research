---
name: past-work
description: Curate past projects — list, add, sync, or bind a GitHub repo for entries under inputs/past-work/ so the past-work-historian agent can recall them
---

# /past-work

Invoke the `past-work-historian` agent in the mode matching `$ARGUMENTS`.

## Subcommands

### Prose lifecycle
- `/past-work` or `/past-work list` — list entries in `inputs/past-work/`
  (status / year / venue / repo / archived-paper per row). The `repo` column
  shows the `clone_status` of any bound repo (`–` / `tracked` / `cloned` /
  `missing`); the `archived` column flags entries whose companion folder
  contains a `paper/` subdir (i.e. they came from `/paper archive`).
- `/past-work add` — interactive capture; Claude prompts for the fields, writes
  `inputs/past-work/<slug>.md` from `docs/past-work-template.md`, and indexes
  the entry in AgentDB `project/past-work/<slug>`. If the user supplies a
  GitHub URL during capture, also writes the `repo:` frontmatter block (status
  `tracked`) and offers to clone immediately.
- `/past-work sync` — re-walk `inputs/past-work/*.md` and upsert each entry
  into AgentDB. Does NOT pull bound repos — use `/past-work pull <slug>` for
  that.

### Repo binding (each entry can optionally bind to one GitHub repo)
- `/past-work bind <slug> <repo-url> [--branch <b>]` — write the `repo:`
  frontmatter block on `inputs/past-work/<slug>.md`. Does NOT clone. Use
  `clone` afterwards when ready.
- `/past-work clone [<slug>]` — shallow-clone (`git clone --depth 1
  --branch <b>`) the bound repo into `inputs/past-work/<slug>/repo/`.
  Idempotent (refuses if the clone exists; pass `--force` to recreate).
  Updates `last_known_sha`, `cloned_at`, and `clone_status: cloned`. If
  `<slug>` is omitted, prompt to pick from entries with a `tracked` repo and
  no local clone.
- `/past-work sync-repo <slug>` — `git ls-remote` the bound URL, refresh
  `last_known_sha`. Network-only; doesn't pull.
- `/past-work pull <slug>` — `git pull --ff-only` inside
  `inputs/past-work/<slug>/repo/`; refresh `last_known_sha`. Explicit, user-driven.
- `/past-work unbind <slug> [--keep-clone]` — remove the `repo:` block; by
  default also delete `inputs/past-work/<slug>/repo/` to free disk. Pass
  `--keep-clone` to leave the local clone in place.

## Companion-folder layout

Each entry can grow a companion folder at `inputs/past-work/<slug>/` containing
any of:

- `repo/`  — clone of the bound GitHub repo (`/past-work clone`).
- `paper/` — archived `outputs/papers/<venue>/<direction>/` tree
  (written by `/paper archive`).
- `notes/` — user-curated extras (slides, screenshots, datasets).

The `<slug>.md` file stays the canonical entry; everything in the companion
folder is optional and per-user.

## Action

1. Load the `past-work-historian` agent (`.claude/agents/past-work-historian.md`).
2. Run the matching workflow using helpers from
   `research_assistant.mentor.past_work`:
   - `bind_repo`, `clone_repo`, `sync_repo`, `pull_repo`, `unbind_repo` for the
     repo-binding subcommands.
   - `list_entries_with_repo` for the `list` table.
   - `entry_path`, `companion_dir`, `repo_dir`, `paper_dir` for path resolution.
3. Source of truth on disk: `inputs/past-work/*.md` (gitignored, per-user).
   Shared template: `docs/past-work-template.md`.
