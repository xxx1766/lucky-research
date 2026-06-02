---
name: past-work-historian
description: Curates and surfaces the user's prior research/projects. Source of truth is `inputs/past-work/*.md`; indexed copy lives in AgentDB namespace `project/past-work/`. Use during /paper direction discussions, /past-work commands, or whenever the user says "have I done something like this before".
---

# past-work-historian

## Data layout

| Where | Role |
|---|---|
| `inputs/past-work/<slug>.md` | **Source of truth** — one file per past project, YAML frontmatter + body. Gitignored. User-editable. |
| `inputs/past-work/<slug>/repo/` | **Optional clone** — shallow `git clone --depth 1` of the bound GitHub repo (`/past-work clone <slug>`). Lives next to the `.md`, never required. |
| `inputs/past-work/<slug>/paper/` | **Optional archived paper** — full `outputs/papers/<venue>/<direction>/` tree relocated by `/paper archive`. Same companion folder as the optional clone. |
| `inputs/past-work/<slug>/notes/` | **Optional extras** — slides, screenshots, datasets the user wants next to the entry without putting them in the repo. |
| `docs/past-work-template.md` | **Shared template** — committed. Copy + fill when adding a new entry. |
| AgentDB `project/past-work/<slug>` | **Indexed mirror** — vector-indexed for semantic recall. Rebuilt by `/past-work sync` or after `/past-work add`. |

Helper module: `src/research_assistant/mentor/past_work.py` exposes
`PastWorkEntry`, `PastWorkRepo`, `slugify`, `next_available_slug`,
`entry_path`, `companion_dir`, `repo_dir`, `paper_dir`, `notes_dir`,
`list_entries`, `list_entries_with_repo`, `read_repo_block`,
`write_repo_block`, `bind_repo`, `clone_repo`, `sync_repo`, `pull_repo`,
`unbind_repo`, `parse_entry`, `to_agentdb_payload`.

## When to invoke

- Indirectly from `/paper direction` — seed the discussion with relevant prior work.
- Indirectly from `/paper archive` — the archived paper auto-creates a
  past-work entry, so the historian becomes the "memory" of finished papers.
- Directly from `/past-work` (list / add / sync / bind / clone / sync-repo / pull / unbind).
- User says "have I done X before", "what did I conclude about Y", "is this a repeat".

## Workflows

### Recall (the historian's main job)
1. Call `mcp__claude-flow__memory_search` over namespace `project/past-work/` with the
   user's direction or topic as the query.
2. For each hit return `{title, year, venue, status, repo (if bound), one-line "what I learned"}`.
   Mention the repo URL if the entry has a `repo:` block — the user often wants
   to revisit the code, not just the prose.
3. If fewer than three hits, broaden to `project/decisions/` and `ideas/`.
4. Return a short markdown block the caller can paste into the discussion.

### Add (driven by `/past-work add`)
1. Prompt the user for the fields (title, year, venue, status, tags, abstract,
   what-I-learned bullets, links). Use `slugify(title)` to derive the slug.
2. If the user mentions a GitHub URL during capture, offer to bind it:
   `mentor.past_work.bind_repo(slug, url, branch=...)`. Ask whether to clone
   now (`clone_repo(slug)`) or leave as `tracked` for later.
3. Compose a markdown file matching `docs/past-work-template.md`.
4. Write to `inputs/past-work/<slug>.md`.
5. Index in AgentDB: `mcp__claude-flow__memory_store(namespace="project/past-work",
   key=<slug>, value=<yaml frontmatter as string>)`.

### Sync (driven by `/past-work sync`)
1. Walk `inputs/past-work/*.md` via `list_entries()`.
2. Parse each via `parse_entry(path)`.
3. Upsert each into AgentDB `project/past-work/<slug>`. (Cleanup of orphaned entries
   for files that were deleted is deferred to the real implementation.)

### Bind / clone / sync-repo / pull / unbind (driven by `/past-work bind|clone|sync-repo|pull|unbind`)
1. `bind`: `mentor.past_work.bind_repo(slug, url, branch=...)` writes the
   `repo:` frontmatter block. Idempotent on same URL; replacing the URL
   doesn't auto-delete an existing clone — the user must `unbind --keep-clone`
   first if they want to migrate.
2. `clone`: `mentor.past_work.clone_repo(slug)` shallow-clones into
   `inputs/past-work/<slug>/repo/`. Updates `last_known_sha`, `cloned_at`,
   `clone_status: cloned`. Refuses if the clone already exists (pass
   `force=True` to recreate).
3. `sync-repo`: `mentor.past_work.sync_repo(slug)` calls `git ls-remote`;
   updates `last_known_sha`. Network-only, no pull.
4. `pull`: `mentor.past_work.pull_repo(slug)` runs `git pull --ff-only`
   inside the clone; refreshes `last_known_sha` on success.
5. `unbind`: `mentor.past_work.unbind_repo(slug, keep_clone=<flag>)` strips
   the `repo:` block; by default deletes the clone.

### Archive companion (driven by `/paper archive`)
- `/paper archive` calls into `research_assistant.papers.archive_direction(...)`,
  which physically moves the paper tree to
  `inputs/past-work/<slug>/paper/` and merges a past-work entry. The
  historian doesn't drive this — but `/past-work list` should show these
  entries with an `archived` flag so the user can tell external-project
  entries (which only ever have `repo/`) from archived-paper entries (which
  have `paper/`).

## Schema (YAML frontmatter)

```yaml
slug: contrastive-code-retrieval
title: "Contrastive pre-training for code retrieval"
year: 2024
venue: "EMNLP"
status: "published"      # published | unpublished | abandoned | in-progress
tags: [retrieval, contrastive, code]
links:
  - "arxiv:2401.xxxxx"
  - "paper:./paper/main.pdf"            # archived-paper companion
  - "archived-from:outputs/papers/EMNLP-2024/contrastive-code-retrieval"
  - "experiment:<exp-slug>"             # if the archived paper was bound to one
repo:                                    # optional — populated by /past-work bind
  url: "git@github.com:user/repo.git"
  branch: "main"
  last_known_sha: "abc1234..."
  clone_status: "cloned"                 # tracked | cloned | missing
  cloned_at: "2026-05-22"
```

Body sections (free markdown): Abstract, What I learned, Methods used, Outcome /
impact, Notes for future-me.

## Open TODOs

- [ ] Decide ranking when many hits (semantic score vs. recency).
- [ ] Add a `last-touched` signal so stale entries decay in ranking.
- [ ] Optional: index the cloned `repo/` for repo-grep recall during `/paper direction` and `/idea-check`.
