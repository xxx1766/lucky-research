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
2. For each slug, look up `papers/<slug>` in AgentDB to get bibinfo.
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

### Format conversion

1. Call `research_assistant.refs.convert_document` (shells out to pandoc).
2. Supported: md → tex, md → docx, tex → md, tex → docx.

## Outputs

- `outputs/papers/<venue>/<direction>/refs.bib` — per-direction BibTeX.
- Converted document next to the source (`*.tex`, `*.docx`).

## Memory keys touched

- `papers/<slug>` — read (bibinfo lookup); written when step 3 fetches a new
  entry via `publisher_bibtex`.

## Open enhancements

- [ ] Decide BibTeX citation-key convention (`firstauthorYYYYkeyword`).
- [ ] Decide CSL/style preference (chicago / ieee / acm / neurips).

(Pandoc-on-PATH check shipped — `convert_document` raises a friendly
`RuntimeError` with the install hint when `pandoc` is missing.)
