---
name: pseudocode
description: Generate / manage publication-grade LaTeX algorithm pseudocode. Bound to the current /paper or /experiment cursor; enforces method-level abstraction (not code translation).
---

# /pseudocode

Invoke the `pseudocode-tool` skill in the mode matching `$ARGUMENTS`.

## Subcommands

- `/pseudocode new <slug>` — interactive 5-step generation (intent → kind → inputs/outputs/notation → draft+lint → render+note). Writes `<slug>.{tex,note.md,pdf}` to the resolved scope's `algorithms/` dir.
- `/pseudocode list` — table of all algorithms in the current paper / experiment scope (slug · kind · package · time · space · created).
- `/pseudocode render <slug>` — recompile the standalone preview PDF from `<slug>.tex` (reads `<slug>.note.md` to pick the package family).
- `/pseudocode render --all` — batch-render every algorithm in the current scope.
- `/pseudocode check <slug>` — run `pseudocode.lint.scan()` on `<slug>.tex`; print anti-pattern smells (framework calls, tensor-lib calls, missing `\KwIn`/`\KwOut`, etc.).
- `/pseudocode check --all` — lint every algorithm in the current scope; non-zero count is a soft failure.
- `/pseudocode notation [--grep <q>]` — print the symbol-mapping table; `--grep attention` filters by case-insensitive substring.
- `/pseudocode` (bare) — same as `/pseudocode list`.

## Action

1. Load the `pseudocode-tool` skill (`.claude/skills/pseudocode-tool/SKILL.md`).
2. Read both cursors in AgentDB (`project/paper-context.current`, `project/experiment-context.current`) and call `research_assistant.pseudocode.paths.resolve_scope(...)` — error if neither cursor is set.
3. Parse `$ARGUMENTS` into `<subcommand> <args>`; dispatch the matching workflow stage.
4. Always end with the `\input{algorithms/<slug>.tex}` snippet (for `new` / `render`) or a status table (for `list` / `check`).
