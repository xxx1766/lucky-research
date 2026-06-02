---
name: lit-summarize
description: Summarize research papers (PDF or arXiv) into structured markdown (problem / method / results / contribution / limitations) and index each summary into the AgentDB `papers/` namespace for later semantic search. Use when the user drops PDFs into `inputs/papers/` or pastes an arXiv URL.
---

# lit-summarize

> **STATUS**: active. `research_assistant.lit.extract_pdf_text` / `fetch_arxiv` / `parse_metadata` are implemented; Claude generates the structured summary in-skill.

## When to use

- User mentions a PDF path under `inputs/papers/`.
- User pastes an arXiv URL or DOI.
- User says "summarize this paper", "what's the key idea of X", "intake these papers".

## Workflow

1. **Resolve sources** — collect every PDF in `inputs/papers/` not yet summarized + any
   arXiv URL the user named.
2. **Extract text** — call `research_assistant.lit.extract_pdf_text` (PyMuPDF).
3. **Summarize** — Claude produces a structured markdown with sections:
   `Problem`, `Method`, `Results`, `Contribution`, `Limitations`, `Related work pointers`.
4. **Persist** — write to `outputs/summaries/<slug>.md`.
5. **Index** — store the summary into AgentDB:
   - tool: `mcp__claude-flow__memory_store`
   - namespace: `papers`
   - key: paper slug
   - value: the summary markdown (vector-indexed automatically).

## Outputs

- `outputs/summaries/<slug>.md` (one file per paper).
- AgentDB entry in namespace `papers/` keyed by slug.

## Memory keys touched

- `papers/<slug>` — write
- `papers/*` — read (to avoid re-summarizing what's already indexed)

## Open enhancements

- [ ] Decide the slug format (arxiv id? doi? title hash?).
- [ ] Decide whether to call GROBID for higher-quality structural parsing.
- [ ] Define the structured-summary JSON schema (Pydantic model) for downstream consumers.
