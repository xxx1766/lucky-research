---
name: cite
description: Resolve `[@cite:slug]` placeholders in a draft into BibTeX entries + citation keys
---

# /cite

Invoke the `ref-manager` skill in cite-as-you-write mode.

## Args

- `$ARGUMENTS` — path to a draft under `outputs/drafts/`. If empty, run on every draft
  that has unresolved `[@cite:...]` placeholders.

## Action

1. Load the `ref-manager` skill (`.claude/skills/ref-manager/SKILL.md`).
2. Follow the "Cite-as-you-write" workflow.
3. Write BibTeX to `outputs/references/<paper-slug>.bib`.
