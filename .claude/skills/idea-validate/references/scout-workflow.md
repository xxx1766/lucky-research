# Stage 2 — Scout (近三年) + Stage 2.5 — Contrarian workflow detail

Load when actually running scout. Main SKILL has the high-level goal and the
auto-trigger contract; this file has the full per-step flow including the
gap-consolidation buckets and the Contrarian micro-flow that runs at the end
of Stage 2.

## Stage 2 — Scout

**Goal:** ground the discussion in real, recent literature.

### Workflow

1. **Load the active idea** (`registry.load_idea(slug)`). Confirm with the
   user:
   > `Search query default: <slug+statement keywords>. Year range default:
   > <last-3-years-inclusive>. Override?`

   Accept plain-text edits.

2. **Primary source — arXiv.** Call
   `research_assistant.ideas.scout.scout_recent_papers(query, year_range,
   max_results=25)`. This wraps `lit.sourcing.search_arxiv` and returns
   `ScoutResult`.

3. **Fallback — non-arXiv venues.** If the idea's area tags include any
   of `{sys, sec, db, hci}` and arXiv yielded fewer than ~5 hits in that
   area, invoke Claude's `WebSearch` tool with queries like
   `<venue> <query> last 3 years site:usenix.org OR site:acm.org` against
   OSDI / SOSP / NSDI / USENIX ATC / USENIX Security / CHI / SIGMOD /
   VLDB / etc. Wrap results as additional `PaperRef`s and append to
   `result.papers`.

4. **Cluster + relation notes** (Claude's reasoning). Group papers by
   sub-topic, then for each paper fill `relation_note` with 2–3
   sentences:

   > *What they did. How it relates to your idea. Why it doesn't subsume
   > yours (or does).*

   Cite by URL + arXiv ID.

5. **Gap consolidation** (Claude's reasoning, adapted from
   Orchestra-Research/AI-Research-SKILLs MIT `0-autoresearch-skill`
   Bootstrap step 2). After the per-paper relation notes are written,
   populate `result.gaps` (a `ScoutGaps` instance) with four buckets:

   | Bucket | Definition |
   |---|---|
   | `tried` | One bullet per cluster of approaches the last 3 years have explored. |
   | `untried` | Combinations, regimes, or extensions nobody has published yet (inversions / missing intersections). |
   | `where_broken` | Concrete failure modes documented in the scouted papers (table 5 of paper X, §6.3 of paper Y, etc.). |
   | `future_work` | Pointers from the scouted papers' Discussion sections (cite by URL). |

   Empty buckets are fine — `render_scout_md` omits them. Aim for 1–4
   bullets per non-empty bucket; this is a triage, not an exhaustive list.

6. **Render** with `scout.render_scout_md(result)` → write
   `outputs/idea-checks/<slug>/scout.md`.

7. **Index every paper.** For each paper,
   `mcp__claude-flow__memory_store` namespace=`papers`, key=`<paper-slug>`
   so `/paper scout` later can reuse the index. Then
   `mcp__claude-flow__memory_store` namespace=`ideas`, key=`<slug>/scout`
   with `scout.to_agentdb_payload(result)`.

8. **Mark scouted:** `registry.update_idea(slug, status="scouted")`.

9. **Cluster review.** Show the cluster overview; ask plain text:
   > `覆盖到了吗? 还要我搜哪个方向?`

   Multi-round refine until the user is satisfied.

10. **Offer summarization.** `要让 /summarize 把某篇做成完整 summary 吗?`
    Don't auto-invoke.

## Stage 2.5 — Contrarian micro-flow (反其道而行)

**Goal:** after the user has seen what the last-3-years mainstream is
doing, ask whether inverting the dominant assumption could win — and, if
so, capture the inversion as a sibling idea so both framings live
alongside each other.

**Auto-triggered** at the end of Stage 2 (right after step 9 above).
Bail by answering `skip` / `跳过` to Q1. Re-entry on demand via
`/idea-check contrarian` (or `/idea-check contrarian <slug>` for a
specific idea).

Build a `research_assistant.ideas.contrarian.ContrarianTrace(
parent_slug=slug, parent_statement=manifest.statement)`. Append every
Q/A with `contrarian.record_turn(trace, q, a)`.

### Questions

**Q1 — mainstream pattern**
> `最近 3 年这一波 arxiv 工作里最广泛的做法 / 模式是什么? (回答 \`skip\` / \`跳过\` 可以跳过这一步)`

If the answer is `skip` / `跳过`: set `trace.mainstream_pattern =
"<skipped>"`, `mcp__claude-flow__memory_store` namespace=`ideas`,
key=`<slug>/contrarian` with `contrarian.to_agentdb_payload(trace)`
(audit only), **DO NOT** touch `scout.md`, skip directly to Stage 3.

**Q2 — shared assumption**
> `这些做法共同假设了什么?`

**Q3 — inversion**
> `如果反过来 — 否定这个假设 — 会变成什么样?`

**Q4 — win condition**
> `反过来这条路要赢, 最起码需要什么证据?`

### Distill + confirm

1. Draft a 1–2 sentence contrarian framing grounded in Q3 + Q4; set
   `trace.final_statement`.
2. Show the triple `(proposed sibling slug = <parent>-contrarian,
   framing)` and ask plain text: `要把这个反向框架立成一个 sibling
   idea 吗? Y / N / 编辑`.
3. On `编辑`: take the user's correction as the new `final_statement`,
   re-show, re-ask.

### On `Y` (accept)

1. `trace.accepted = True`.
2. `new = registry.create_variant_idea(parent_slug=slug,
   suffix="contrarian", new_statement=trace.final_statement)`. Sibling
   slug collisions resolve to `<parent>-contrarian-2`, `-3`, …
   automatically.
3. Write `outputs/idea-checks/<new.slug>/contrarian.md` via
   `contrarian.render_contrarian_md(trace)`.
4. Append `contrarian.render_scout_appendix(trace)` to the parent's
   `outputs/idea-checks/<slug>/scout.md`. **Idempotent:** if the file
   already contains a `## Contrarian framings` section, splice it out
   (everything from that header to either the next `##` header or EOF)
   and replace it; never duplicate.
5. `mcp__claude-flow__memory_store` namespace=`ideas`,
   key=`<slug>/contrarian` with
   `contrarian.to_agentdb_payload(trace)`.
6. `mcp__claude-flow__memory_store` namespace=`ideas`,
   key=`<new.slug>` with `registry.to_agentdb_payload(new)`.
7. Print: `Sibling idea: <new.slug>. Switch active idea to it? Y/N`.
   Only update `project/idea-context.current` if the user picks Y;
   default stays on the parent.

### On `N` (reject)

Still set `trace.accepted = False`, run steps 4 + 5 above (scout.md
appendix + AgentDB trace mirror); **skip** step 2 (no sibling created)
and step 6 (no sibling payload).

Then proceed to Stage 3 on whichever idea the cursor points at.
