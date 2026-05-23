---
name: migrate
description: Bundle per-user state (inputs/, outputs/, ruvector.db, .swarm/memory.db, .claude config) into a zip for cross-machine migration. Restores on a new machine without overwriting existing files. Triggered by /migrate.
---

# /migrate

Invoke the `migrate-tool` skill in the stage matching `$ARGUMENTS`.

## Subcommands

- `/migrate export [--out <dir>] [--include inputs|outputs|dbs|claude_config]
  [--dry-run] [--non-interactive]` — scan the repo, classify files into
  must / excluded-registered / excluded-unregistered / skip, interactively
  register any unregistered ≥1GB files in experiments (see
  `/experiment artifacts`), and write a `migrate-<host>-<YYYYMMDD-HHMMSS>.zip`
  to `outputs/migrate/` (or `--out <dir>`). Excludes registered external
  artifacts (HuggingFace base models, etc.) and records their fetch commands
  in the archive's `MANIFEST.json`.
- `/migrate import <archive.zip> [--dry-run]` — restore an archive on this
  machine. **Never overwrites** existing files: collisions become
  `<name>.from-migrate-<ts>.<ext>` sidecars; if `ruvector.db` /
  `.swarm/memory.db` is already non-empty on this machine, the archive copy
  lands as `<name>.from-migrate.db`. Writes a Markdown report under
  `outputs/migrate/imports/<archive-stem>.report.md` listing each verdict
  and the external artifacts the user still needs to re-fetch.

## What's included by default

| Category | Examples | Notes |
|---|---|---|
| User content | `inputs/papers/*.pdf`, `inputs/past-work/*.md`, `inputs/boss-profile/**` | always |
| Generated work | `outputs/papers/`, `outputs/experiments/<slug>/{manifest,design,versions,results,configs,data,…}`, `outputs/summaries/`, `outputs/idea-checks/`, `outputs/figures/`, `outputs/mentor/`, … | files in experiments are filtered against `external-artifacts.md` |
| AgentDB memory | `ruvector.db`, `.swarm/memory.db` | WAL-checkpointed before archive; sidecar `-shm` / `-wal` dropped |
| Claude config | `.claude/settings.local.json`, `.claude-flow/config.yaml` | not logs / sessions / metrics / pid |

## What's excluded

- `external-artifacts.md`-registered files (re-pull on the destination).
- `inputs/.env*`, anywhere — never archived (security).
- `__pycache__/`, `.venv/`, `.pytest_cache/`, `.ruff_cache/`, `build/`, `dist/`,
  `.vscode/`, `.idea/`, `.DS_Store`, `*.pyc`.
- `.claude-flow/{logs,sessions,metrics,data,learning,security}/`,
  `.claude-flow/daemon.pid`.
- Anything in a hidden `.git/` directory (re-clonable from GitHub).

## Action

1. Load the `migrate-tool` skill (`.claude/skills/migrate-tool/SKILL.md`).
2. Parse `$ARGUMENTS` into `<subcommand> <args>`; run the matching workflow.
3. Shell out to `python -m research_assistant.migrate` for the heavy lifting;
   never re-implement scan / zip logic in the skill prompt.
4. Print the resulting archive path (export) or report path (import) and a
   concise summary of next-step commands (re-fetch checklist for excluded
   artifacts on import).
