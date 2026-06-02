---
name: cite
description: Scan the current paper direction for `\cite{...}` keys and merge canonical BibTeX into `refs.bib`. Missing slugs are auto-fetched via CrossRef / doi.org / CloakBrowser when a DOI is known.
---

# /cite

Invoke the `ref-manager` skill in cite-as-you-write mode.

## Args

- `$ARGUMENTS` — optional. Either:
  - Omitted (a paper direction must be the current `paper-context` cursor) →
    scan `outputs/papers/<venue>/<direction>/{main.tex, sections/*.tex}` for
    `\cite{slug}` keys and merge entries into `<direction>/refs.bib`.
  - `<venue>/<direction>` — adopt that cursor first, then proceed as above.

## Action

1. Load the `ref-manager` skill (`.claude/skills/ref-manager/SKILL.md`).
2. Resolve the paper direction (cursor or `$ARGUMENTS`).
3. Follow the "Cite-as-you-write" workflow: scan tex → look up AgentDB
   `papers/<slug>` → for any slug missing in AgentDB, fall back to
   `lit.publisher_bibtex.fetch_bibtex_from_publisher(doi)` if a DOI is known
   → `merge_bibtex` → write `<direction>/refs.bib`.
4. Report which slugs were resolved locally vs fetched, and which (if any)
   are still unresolved (no AgentDB entry + no known DOI).
