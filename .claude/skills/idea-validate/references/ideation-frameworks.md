# Ideation frameworks — when you're stuck on /idea-check

> **Source:** condensed from
> [Orchestra-Research/AI-Research-SKILLs](https://github.com/Orchestra-Research/AI-Research-SKILLs)
> (MIT) `21-research-ideation/`. The original repo has two longer files
> (`brainstorming-research-ideas`, `creative-thinking-for-research`). This
> file picks the bits that map to `/idea-check`'s shape and keeps the
> Selection Guide front and center. Read the originals on GitHub when you
> want the full theoretical background (Koestler, Boden, Polya, Kauffman,
> Rothenberg).

## When `/idea-check brainstorm` reaches for this

The brainstorm subcommand is the escape hatch when Stage 1 Socratic stalls
or when the user's idea feels too narrow / too obvious / pre-occupied.
Pick **2–3** frameworks from the table below (not all of them) and walk
each one as a 3–6 turn micro-flow. Output appends to
`outputs/idea-checks/<slug>/brainstorm.md` and indexes to AgentDB
`ideas/<slug>/brainstorm`.

## Selection Guide

| User said / situation | Use lens(es) |
|---|---|
| "I don't know what area to work in" | F3 (tension) → F5 (what-changed) |
| "I have a vague area but no specific idea" | F2 (abstraction ladder) → F6 (boundary probing) |
| "I have an idea but I'm not sure it's good" | F10 (two-sentence test) → F7 (simplicity) |
| "It feels incremental / +2% on a benchmark" | F2 (ladder up) → F4 (cross-pollination) |
| "I keep coming back to the same shape" | F1 (bisociation) or F3 (analogy) |
| "I want to challenge conventional wisdom" | F6 (failure analysis) → F8 (negation) |
| "I want to combine existing work" | F9 (composition/decomposition) |
| "I have a cool technique, no problem yet" | F1 (problem-first check) → F10 (stakeholder rotation) |
| "Stuck holding two opposites" | F11 (Janusian — synthesize, don't choose) |

## The 11 lenses (condensed)

### F1. Problem-first vs solution-first

Ask which mode the user is in. Solution-first ideas need 2+ genuine problems
they address; problem-first ideas need a named beneficiary. Both modes are
valid — naming the mode prevents the silent failure.

### F2. Abstraction ladder

Three moves:
- **Up** (generalize): is this a special case of something broader?
- **Down** (specialize): what happens at extreme constraints?
- **Sideways** (analogize): where else does this pattern appear?

Each move can be a publishable contribution on its own.

### F3. Tension hunting

Common research tensions:
performance ↔ efficiency · privacy ↔ utility · generality ↔ specialization ·
safety ↔ capability · interpretability ↔ performance · scale ↔ accessibility.

Ask: is this trade-off fundamental or an artifact of current methods? If
artifact, the reconciliation **is** the contribution.

### F4. Cross-pollination

Borrow structural ideas from adjacent disciplines. The mapping must hold at
the **mechanism** level (not surface metaphor).

High-yield source fields for ML/AI:
neuroscience · physics · economics · ecology · linguistics · control theory.

Validate by generating testable predictions from the analogy.

### F5. What changed?

Revisit old negative results under new conditions. List the assumptions that
led to its rejection; check which have been invalidated by recent shifts in:
compute · scale · data · regulation · tooling · cultural conditions.

Frame as: "X was previously impractical because Y, but Z has changed."

### F6. Failure analysis / boundary probing

Pick a widely-used method. List its implicit assumptions
(dataset / scale / domain / distribution). Systematically violate each one
and document where + why it breaks. Diagnose root cause, propose a fix
or explain why the failure is fundamental.

### F7. Simplicity test

Strip the SOTA method to its one key idea. Build the minimal version with
matching engineering effort. Two outcomes are both publishable:
- Small gap → the contribution is the simplicity itself.
- Large gap → you now know which component is doing the work.

### F8. Negation Hall of Fame (Boden's transformational creativity + TRIZ)

Take a "thing everyone knows" and drop it. Six patterns that worked:

| Assumption | Negation | Result |
|---|---|---|
| We need strong consistency | What if eventual? | CRDTs, eventual-consistency systems |
| We need exact answers | What if approximate? | LSH, sketches, ANN |
| Labels are necessary | What if learn without? | Self-supervised learning |
| More params = more compute | What if sparse? | Mixture of Experts |
| Train/inference are separate | What if model keeps learning? | Test-time training |
| Errors must be prevented | What if embrace + correct? | Speculative decoding |

### F9. Composition and decomposition

- **Compose**: pick two methods that solve complementary subproblems; ask what
  emergent capability arises. (RAG + CoT → retrieval-augmented reasoning.)
- **Decompose**: take an entangled method; isolate each component's
  contribution. (Fine-tuning = data selection + optimization + regularization
  — which one matters most?)

### F10. The two-sentence test

> **Sentence 1 (Problem)**: "[Domain] currently struggles with [specific
> problem], which matters because [concrete consequence]."
> **Sentence 2 (Insight)**: "We [approach] by [key mechanism], which works
> because [reason]."

If the user can't fill both — the idea isn't ready. Loop back to F1 / F7 / F3.

### F11. Janusian / dialectical thinking (Rothenberg)

When the user is stuck choosing between A and B, resist the choice. Instead
ask: "What system achieves both A and B?" The synthesis often requires a new
abstraction that reframes the opposition.

CAP theorem · zero-knowledge proofs · grokking · neural codecs are all
products of this move.

## Workflow protocol (use this verbatim in /idea-check brainstorm)

### Phase 1 — diagnose (1 turn)

Pick 2–3 frameworks per the Selection Guide. Tell the user: "我用 F<n>(name)
和 F<m>(name) 走一遍 —— 第一轮先 …"

### Phase 2 — diverge (3–6 turns)

Walk each chosen lens as a Q→A→Q sequence. Aim for **10–20 raw ideas**
across frameworks. Do not filter yet.

### Phase 3 — converge (1–2 turns)

Apply the filters to each candidate:

| Filter | Kill if |
|---|---|
| Explain-it test (F10) | Can't state in two sentences |
| Problem-first (F1) | No one suffers from this |
| Simplicity (F7) | A simpler approach already works |
| Stakeholder check | No clear beneficiary |
| Feasibility | Clearly infeasible at user's scale |

### Phase 4 — refine (1 turn)

For the surviving 1–3 ideas, write the two-sentence pitch (F10). Hand off:
- If the candidate is **distinct from the active idea** → offer to spawn it
  as a sibling idea via `registry.create_variant_idea(parent_slug=<active>,
  suffix=<short-tag>, new_statement=<pitch>)`.
- If the candidate is **a refinement of the active idea** → offer to update
  the active idea's `socratic.idea_statement` (the user can then re-enter
  Stage 1 to capture the new framing).

## What to keep in the trace

Persist to `outputs/idea-checks/<slug>/brainstorm.md`:

- Which frameworks were used (with F-numbers).
- Each Q/A turn verbatim.
- The 10–20 raw candidates from Phase 2.
- The 1–3 survivors from Phase 3 with reasons.
- The hand-off decision in Phase 4.

Mirror to AgentDB `ideas/<slug>/brainstorm` via `brainstorm.to_agentdb_payload`.

## Common pitfalls

| Pitfall | Symptom | Fix |
|---|---|---|
| Surface analogy | "X is like Y" without mechanism mapping | Force F3 mechanism-level check |
| Premature convergence | User picks the first idea | Run full Phase 2 diverge |
| Self-censoring | "That sounds weird" before exploring | F8 — weird is the point |
| Single-perspective bias | All ideas from one subfield | F4 cross-pollination is mandatory |
| Echo chamber | All ideas come from the same 10 papers | F5 what-changed forces fresh inputs |
