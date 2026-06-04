# Stage 3 workflow detail (`/experiment design`)

Load when actually narrowing a design. Main SKILL has the high-level triggers
and inputs; this file has the full per-step flow including the idea-handoff
pre-fill contract.

## Inputs

- Current `slug` from `project/experiment-context.current`.
- `references.md` if present (baselines + comparison papers).
- Optionally a bound paper-cursor (`project/paper-context.current`) whose
  `direction` is an idea slug — see step 2 below.

## Workflow

1. **Resolve target design version.** If `latest_design(slug)` returns
   nothing this is the first run → target = `d1.0`. Otherwise prompt the
   user (plain text Y/N per `feedback_decision_ui`):
   - minor revision → `next_design_version(slug, "minor")`
   - major redesign → `next_design_version(slug, "major")`

2. **Pre-fill from a bound idea, if one exists.** Read
   `mcp__claude-flow__memory_retrieve` namespace=`project`
   key=`paper-context.current` (paper-context holds `{venue, direction}`
   where `direction` equals the idea slug after `/idea-check handoff`). If
   present, also read `ideas/<direction>` for the manifest plus
   `ideas/<direction>/{socratic,evaluation}` for the hypothesis tree and
   pre-registration:

   > **Rebuild the models first.** Those AgentDB values were stored by
   > idea-validate as `trace.model_dump()` / `ev.model_dump()` — i.e. plain
   > dicts. The seed functions below take the **pydantic objects**, so
   > reconstruct them before calling:
   > `trace = SocraticTrace(**socratic_payload)` (from
   > `research_assistant.ideas.socratic`) and
   > `ev = IdeaEvaluation(**evaluation_payload)` (from
   > `research_assistant.ideas.evaluate`). Passing the raw dict raises
   > `AttributeError`.

   - **Hypothesis tree.** Call
     `research_assistant.ideas.socratic.to_experiment_hypothesis_seed(trace)`
     and paste the returned Markdown into `## Hypothesis` instead of the
     free-text prompt. The user can still edit. An empty seed → fall
     through to the prompt in step 3.

   - **Pre-registration.** Call
     `research_assistant.ideas.evaluate.to_experiment_metrics_seed(ev)`.
     `None` means the user skipped Stage 3 pre-reg → fall through. A
     non-`None` value pre-fills:
     - `## Metrics` row: `metric`, "Why it matters" = the pre-reg `notes`,
       "Target" = `target_delta`.
     - `## Success criteria` (free text): *"Improve `<metric>` over
       `<baseline_source>` (`<baseline_value>`) by at least
       `<target_delta>`, measured on …"*. User can edit.

3. **Interactive narrowing** — ask the user only for what wasn't pre-filled:
   - *Research question* — always ask. The design's RQ is usually narrower
     than the idea's question.
   - *Hypothesis* — skip if seeded above; otherwise ask
     `What's your hypothesis?`
   - *Baselines from `references.md`* — which will you re-run yourself?
   - *Metric + success criteria* — skip if seeded above; otherwise ask
     `What's the smallest result that would confirm/falsify the hypothesis?`

4. **Render** `docs/experiment-design-template.md` from the answers,
   populating the YAML frontmatter:
   ```yaml
   design_version: d1.0    # or whatever step 1 picked
   created_at: <today>
   derived_from: null      # set if this is a revision
   feasibility_source: null
   adopted_suggestions: []
   ```
   Write to `design_version_path(slug, version)`.

5. **Optional hypothesis tree.** If step 2 already seeded the tree from
   `ideas/<direction>/socratic`, it's already shaped as `H1 / H1.1 / H1.2`.
   Otherwise, when the user's free-text hypothesis decomposes into sub-
   hypotheses, encourage the same pattern (the template's HTML comment
   shows the shape). Adapted from Orchestra-Research/AI-Research-SKILLs
   (MIT) `0-autoresearch-skill`. Keep the tree shallow — `H1.1.2`-deep
   usually means "this should be a new root hypothesis". The pattern is
   purely notational; no helper enforces it, and `/experiment feasibility`
   treats `## Hypothesis` as a single preserved block regardless of
   internal structure.

6. Print `render_progress_footer(slug, stage_status(slug))`.
