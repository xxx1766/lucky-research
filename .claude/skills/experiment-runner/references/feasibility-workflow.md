# Stages 3.5 / 3.6 workflow detail (`/experiment feasibility [apply]`)

Two-step flow:

* **3.5 — feasibility** is advisory-only. It asks an LLM to score the
  design against the merged fleet + references and writes a verdict file.
  **No mutation to design files.**
* **3.6 — feasibility apply** is the mutating step. The user picks which
  suggestions to adopt, the design version is bumped, and the audit
  trail (`derived_from` + `feasibility_source` + `adopted_suggestions`)
  is written into the new design's frontmatter.

The split exists so the user can sit on a feasibility report (re-read,
discuss with the advisor, sleep on it) without ever committing to the
suggestions.

## Stage 3.5 — `/experiment feasibility`

**Inputs**

- Current `slug`; `latest_design_path(slug)`; `references.md` (optional);
  merged fleet snapshot (auto + manual).

**Workflow**

1. **Build the merged fleet picture:**
   - `auto = infer_fleet_from_versions()` walks every experiment's
     `versions/*.md` for `host:` + `gpu:` frontmatter; dedupes by hostname.
   - `manual` = parse `inputs/fleet.md` via
     `research_assistant.experiments.parsers.parse_fleet` if the file
     exists.
   - **Merge:** user-supplied takes precedence on hostname collisions.

2. **Gap detection.** Ask the user (plain text — no `AskUserQuestion`) if:
   - `auto + manual` is empty;
   - any machine the user mentions during the chat is not in the snapshot;
   - GPU info is missing for a machine the design will likely target.

   Each user answer is persisted **immediately** to `inputs/fleet.md`
   (rewrite the full file, preserving previously-known machines) before
   the LLM assessment runs. The fleet manifest is the durable ground
   truth.

3. **Compose the LLM prompt context:** the latest design body + the
   merged fleet + (optionally) `references.md`.

4. **LLM produces:**
   - `verdict: feasible | tight | infeasible`
   - `blockers: list[str]` — concrete hardware-vs-design conflicts.
   - `suggestions: list[FeasibilitySuggestion]` — each one
     purpose-preserving, with fields:
     - `id` (1, 2, 3, …)
     - `axis` ∈ `{model-size, baseline-pruning, batching, sharding,
       dataset-subset, sequential, lighter-eval, mixed-precision,
       gradient-checkpointing, other}`
     - `change`
     - `rationale`
     - `cost`

5. **Render and write** the report file to `feasibility_path(slug, today)`
   (collision-safe — same-day reruns get `-2`, `-3`, …). The frontmatter
   shape matches `FeasibilityReport`. Body sections:
   - `## Verdict`
   - `## Blockers`
   - `## Suggestions` (one `### S<id>` per suggestion)
   - `## Fleet snapshot (used for this assessment)`
   - `## Next step`

6. **Refresh `_index.md`** (add `last_feasibility_check`). Refresh
   `status.md`.

7. Print the report summary + footer.

## Stage 3.6 — `/experiment feasibility apply [<feasibility-file>]`

Adopt selected suggestions → bump the design version.

**Workflow**

1. **Resolve the target file:** explicit arg, else `latest_feasibility(slug)`.
2. **Read its frontmatter `suggestions:` list;** pretty-print to the user
   with IDs.
3. **Plain-text prompt:** `"Which suggestions to adopt? (e.g. '1,3' or
   'none' or 'all')"`. Accept any subset; `none` aborts.
4. **Plain-text prompt for bump kind:** `"Minor revision (default;
   next_design_version('minor')) or major redesign?"`.
5. **Compose the new design body:**
   - Read `latest_design_path(slug)`.
   - Apply each adopted suggestion's `change` to the relevant section
     (whichever the `axis` corresponds to: Baselines / Traces / Platforms
     / Metrics; `other` maps to Risks notes).
   - **Preserve verbatim** the `## Research question`, `## Hypothesis`,
     and `## Success criteria` sections — they define the experiment's
     purpose. This is a hard contract; don't paraphrase.
6. **Write** to `design_version_path(slug, new_version)` with
   frontmatter:
   ```yaml
   derived_from: <predecessor design_version>
   feasibility_source: <feasibility filename>
   adopted_suggestions: [<chosen ids>]
   ```
7. **Refresh** `_index.md`, `status.md`. Print a short diff summary
   (which sections changed) + footer.

## Audit-trail contract

The frontmatter chain `derived_from` + `feasibility_source` +
`adopted_suggestions` lets paper-readers reconstruct why an experiment was
scaled / pruned / redesigned. Don't strip these fields when bumping a
version. The `## Research question` / `## Hypothesis` / `## Success
criteria` invariant above is the other half of the same contract — the
*purpose* is preserved while the *plan* evolves.
