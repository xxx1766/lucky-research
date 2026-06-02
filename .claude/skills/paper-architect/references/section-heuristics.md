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

---

# Per-family overrides

`paper-architect` resolves a *venue family* for the current direction via
`research_assistant.papers.family_for_venue(venue)` (built-in prefix map +
optional `Family: <name>` override in `_venue.md`). When the family resolves
to one of `systems` / `nlp` / `cv`, `/paper write` prepends the matching
`### <kind>` sub-block here on top of the default `## section: <kind>`
block above. Each sub-block is **additive** — extra Do / Don't / Beats
items, not replacements.

`ml`, `db`, `ir` families resolve correctly but don't have sub-blocks yet —
they degrade to the default heuristics.

---

## family: systems

OSDI / SOSP / NSDI / EuroSys / ATC / ASPLOS / MICRO / ISCA / HPCA / FAST /
MLSys / SIGCOMM / SoCC voice: **mechanism + measured numbers + workload
implications**, not formulation-led.

### intro

- **Extra do:** open with a real workload (named system, named trace) and the
  tax it pays *as a number*; cite a production data point if you have one;
  close the funnel with a single mechanism word (`scheduling`, `caching`,
  `placement`, …) so the reader knows which lever you'll pull.
- **Extra don't:** open with formal notation; open with "with the rise of …".

### method

- **Extra do:** lead with the *mechanism*, not the formulation; describe one
  quantified design choice (page size, queue depth, batch threshold) and why;
  call out concurrency / failure-handling primitives explicitly; cite the
  implementation effort (LOC, lines changed in an existing kernel) when it
  matters for trust.
- **Extra don't:** defer engineering decisions to an appendix when reviewers
  need them inline; introduce a new theoretical bound — that belongs in
  related-work or discussion.

### results

- **Extra do:** evaluate on a *real* workload, not just a microbenchmark;
  report **tail latency (p50/p95/p99)** alongside throughput; describe the
  deployment shape (cluster size, node count, NIC, GPU model) once at the
  top of the section so each figure caption can be terse; include a
  cost / energy / utilization angle when the headline is "we save X".
- **Extra don't:** rely on a single synthetic microbenchmark; report only
  means — reviewers ask for tails.

### related-work

- **Extra do:** cluster by **mechanism category** (caching / replication /
  scheduling / consensus / …); for each cluster, end with "but none of them
  addresses [the focused problem from §1]"; cite production systems
  (Borg, Spanner, Ceph, …) when the comparison helps trust.
- **Extra don't:** organize by year; treat ML-systems work and pure-OS work
  as the same cluster.

### discussion

- **Extra do:** name the workload classes where the mechanism *doesn't* help;
  state the deployment assumption that would have to break for it to fail
  (e.g. "if the trace's working set spans more than 4× cache size, …").

---

## family: nlp

ACL / EMNLP / NAACL / TACL / COLING / EACL voice: **task framing +
multi-dataset evaluation + significance testing**, with an honest
Limitations + Ethics block as a hard requirement at most modern venues.

### intro

- **Extra do:** name the **task** and the **target users** in the first
  paragraph; cite the canonical benchmark(s) you'll use and the SOTA number
  on each; if your contribution is a method, position it against the
  competing paradigm (e.g. retrieval-augmented vs. fine-tuning).
- **Extra don't:** present a model as a contribution without naming the
  downstream task it serves; conflate "evaluation on dataset X" with "claim
  about language."

### method

- **Extra do:** present the **task formulation first** (input space, output
  space, training objective), then the architecture or prompt; give the
  formal objective `\mathcal{L}` once and reuse the symbol; describe the
  inference-time pipeline distinctly from training when they differ.
- **Extra don't:** describe an LLM by its parameter count alone — the family,
  the tokenizer, and the instruction-tuning status all change the comparison.

### results

- **Extra do:** evaluate on **≥2 datasets** when the task supports it;
  report **significance** (paired bootstrap or McNemar's, ≥3 seeds for
  training-from-scratch); when reporting LLM outputs, declare the model
  family, version date, decoding params, and prompt template once.
- **Extra don't:** report a single number without a CI or std; conflate
  zero-shot, few-shot, and fine-tuned numbers in one column.

### related-work

- **Extra do:** distinguish *task* prior-work from *method* prior-work as
  separate sub-paragraphs; cite the dataset paper alongside the first
  evaluation result; mention the modeling family you build on (encoder /
  decoder / encoder-decoder / retrieval-augmented).

### discussion

- **Extra do:** include an explicit **Limitations** sub-section (most
  *ACL/EMNLP venues require it post-2023); include an **Ethical
  considerations** sub-section when the work touches user data, generation
  at scale, or downstream-harm risks; declare the languages evaluated and
  the population they sample from.

---

## family: cv

CVPR / ICCV / ECCV / BMVC / WACV / 3DV voice: **architecture diagram +
qualitative + quantitative**, with visual examples surfacing early and a
teaser figure typically on page 1.

### intro

- **Extra do:** include a **teaser figure** on page 1 (referenced from
  intro); state the visual phenomenon you're tackling in one sentence
  before any architecture talk; cite the standard dataset(s) and the SOTA
  number on each up front.
- **Extra don't:** start with formulation when a single example image
  conveys the problem in one glance.

### method

- **Extra do:** open with the **architecture diagram** (referenced by
  number) and walk the data flow left-to-right; declare image / video /
  point-cloud / 3D input modality explicitly; state the inference compute
  budget (params, FLOPs, ms / image) early so reviewers know the comparison
  bracket.
- **Extra don't:** describe a backbone change as a contribution without an
  ablation isolating its effect.

### results

- **Extra do:** report on **the standard benchmark(s)** for your task
  (ImageNet / COCO / KITTI / nuScenes / …); show **qualitative failure
  examples** alongside the quantitative table; report FPS / latency on a
  named GPU when the contribution is efficiency.
- **Extra don't:** crop figures so the failure cases are invisible; report
  only one resolution when the method depends on input scale.

### related-work

- **Extra do:** organize by **task** first (detection / segmentation /
  generation / depth / …), then by paradigm (CNN / transformer / diffusion
  / NeRF); cite the recent SOTA you compare against by name and date.

### discussion

- **Extra do:** discuss what fails when the input distribution shifts
  (day→night, indoor→outdoor, synthetic→real); call out cases where the
  ground truth itself is ambiguous; note compute-budget assumptions that
  would break the comparison.
