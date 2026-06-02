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
     fetch command from source type + repo if you leave it blank. For
     `--source other`, the synthesized line is a `# TODO: fetch <repo> into
     <experiment>/<path>` placeholder the user fills in by hand — this is
     by-design (no canonical fetcher exists for "other"), so don't read it
     as an unfinished feature.
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

## Encryption

`/migrate export --encrypt` AES-encrypts every entry in the resulting
archive via [`pyzipper`](https://github.com/danifus/pyzipper). The output
file is still a `.zip` (extension unchanged) so naive file managers see a
zip; entries are unreadable without the passphrase.

| Flag | Where | Behavior |
|---|---|---|
| `--encrypt` | export | Prompt for a passphrase via `getpass` (twice, for confirmation). Never lands in shell history. |
| `--passphrase-env <VAR>` | export, import | Read passphrase from the named env var instead of prompting. For CI / piped use. Empty / unset env var is a hard error so scripts fail loudly instead of silently producing a plaintext archive. |
| _(none)_ | import | If the archive is encrypted (detected from zip flag bits), prompt via `getpass`. If unencrypted, ignore even if `--passphrase-env` is given. |

Notes:

- **Filenames stay in plaintext** in the zip central directory — that's how
  zip works regardless of encryption. The threat model is "USB stick falls
  out of pocket / archive uploaded to a third-party drive", not "adversary
  enumerating entries". Don't bake secrets into file paths.
- **Per-entry compression policy is preserved** under AES — `.pdf`/`.safetensors`
  still stored, `.md`/`.json` still deflated.
- **Decryption is one-pass.** `/migrate import` walks the encrypted archive
  the same way it walks an unencrypted one; the merge policy is unchanged.

## Reindex (rebuilding AgentDB from disk truth sources)

When two machines both have non-empty `ruvector.db`s and need to share
state, `/migrate import` currently keeps the destination's DB intact and
lands the source's copy as a `.from-migrate.db` sidecar — no automatic
content merge (the AgentDB SQLite schema isn't a public contract we want
to dump + diff against). The right workaround is to **reindex from disk
truth sources** instead:

```
python -m research_assistant.migrate reindex [--namespace NS] [--summary]
```

The command walks every on-disk source that has a structured payload
helper and emits one `{namespace, key, value, metadata}` dict per record
as JSONL on stdout. The calling skill prompt reads the JSONL and pipes
each line into `mcp__claude-flow__memory_store(**payload)`. Coverage:

| Namespace | Truth source |
|---|---|
| `project/past-work/<slug>` | `inputs/past-work/<slug>.md` |
| `project/experiments/<slug>` | `outputs/experiments/<slug>/manifest.md` |
| `project/experiments/<slug>/versions` | `outputs/experiments/<slug>/versions/<vN.M>.md` |
| `ideas/<slug>` | `outputs/idea-checks/<slug>/idea.md` |
| `project/boss/profile` | `inputs/boss-profile/profile.md` |
| `project/boss/meetings` | `inputs/boss-profile/meetings/<date>.md` |
| `project/research-notes/<slug>` | `outputs/research-notes/<slug>/state.yaml` |

`papers/<slug>` is intentionally **not** covered — re-summarizing PDFs
via `/summarize` rebuilds it more reliably than reverse-engineering the
embedded text. Run `/summarize sync` after the structured reindex.

Use `--summary` to preview counts before piping into a memory_store loop;
use `--namespace project/experiments` (or any other prefix) to scope a
partial reindex. Per-file errors are swallowed (one corrupt markdown
file can't poison the whole pass).
