---
name: convert
description: Convert a document between Markdown / LaTeX / docx via pandoc
---

# /convert

Invoke the `ref-manager` skill in format-conversion mode.

## Args

- `$ARGUMENTS` — `<source-path> --to=<tex|md|docx>`.

## Action

1. Load the `ref-manager` skill (`.claude/skills/ref-manager/SKILL.md`).
2. Follow the "Format conversion" workflow.
3. Emit the converted file next to the source.
