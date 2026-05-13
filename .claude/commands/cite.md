---
name: cite
description: Resolve citations into BibTeX. In a paper direction, scans `*.tex` for `\cite{slug}` keys and writes `refs.bib`. In free-form Markdown drafts, scans `[@cite:slug]` placeholders.
---

# /cite

Invoke the `ref-manager` skill in cite-as-you-write mode.

## Args

- `$ARGUMENTS` — optional. Path or mode hint:
  - Omitted + a paper direction is the current context → **Mode A**: scan
    `outputs/papers/<venue>/<direction>/{main.tex, sections/*.tex}` for `\cite{slug}`
    keys and update `<direction>/refs.bib`.
  - Path to a Markdown draft under `outputs/drafts/` → **Mode B**: scan that file
    for `[@cite:slug]` placeholders.
  - Omitted with no paper context → **Mode B** over every draft under
    `outputs/drafts/` with unresolved placeholders.

## Action

1. Load the `ref-manager` skill (`.claude/skills/ref-manager/SKILL.md`).
2. Pick mode based on target (paper direction → A; Markdown draft → B).
3. Follow the matching "Cite-as-you-write" workflow.
4. Write BibTeX to `<direction>/refs.bib` (Mode A) or
   `outputs/references/<paper-slug>.bib` (Mode B).
