# Stage 6.5 workflow detail (`/experiment artifacts list|register|scan`)

External artifacts that are reproducible from outside sources (HuggingFace
base-model shards, downloaded datasets, …) are recorded in
`outputs/experiments/<slug>/external-artifacts.md` so `/migrate export`
can exclude them and instead record their re-fetch commands in the
migration archive's `MANIFEST.json`.

All three subcommands shell out to `python -m research_assistant.migrate
artifacts <op> --slug <current-slug>` (the cursor is resolved by the skill
body, not by the CLI).

## `/experiment artifacts list`

Print the current experiment's `external-artifacts.md` as a record-by-
record summary. No-op if the file is absent.

## `/experiment artifacts register --name <short> --path <path> [...]`

Full CLI:

```
/experiment artifacts register --name <short> --path <path>
  [--source huggingface|http|git-lfs|s3|other]
  [--repo <ref>]
  [--revision <sha>]
  [--glob <pat>]
  [--size <est>]
  [--fetch-cmd '...']
```

Append one record to the experiment's `external-artifacts.md`. The CLI
requires `--name` and `--path` (named, not positional). The skill body
collects any missing required fields interactively (plain-text Q&A — no
`AskUserQuestion` per the `feedback_decision_ui` memory) before shelling
out:

1. Resolve the experiment slug from the cursor.
2. If `--name` is missing, default to the basename of `--path`.
3. Default `--glob` to `*` (everything under the path).
4. **Default `--fetch-cmd`** is synthesized from `--source` + `--repo`
   (and `--revision` where it carries meaning):

   | Source | Synthesized fetch-cmd |
   |---|---|
   | `hf` / `huggingface` | `huggingface-cli download <repo> --revision <rev> --local-dir <experiment>/<path>` |
   | `http` | `curl -L -o <experiment>/<path> <repo>` |
   | `git-lfs` | `git lfs clone <repo> <experiment>/<path>` |
   | `s3` | `aws s3 cp <repo> <experiment>/<path>` (adds `--recursive` when `<repo>` ends with `/`; surfaces `--revision` as a trailing `# revision: <rev>` comment since S3 has no native revision concept) |
   | `other` | `# TODO: fetch <repo> into <experiment>/<path>` (with a `# revision: <rev>` comment when given) — the manual command the user will need to write is one edit away rather than blank |
   | No `--repo` at all | Manual-fill-in placeholder |

5. Shell out: `python -m research_assistant.migrate artifacts register
   --slug <slug> --name <name> --path <path> ...`.
6. Print the resulting file path.

## `/experiment artifacts scan [--threshold <bytes>]`

Walk the current experiment's directory, prompt the user about every
file ≥ threshold (default 1 GiB) that isn't already covered by an
entry. Same prompt as the `/migrate export` flow uses, reachable
proactively rather than only at export time. Shells out to
`python -m research_assistant.migrate artifacts scan --slug <slug>`.

## Composition with `/migrate`

These subcommands compose with `/migrate export`: registering artifacts
once via `/experiment artifacts scan` means future `/migrate export`
calls silently exclude them and embed the fetch commands in the archive
manifest. On the destination machine, `/migrate import` prints the
fetch-cmd list as a re-fetch checklist.
