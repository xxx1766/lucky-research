# Per-section writing heuristics

Adapted from https://xxx1766.github.io/2026/03/19/how-to-write-paper/ ("how to write a paper").

`SKILL.md` Stage 6 loads this file when drafting a section and prepends the matching
`## section: <kind>` block to its drafting instructions. Cross-cutting principles
apply to every section.

**Synonym map (section name → kind):**

| Section name written by user / outline | Kind |
|---|---|
| `intro`, `introduction` | `intro` |
| `method`, `design`, `approach`, `system`, `mechanism` | `method` |
| `results`, `evaluation`, `eval`, `experiments` | `results` |
| `related-work`, `related`, `rw`, `background` | `related-work` |
| `discussion`, `limitations`, `threats` | `discussion` |
| `abstract` | `abstract` |
| `title` | `title` |
| anything else | use `## section: default` |

---

## cross-cutting

- Recommended drafting order: **figures → method → results → related-work → intro → abstract → title** (the blog's order — *not* IMRAD).
- Draft a provisional title at outline time; finalize only after the abstract is stable.
- Validate ideas via implementation; don't write from passive reading alone.
- The outline owns page allocation — defend it against scope creep.
- Block 3–5 days of focused time for hard sections (intro, method); use scattered time for easy sections (refs, conclusion).
- A paper's final goals usually differ from its initial ones — opportunism + revisionism is normal; let results steer the framing.

---

## section: figure

- **Do:** clarify the figure's *purpose, location, size* before drawing; keep to 3–4 data series; ensure B&W versions remain visually distinct; write the caption now, not later; the figure must be self-explanatory when extracted from the paper.
- **Don't:** defer captions; assume the surrounding prose will explain it; cram more than 4 series; pick a color palette that collapses in grayscale.
- **Beats:** state what the figure proves (the "owns" cell from `outline.md`'s figure table) → check the caption alone answers "what claim does this support".

---

## section: method

- **Do:** lead with the *idea + novelty*, not the engineering sequence; arrange content by importance (most-distinguishing mechanism first); include necessary formulas and citations inline; refer to algorithms via `\input{algorithms/<slug>.tex}` per the algorithm-inclusion rule.
- **Don't:** write as an experimental report ("we then did X, then Y"); bury the key idea inside chronological narrative; defer formal notation to an appendix when reviewers need it inline.
- **Beats:** contribution claim → mechanism overview → key design choices (and why) → formal description → relation to baselines / prior mechanisms.

---

## section: results

- **Do:** restate the paper's goal before each experiment so the reader knows what's being measured; report the headline number first, then breakdowns; extract significance — what each result *implies* — not just what it shows.
- **Don't:** merely repeat findings; pick metrics post-hoc to flatter the system; let ablations or breakdowns precede the headline.
- **Beats:** goal restatement → metric definition → headline number → ablation / breakdown → discussion of significance ("what this implies for §1's claim").

---

## section: related-work

- **Do:** cite ~30 most-relevant + foundational works, no more; arrange them as a progressive story (nearest → adjacent → foundational); make every cluster end on "but none of them addresses the focused problem from §[problem]".
- **Don't:** dump tangentially related work; arrange alphabetically or strictly chronologically; let RW grow until it dilutes the contribution.
- **Beats:** nearest neighbors → adjacent threads → foundational lineage → why none solves the focused problem.

---

## section: intro

- **Do:** funnel — broad topic → existing solutions → best existing → its limitations → this paper's goal; discuss the funnel structure with your advisor *before* drafting (intro rewrites cascade through the whole paper); lead every paragraph with mechanism or number, not vibe.
- **Don't:** use the words `novel`, `first`, `first ever`, `first time`, `paradigm-changing`, `paradigm-shifting`, or `we propose` (Stage 6 greps for these post-draft and warns); start with adjectives where a number would fit.
- **Beats:** hook (workload / pain) → state the tax (a number) → why the current best fails → this paper's wedge → headline result → contributions list.
- **Gate:** before drafting, Stage 6 prints a plain-text funnel check (yes / draft anyway / abort). On `abort`, stop.

---

## section: discussion

- **Do:** name the threats to validity honestly; state the failure modes the method has; describe one open question the result raises.
- **Don't:** treat discussion as a victory lap; introduce new claims that weren't supported by experiments.
- **Beats:** when the mechanism *doesn't* help → assumptions it depends on → what would falsify it → next step.

---

## section: abstract

- **Do:** flow industry-context → problem → key approach (minimize details) → results; end with quantified results (the headline number); ~250 words / ~12 lines two-column.
- **Don't:** use jargon, rare abbreviations, or citations; restate intro paragraph-by-paragraph; hide the headline number in the body.
- **Beats:** one sentence on workload + tax → one on what existing work optimizes vs. misses → two on the system (mechanism + key choice) → two on results (headline numbers) → one on artifact / open-source.

---

## section: title

- **Do:** concise, specific, accurately reflective of content; ~8–12 English words; revisit only after the abstract is stable.
- **Don't:** pad with redundant adjectives; lead with the system name when the contribution is the mechanism (per OSDI/SOSP voice notes: "do not let the system name carry the contribution"); promise more than the experiments deliver.
- **Beats:** read the current `\title{}` + stable abstract → propose 3 candidates in plain text → user picks (or supplies their own) → rewrite `\title{}`.

---

## section: default

- **Do:** read `outline.md`'s block for this section name (purpose, paragraph beats, anchors, sources, voice notes) and follow it verbatim.
- **Don't:** invent claims the outline doesn't carry.
- **Beats:** outline beats, in order.
