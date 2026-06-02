---
design_version: d1.0                   # bumped by /experiment design re-run + /experiment feasibility apply
created_at: <YYYY-MM-DD>
derived_from: null                     # null for d1.0; predecessor version slug for d1.1+
feasibility_source: null               # path to feasibility-<date>.md when revision was driven by adoption
adopted_suggestions: []                # IDs from the feasibility report's `suggestions` list
---

# Design — {{title}} — {{design_version}}

<!--
Section convention: `/experiment feasibility apply` preserves the
**Research question**, **Hypothesis**, and **Success criteria** sections
verbatim across design versions — those define the experiment's purpose.
Only the other sections (Baselines, Traces, Platforms, Metrics, Risks) get
rewritten to fit a feasibility suggestion.
-->

## Research question

<one sentence: what does this experiment ask?>

## Hypothesis

<what do you expect to find, and why?>

<!--
Optional: when the design naturally decomposes into a tree of sub-hypotheses,
list them here using the H1 / H1.1 / H1.2 pattern (adapted from
Orchestra-Research/AI-Research-SKILLs MIT `0-autoresearch-skill`):

- H1: <root claim>
  - H1.1: <follow-up that only matters if H1 is supported>
  - H1.2: <alternative sub-claim>
- H2: <independent claim>

Each sub-hypothesis carries an independent prediction. Test the root first;
spawn sub-hypotheses only when results justify the deeper question. Keep
the tree shallow — if you find yourself at H1.1.2, you probably want a new
root.
-->

## Baselines

- <baseline-1 — paper / model / heuristic>
- <baseline-2>
- <baseline-3>

## Traces / datasets

- <name + source + size + license>
- <name + source + size + license>

## Platforms

- <hardware spec — e.g. "4× A100-80GB, single node">
- <software stack — e.g. "torch 2.4 + transformers 4.45 + peft 0.13">

## Metrics

| Metric | Why it matters | Target |
|---|---|---|
| <name> | <reason> | <expected range or `>X`> |

## Success criteria

<what would convince a reviewer that the hypothesis was confirmed (or falsified)?>

## Risks

- <thing that could invalidate the result>
- <thing that could blow up the budget>
