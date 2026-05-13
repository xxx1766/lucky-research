---
name: figure
description: Generate / manage research figures — structural SVG (arch / pipeline / concept) or matplotlib data plots — plus curate a reference-figure library. Bound to the current /paper or /experiment cursor.
---

# /figure

Invoke the `figure-tool` skill in the mode matching `$ARGUMENTS`.

## Subcommands

- `/figure new <slug>` — interactive 6-step generation (intent → kind → refs → size → palette → render). Writes `<slug>.{svg,pdf,png}` plus `<slug>.note.md` to the resolved scope's figures dir.
- `/figure list` — table of all figures in current paper / experiment scope.
- `/figure render <slug>` — re-export PDF + PNG from the (possibly hand-edited) source SVG. For data figures, re-run `plot_<slug>.py`.
- `/figure render --all` — batch re-render every figure in the current scope.
- `/figure edit <slug>` — print the absolute path of `<slug>.svg` so you can open it in Inkscape. No automated changes.
- `/figure export <slug> --format jpeg --quality 90` — opt-in JPEG export.
- `/figure ref add [<file>|--url <u>]` — capture a reference figure: copies image into `inputs/figure-refs/<slug>/`, auto-suggests tags + colors + reasons (you confirm / edit), indexes in AgentDB.
- `/figure ref list [--kind k] [--tag t]` — filtered table of curated references.
- `/figure ref sync` — re-walk `inputs/figure-refs/*/note.md`, refresh AgentDB index.
- `/figure ref show <slug>` — print one reference's note + image path.
- `/figure` (bare) — same as `/figure list`.

## Action

1. Load the `figure-tool` skill (`.claude/skills/figure-tool/SKILL.md`).
2. Read both cursors in AgentDB (`project/paper-context.current`, `project/experiment-context.current`) and call `research_assistant.figures.paths.resolve_scope(...)` — error if neither cursor is set.
3. Parse `$ARGUMENTS` into `<subcommand> <args>`; dispatch the matching workflow stage.
4. Always end with the LaTeX include snippet (for `new` / `render`) or a status table (for `list` / `ref list`).
