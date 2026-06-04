---
name: ref-manager
description: Manage references (BibTeX merge, cite-as-you-write resolution) and convert documents between Markdown / LaTeX / docx via pandoc. Use when the user says "build my bib file", "resolve [@cite] placeholders", "convert this draft to LaTeX / Word".
---

# ref-manager

> **STATUS**: active. `research_assistant.refs.merge_bibtex` / `convert_document` / `scan_tex_cite_keys` / `render_latex` all implemented.

## When to use

- User says "build the bib", "resolve citations in this draft", "convert X to LaTeX/docx".
- A draft under `outputs/drafts/` contains `[@cite:slug]` placeholders to resolve.

## Workflow

### Cite-as-you-write

Target: `outputs/papers/<venue>/<direction>/refs.bib`.

1. Walk `main.tex` + `sections/*.tex` for `\cite{<slug>}` keys via
   `research_assistant.refs.scan_tex_cite_keys`.
2. For each slug, look up `papers/<slug>` in AgentDB. If its
   `metadata.bibtex` field is populated (lit-summarize stores it there when a
   DOI was known), use that canonical entry directly — no network. Otherwise
   fall through to step 3.
3. **If a slug has no AgentDB entry** but the user knows the DOI: call
   `research_assistant.lit.publisher_bibtex.fetch_bibtex_from_publisher(doi)`
   to fetch the canonical BibTeX (tries CrossRef → doi.org content
   negotiation → CloakBrowser stealth fallback). Then `memory_store` it under
   `papers/<slug>` so the next `/cite` run skips the network entirely.
4. Append BibTeX entries to `<direction>/refs.bib` via
   `research_assistant.refs.merge_bibtex` (dedupes by DOI → title+author →
   entry key).
5. No source edit needed — `\cite{slug}` keys already match `refs.bib`
   entries.

**Citation-debt check (evidence-first).** A `\cite{slug}` in the prose with no
matching `refs.bib` entry is a *citation debt* — `paper-architect` surfaces it
on the progress board. Use
`research_assistant.refs.unresolved_cite_keys(direction_dir)` to list those keys
(it diffs `scan_tex_cite_keys` against `bib_entry_keys(refs.bib)`). After a
`/cite` run, the right outcome is an empty list; any remainder means the slug
has no `papers/<slug>` bibinfo and no known DOI — leave it as a `[REF_NEEDED]`
gap rather than inventing an entry.

### Format conversion

1. Call `research_assistant.refs.convert_document` (shells out to pandoc).
2. Supported: md → tex, md → docx, tex → md, tex → docx.

## Outputs

- `outputs/papers/<venue>/<direction>/refs.bib` — per-direction BibTeX.
- Converted document next to the source (`*.tex`, `*.docx`).

## Memory keys touched

- `papers/<slug>` — read (bibinfo lookup); written when step 3 fetches a new
  entry via `publisher_bibtex`.

## Conventions (settled defaults)

- **BibTeX citation key**: `firstauthorYYYYkeyword` — e.g.
  `vaswani2017attention`. `merge_bibtex` preserves whatever key the source
  entry carries; the convention only governs keys we mint ourselves when a
  publisher feed omits one. Override per-venue by editing the entry in
  `<direction>/refs.bib` after the merge.
- **CSL / style**: `ieee` for tech venues (default), `acm` for ACM venues
  (SIGCOMM / OSDI / SOSP / NSDI / SIGMOD / VLDB), `neurips` for ML venues.
  The venue's own `_template/` `.bst` always wins when one is present; this
  default only applies when no template ships.

(Pandoc-on-PATH check shipped — `convert_document` raises a friendly
`RuntimeError` with the install hint when `pandoc` is missing.)
