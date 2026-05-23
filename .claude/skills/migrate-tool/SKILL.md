---
name: migrate-tool
description: Bundle per-user state into a zip for cross-machine migration and restore it on the new machine without overwriting existing files. Excludes externally-reproducible artifacts (HuggingFace base models, etc.) registered via per-experiment external-artifacts.md. Triggered by /migrate.
---

# migrate-tool

> **STATUS**: real implementation. Backed by `research_assistant.migrate`.

## Mental model

When the user moves to a new machine, the plugin's code is on GitHub but the
per-user state is gitignored:

```
inputs/                       — PDFs, past-work, boss-profile
outputs/                      — papers, experiments, summaries, figures, idea-checks
ruvector.db, ruvector.db-{shm,wal}   — AgentDB memory
.swarm/memory.db, .swarm/memory.db-{shm,wal}   — swarm coordination
.claude/settings.local.json
.claude-flow/config.yaml      — config only; logs/sessions/metrics excluded
```

`/migrate export` bundles the above into one zip. The 80GB elephant in the
room is bound experiment repos under `outputs/experiments/<slug>/repo/` — the
big files there are usually re-downloadable HuggingFace checkpoints, so each
experiment maintains an `external-artifacts.md` listing files that the
migration tool should **exclude** (and instead record the re-fetch command
inside the archive's `MANIFEST.json`).

If `/migrate export` finds a file ≥1GB in any experiment with no matching
entry in `external-artifacts.md`, it stops and asks the user to either:

1. register it as externally fetchable (writes a new record to that
   experiment's `external-artifacts.md`),
2. include it in the archive anyway,
3. skip it entirely.

`/migrate import` never overwrites files on the destination machine. File
collisions become `<name>.from-migrate-<timestamp>.<ext>` sidecars; DB
collisions (the destination already has a non-empty `ruvector.db` or
`.swarm/memory.db`) become `<name>.from-migrate.db` sidecars.

## Directory layout this skill owns

```
outputs/migrate/
  migrate-<hostname>-<YYYYMMDD-HHMMSS>.zip
  imports/
    migrate-<hostname>-<YYYYMMDD-HHMMSS>.report.md
```

## Workflow

The skill is a thin wrapper around `python -m research_assistant.migrate`.
Every subcommand shells out to the CLI; the skill body itself does no zip /
scan / sqlite work.

### `/migrate export [--out <dir>] [--include …] [--dry-run] [--non-interactive]`

1. Run `python -m research_assistant.migrate export` with the user's flags.
   Default scope = all four (`inputs`, `outputs`, `dbs`, `claude_config`).
2. If the CLI prompts for an unregistered ≥1GB file:
   - Show the user the path + size.
   - Plain text Y/N — no AskUserQuestion — per the `feedback_decision_ui`
     memory.
   - On "(1) register & exclude", inline-ask for: short name, source type
     (huggingface / http / git-lfs / s3 / other), repo URL, revision, and
     (optionally) a custom fetch command. The CLI synthesizes a default
     fetch command from source type + repo if you leave it blank.
3. When export finishes, print:
   - Archive path + size.
   - Number of files / DBs / excluded artifacts.
   - The re-fetch checklist (`huggingface-cli download …` lines) the user
     should run on the destination machine after `/migrate import`.

### `/migrate import <archive.zip> [--dry-run]`

1. Run `python -m research_assistant.migrate import <archive>`.
2. The CLI prints the Markdown `ImportReport` to stdout AND writes it to
   `outputs/migrate/imports/<archive-stem>.report.md`. Show the user the
   report path + a short summary:
   - How many files restored, collided (sidecar created), DB-restored,
     DB-sidecar'd, skipped.
   - The external-artifact re-fetch checklist embedded in the report.
3. If there are collisions: tell the user to diff sidecars vs originals at
   their leisure; nothing on disk has been destroyed.

### `/migrate status` (bare `/migrate`)

If `$ARGUMENTS` is empty:

1. List archives in `outputs/migrate/` with sizes + mtimes.
2. List reports in `outputs/migrate/imports/` with mtimes.
3. Print a one-line hint: `Run /migrate export to bundle this machine's state,
   or /migrate import <archive> to restore one.`

## Outputs

- `outputs/migrate/migrate-<host>-<ts>.zip` — the archive itself.
- `outputs/migrate/imports/<stem>.report.md` — Markdown report from the last
  import of each archive.

## Memory keys touched

None — `/migrate` is filesystem-only; AgentDB memory is migrated **inside**
`ruvector.db`, not via the MCP memory tools.

## Open TODOs

- [ ] Optional `--encrypt <passphrase>` flag for archives that ride USB
      sticks. The current archive is plain ZIP (no auth, no encryption).
- [ ] AgentDB JSONL export/import path so two non-empty `ruvector.db`s can
      be merged by `namespace+key` rather than only sidecar'd. Today's
      sidecar behavior matches user-stated preference; the JSONL path is
      future work.
