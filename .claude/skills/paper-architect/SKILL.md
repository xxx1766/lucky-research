---
name: paper-architect
description: Help structure and draft a research paper — outline generator (intro / methods / results / discussion templates for the target venue) and per-section drafting helper. Use when the user says "outline a paper on X", "draft the intro", "what should the methods section cover".
---

# paper-architect

> **STATUS**: stub. Frontmatter + section headers only. Real skill body TBD.

## When to use

- User says "outline a paper", "draft section X", "what should I write here".
- User has summaries in `papers/` namespace and ideas in `ideas/` namespace ready to compose.

## Workflow

1. **Read context** — pull project goals from AgentDB `project/` namespace, the validated
   idea from `ideas/`, and related-work from `papers/`.
2. **Outline** — generate a section-by-section outline tailored to the target venue
   (NeurIPS / ACL / CHI / arXiv / blog).
3. **Per-section drafting** — for each requested section, Claude writes a draft using:
   - the outline,
   - the structured summaries of cited papers,
   - the user's stated contribution.
4. **Persist** — write to `outputs/drafts/<paper-slug>/<section>.md`.

## Outputs

- `outputs/drafts/<paper-slug>/outline.md`
- `outputs/drafts/<paper-slug>/<section>.md` per section.

## Memory keys touched

- `project/` — read (research goals, voice/style preferences)
- `ideas/<idea-slug>` — read (the validated idea)
- `papers/*` — read (related work for inline citations)
- `drafts/<paper-slug>` — write (snapshot of current outline so the mentor can track)

## Open TODOs before this skill is real

- [ ] Define section templates per venue.
- [ ] Decide citation-placeholder syntax (e.g. `[@cite:slug]`) that ref-manager will resolve.
