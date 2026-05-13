---
name: ref-manager
description: Manage references (BibTeX merge, cite-as-you-write resolution) and convert documents between Markdown / LaTeX / docx via pandoc. Use when the user says "build my bib file", "resolve [@cite] placeholders", "convert this draft to LaTeX / Word".
---

# ref-manager

> **STATUS**: stub. Frontmatter + section headers only. Real skill body TBD.

## When to use

- User says "build the bib", "resolve citations in this draft", "convert X to LaTeX/docx".
- A draft under `outputs/drafts/` contains `[@cite:slug]` placeholders to resolve.

## Workflow

### Cite-as-you-write

Two modes — auto-detected from the target.

**Mode A — paper direction (LaTeX-native, preferred for papers)**

Target: `outputs/papers/<venue>/<direction>/refs.bib`.

1. Walk `main.tex` + `sections/*.tex` for `\cite{<slug>}` keys via
   `research_assistant.refs.scan_tex_cite_keys`.
2. For each slug, look up `papers/<slug>` in AgentDB to get bibinfo.
3. Append BibTeX entries to `<direction>/refs.bib` via
   `research_assistant.refs.merge_bibtex` (dedupes by key).
4. No source edit needed — `\cite{slug}` keys already match `refs.bib` entries.

**Mode B — free-form Markdown drafts (legacy, for `outputs/drafts/`)**

1. Scan a draft for `[@cite:slug]` placeholders.
2. For each slug, look up `papers/<slug>` in AgentDB to get bibinfo.
3. Emit BibTeX into `outputs/references/<paper-slug>.bib` via
   `research_assistant.refs.merge_bibtex` (dedupes by DOI/title).
4. Replace each placeholder with the BibTeX citation key (e.g. `\cite{smith2024}`).

### Format conversion

1. Call `research_assistant.refs.convert_document` (shells out to pandoc).
2. Supported: md → tex, md → docx, tex → md, tex → docx.

## Outputs

- `outputs/papers/<venue>/<direction>/refs.bib` — Mode A (paper direction).
- `outputs/references/<paper-slug>.bib` — Mode B (free-form Markdown drafts).
- Converted document next to the source (`*.tex`, `*.docx`).

## Memory keys touched

- `papers/<slug>` — read (bibinfo lookup)
- `drafts/<paper-slug>` — read (citation resolution)

## Open TODOs before this skill is real

- [ ] Decide BibTeX citation-key convention (`firstauthorYYYYkeyword`).
- [ ] Decide CSL/style preference (chicago / ieee / acm / neurips).
- [ ] Confirm pandoc is on PATH; if not, document install in README.
