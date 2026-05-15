# OSDI '27 — 论文特点和要求

> Scaffold drafted 2026-05-11 from prior OSDI cycles. The 2027 CFP is **not yet
> published** (typical drop: June–July 2026). Fields marked **TBD** must be confirmed
> against the official CFP when it lands.

## Quick facts

| Field | Value |
|---|---|
| Conference | 22nd USENIX Symposium on Operating Systems Design and Implementation |
| Held | Summer 2027 (typ. early–mid July, co-located with USENIX ATC) |
| Submission site | TBD (HotCRP, hotcrp.com/osdi27) |
| Anonymization | Double-anonymous (no author names, no self-revealing acks/refs) |

## Deadlines (TBD — based on '24/'25/'26 pattern)

| Milestone | Target window |
|---|---|
| Abstract registration | early Dec 2026 (~Dec 3 ±1 wk) |
| Full paper | mid Dec 2026 (~Dec 10 ±1 wk, hard) |
| Author response (rebuttal) | mid Feb 2027 (~5–7 days window) |
| Acceptance notification | late Mar 2027 |
| Camera-ready | mid May 2027 |
| Conference | early–mid Jul 2027 |

**Action**: lock these against the actual CFP the moment it drops.

## Page limit & format

- **12 pages** of body content (10pt, USENIX two-column template), **excluding**
  references and appendix.
- **No limit** on references.
- Appendix allowed but reviewers not required to read it.
- LaTeX template: `usenix-2020-09.tex` style (updated each year — use the one linked
  in CFP).
- Must include an **Artifact Availability** statement; OSDI strongly encourages
  artifact submission to the AE process post-acceptance.

## Review criteria (OSDI house style)

OSDI weights five axes. A paper that scores high on three and is defensible on the
others typically lands.

1. **Novelty** — a new mechanism, abstraction, or empirical finding. *Not* a
   straightforward port / re-implementation. Reviewers actively look for "did the
   community already know this?"
2. **Technical depth** — non-trivial engineering or analysis. Toy systems get bounced
   even when the idea is good.
3. **Real-system implementation** — built on, in, or against a real OS/runtime/cluster.
   Simulation-only papers face an uphill review.
4. **Evaluation rigor** — workloads have to be realistic (production traces, real
   apps), baselines have to be strong (SOTA, not strawmen), ablations have to
   isolate the claimed mechanism.
5. **Impact / generality** — does this change how a real subsystem will be built? Or
   does it only apply to a niche?

A 6th implicit axis: **writing & clarity** — OSDI reviewers are time-constrained;
muddled framing in the first 2 pages kills otherwise good work.

## Accepted paper styles

OSDI accepts a wide range, but they typically fall in four buckets:

1. **Build-and-measure** — new system / mechanism, prototype, evaluated on real
   workload. The modal OSDI paper. (e.g. vLLM, Sarathi, Ray, Shenango)
2. **Characterization / measurement** — large-scale measurement of a previously
   opaque system, surfacing actionable findings. (e.g. Meta/Google production
   traces, GPU cluster characterizations)
3. **Experience** — a system deployed at scale, what worked, what didn't, what the
   community should learn. Bar for honesty about failures is high. (e.g. Borg,
   Twine, Sirius)
4. **Formal / verification** — proved properties of a real system. (e.g. Verus,
   Hyperkernel, IronFleet-style)

## Recent trends (OSDI '24 + '25 + '26)

Cluster these to gauge what's "in-distribution" vs novel:

- **LLM infrastructure** — serving (paged-attention, continuous batching, speculative
  decoding, MoE routing), training (sequence/pipeline/expert parallelism), prefix
  cache management. Saturated but still landing — bar is rising.
- **Disaggregated memory / CXL** — far-memory tiering, RDMA-backed object stores,
  pooled-memory schedulers. Hot, still room for novel mechanisms.
- **Accelerator runtimes** — GPU scheduling, multi-tenant SM partitioning, kernel
  fusion / compilers (Triton-class), heterogeneous compute (GPU+DPU+TPU).
- **Serverless / FaaS** — cold start, autoscaling, stateful FaaS, sandbox primitives
  (WASM, gVisor, Firecracker successors).
- **Formal verification** — verified KV stores, verified distributed protocols,
  proof-carrying configs. Smaller niche but consistently lands when rigorous.
- **Storage** — KV-store internals, log-structured everything, persistent memory
  finally fading post-Optane, ZNS / open-channel SSDs.
- **Networking-in-the-OS** — RDMA, kernel-bypass, DPU offload, microsecond-scale
  scheduling, network-attached anything.
- **Security & isolation** — confidential compute (TDX/SEV), supply-chain, sidechannel
  mitigation as a systems problem.
- **Agentic / autonomous systems** — emerging at OSDI '25/'26: scheduling LLM-agent
  workloads, tool-call routing, multi-agent runtime. Lower competition window.
- **Datacenter operations** — power/thermal/scheduling at the cluster level, often
  experience papers from hyperscalers.

## Scoring rubric (informal — what reviewers say in PC meetings)

| Score | Meaning |
|---|---|
| **Accept** | Novel mechanism, real system, rigorous eval. Few caveats. |
| **Weak accept** | Solid contribution but one axis is thin (eval / novelty / scope). |
| **Weak reject** | Idea OK, execution wobbly. Often saved by rebuttal if eval gaps are addressable. |
| **Reject** | Engineering-only (no idea), or idea-only (no system), or eval is wrong workload / baselines. |

Rule-of-thumb: a single PC reviewer can usually kill a paper with a confidently
articulated "the comparison to X is missing" or "this can't work at production scale
because Y". Counter pre-emptively in §Evaluation.

## What does *not* land at OSDI

- Pure ML / algorithm papers with thin "we ran it on a GPU" framing — those belong
  at NeurIPS/ICML.
- Simulation-only systems work with no real implementation.
- "We ported X to Y" without a new mechanism.
- Application-level papers (databases, file systems built for one specific
  application) without a generalizable systems insight.
- Position / vision papers — OSDI does **not** accept these (try HotOS or HotNets).

## Bar for first-time submitters

Be unusually clear about: (1) what is **new** here vs. SOSP/OSDI/NSDI work in the
last 3 years, (2) **why a real system needs this** (not "it'd be elegant"), (3)
**what would falsify the claim** and your eval doing exactly that.

## Writing conventions (distilled from 4 OSDI '24/'25 refs)

Source files: `_venue-refs/chai-osdi25.md` (Fork in the Road),
`_venue-refs/zhang-dingyan-osdi25.md` (BlitzScale),
`_venue-refs/xu-osdi25.md` (DeDe),
`_venue-refs/fu-osdi24.md` (ServerlessLLM).

### Overall structure

- **7-9 numbered sections** is the modal shape.
  ServerlessLLM 8, BlitzScale 8 (+appendix), DeDe 9 (+appendix),
  Fork-in-the-Road ~7.  Weightlet's outline.md plans 8.
- **§1 Introduction** is always ~1.0-1.5 pages.  Opens with the
  workload reality or the cost gap, lands the headline number
  before the bottom of the first page (BlitzScale leads with 94%;
  ServerlessLLM with "10-200X").
- **§2** is *either* motivation/characterization *or* a
  problem-statement section that gathers the prior work and the
  gap.  ServerlessLLM, BlitzScale, and Chai use §2 as motivation
  + measurement.  DeDe uses §2 to taxonomize real-world problems.
  No standalone "§Background" lives outside §2; background is
  folded in.
- **Design section** (§3-§5 depending on system size) presents
  *named mechanisms*, one per subsection.  ServerlessLLM splits
  into 3 (loading format, migration, scheduling).  BlitzScale
  splits §5 into 4 subsections each labelled by *what the
  section delivers* ("Online network-based scale plan
  generation", not "Algorithm").
- **§Evaluation** is the largest section (~3-4 pages, ~30% of body).
  Always opens with the setup table.  Multiple subsections, each
  driven by one figure that targets one claim.
- **Related work** lives at §N-1 (just before conclusion) and is
  *short* (<1 page).  ServerlessLLM and BlitzScale both place
  Discussion *before* Related Work; consider this for Weightlet.

### Section-by-section voice

- **§1**: opens with the workload, *not* with the system name.
  Numbers in the first page.  Three of four refs lead the first
  sentence with the problem area, not "we".
- **§2**: leads with measurement, not theory.  Production refs
  (Chai, ServerlessLLM) lean even harder this way.  Use real
  trace plots / measurement tables in the first two paragraphs.
- **§Design**: each subsection opens with a one-sentence
  *mechanism statement*.  Reviewer should grasp what the section
  delivers before any context.  Worked example before formalism
  (DeDe's pattern) where the mechanism is non-obvious.
- **§Evaluation**: each subsection follows the pattern *figure →
  what it shows → what it proves*.  Three sentences minimum.
  Name the baselines (vLLM, Dragonfly, ServerlessLLM) explicitly
  in prose, not only via numeric cite markers.
- **§7 (Discussion)**: pre-empts reviewer objections.  DeDe's
  separate §4 "Generality and Limitations" is a strong pattern;
  worth folding into Weightlet's §7.

### Figure / table economy

- **Figure count varies widely**: ServerlessLLM ~10-12, BlitzScale 26,
  DeDe 8.  Median ~10-12 figures for a 12-page body.
- **Table count**: 1-3 main tables.  All four use booktabs
  (`\toprule`, `\midrule`, `\bottomrule`).  No vertical rules.
  Compact column headers.
- **Figure types**: data plots (line, bar, CDF) dominate.  At most
  one architecture diagram.  DeDe uses a *taxonomy table* (its
  Table 1) to position prior work — a strong device for §6
  Related Work.
- **Caption length**: full paragraph, not a one-line label.
  Describes the takeaway, not just the axes.

### Citation patterns

- **USENIX numeric style** `[n]` is the OSDI default.
- **Citations come after the introduced concept**, not as the
  noun: `Sarathi-Serve~\cite{...}` not `as shown in [12]`.
- **Density**: 60-80 references for a 12-page body.  Our current
  motivation.tex has 5 cite keys; expect to grow to ~50 across
  the full paper after intro/design/eval/related-work land.
- **Comparative naming**: name baselines and prior systems in
  prose alongside the cite marker, so the reader does not have
  to chase numbers.

### Anti-patterns observed by absence

- **No "we propose"** anywhere in the four refs.  Lead with the
  mechanism or measurement, not the proposal.
- **No marketing adjectives without numbers**.  "Substantially
  better" never appears alone; it always carries a number.
- **No section starts with the system name**.  "Weightlet does X"
  is fine in body; "Weightlet is a system that..." as a section
  opener is not.
- **Em-dashes are common in OSDI (BlitzScale uses them
  liberally)**.  Weightlet has chosen to avoid them per the user's
  feedback on motivation.tex; this is a stylistic deviation from
  modal OSDI prose but is internally consistent.

### Concrete moves we should adopt for Weightlet

1. **Lead §1 with the workload, not the system** (all 4 refs).
   Weightlet's current intro.tex already does this.
2. **Lock the headline number into §1's first page** (BlitzScale,
   ServerlessLLM).  Deferred until §5 stabilises.
3. **Three named-mechanism subsections in §3** (ServerlessLLM
   structure).  Matches outline.md §3.2 / §3.3 / §3.4.
4. **Worked example before formalism for the split-spec format**
   (DeDe pedagogy).
5. **Taxonomy table in §6 Related Work** (DeDe Table 1; outline.md
   Tbl 3 already plans this).
6. **Booktabs throughout; compact column headers; full-paragraph
   captions** (all 4 refs).
7. **Comparative naming in §5 prose** (ServerlessLLM): name vLLM,
   Dragonfly, ServerlessLLM in evaluation text, not only via
   `\cite{}`.
8. **Place §Discussion before §Related Work** (ServerlessLLM,
   BlitzScale).  Updates outline.md's current ordering.

## Figure style conventions (distilled from arXiv-rendered figures of 3 refs)

A deeper pass on figure aesthetics, beyond the count-and-type summary
in the previous section.  Observations come from the arXiv HTML
renderings of BlitzScale (2412.17246), DeDe (2412.11447), and
ServerlessLLM (2401.14351).  Fork-in-the-Road's figures were not
extractable (USENIX-only PDF; 403 to WebFetch), so it does not
contribute.

### Quick cross-paper table

| Dimension                  | BlitzScale                      | DeDe                          | ServerlessLLM                       |
|---|---|---|---|
| Palette per plot           | 1 colour on early panels; 3-4 on comparison plots | 2-4 colours (blue/orange/green) | 3-6 colours (blue/orange/green/grey) |
| Gridlines                  | light horizontal                | light horizontal              | light horizontal                    |
| Legend placement           | inside plot, varies (UL/UR)     | inside plot, UR or UL         | inside plot, UL or UR by density    |
| Annotation density         | high (labels, leader lines, dashed refs) | moderate (text labels in schematics) | high (numeric speedup labels above bars) |
| Architecture diagrams      | 1 (system overview)             | 2 (overview + decomposition)  | 1 (cluster overview)                |
| Multi-panel composites     | many (Fig 1 three panels, Fig 17 six subpanels) | one (Figs 4-8 are siblings)   | common (Fig 8 six subpanels, Fig 10 grouped bars) |
| Caption form               | paragraph (3-5 lines)           | mixed: short on schematics, paragraph on data | paragraph on data; short on small subfigures |

### Borrowable conventions

1. **Palette: 2-4 colours per plot, colourblind-safe.**
   ServerlessLLM and DeDe both stay around blue/orange/green; greys
   appear only as baselines or backgrounds.  Avoid more than 5
   distinct hues per panel.  When showing one series, prefer a
   single saturated colour (BlitzScale's early panels stay
   monochrome on purpose).
2. **Gridlines: light horizontal only.**  All 3 refs use thin
   light-grey horizontal gridlines and no vertical gridlines.
   The y-axis is the one the reader reads; helping them is
   acceptable.  Heavy black gridlines or grids on architecture
   diagrams do not appear.
3. **Legend inside the plot, not in a side rail.**  All 3 refs
   place legends inside the plot area, upper-left or upper-right
   depending on where the data permits empty space.  Legend
   typeface matches the body font (serif) at ~8pt.
4. **Axis convention: linear is default; log only when needed.**
   No log axes are visible in the BlitzScale/DeDe/ServerlessLLM
   figures we extracted, despite some of their metrics spanning
   wide ranges.  Linear axes communicate magnitude more directly.
   Reserve log y for >2 orders of magnitude span.
5. **Annotation use: numbers above bars, dashed refs at
   thresholds, shaded regions for gaps.**  ServerlessLLM labels
   speedup ratios directly above bars ("6X", "8.2X"); BlitzScale
   uses dashed reference lines for layer-completion / SLA
   markers; DeDe annotates toy examples with the concrete values
   the reader will trace.  This is heavier annotation than the
   field average; OSDI papers can afford it because reviewers
   skim figures first.
6. **Caption style: paragraph form for data plots, short label
   only for schematics.**  Data figures (bar, line, CDF) earn
   3-5 line paragraph captions starting with what they show then
   what they imply.  Architecture-diagram captions can stay
   short ("Overview of DeDe") because the labels inside the
   diagram do the work.
7. **Architecture diagrams: 1-2 per paper, no clip-art.**  Boxes
   for named components; arrows labelled with the payload they
   carry (data type, byte size, or "snapshot path") not just an
   arrowhead.  ServerlessLLM Fig 1 colours different module
   classes with different fill colours.  No cartoon icons or
   stock illustrations.
8. **Multi-panel composites for comparisons across workloads /
   scenarios.**  Both BlitzScale and ServerlessLLM use 4-6
   subpanels of the same chart type to compare the same metric
   across multiple workloads (BurstGPT vs AzureCode vs
   AzureConv, etc.).  Subpanels are labelled (a)-(f) and share
   axes.  This is the right shape when you have one claim
   stress-tested against many regimes.

### Anti-patterns observed by absence (or only in one outlier)

- **3-D plots, double y-axes, stacked-bar chart with > 4 strata,
  pie charts**: none of the 3 refs use these.  Skip.
- **>5 series on a line plot**: avoid; DeDe's 4-6-series plots
  in Figs 4-8 are at the upper edge already.
- **Tiny figure inset within a figure**: not seen.  Use a
  separate subpanel instead.
- **26-figure papers**: BlitzScale is at the outlier end with
  ~26 figures.  ServerlessLLM and DeDe sit at 10-12 and 8
  respectively, which is the comfortable range.  Weightlet's
  current count (3 in §2; ~4 more planned for §5) lands in the
  conservative end of normal.

### How Weightlet's current 3 figures score against this

- **`fig:layer-dedup` (2x2 grid)** — matches: light gridlines,
  paragraph caption, multi-panel composite for the granularity
  sweep.  Palette uses 2 colours (blue + orange) ✓.
- **`fig:nydus-dedup-panel` (3-bar chart)** — matches: legend
  inline (annotation box), dashed reference line for the kill
  threshold, paragraph caption.  Could optionally add direct
  numeric labels above bars (currently has them: 0.132, 0.153,
  0.915) ✓.
- **`fig:bytes-gap` (line chart with shaded gap)** — matches:
  legend inside plot upper-left, shaded gap for "the wedge
  Weightlet recovers", peak-gap arrow annotation, region labels
  ("LoRA-only" / "+ sibling FTs") ✓.

All three already follow the distilled conventions.  No refactor
needed for §2 figures.  Apply the same conventions to the §5
evaluation figures when they land (F1-F6 per
`weightlet/experiments/benchmark.md`).

## TODOs for this venue file

- [ ] Lock deadlines from official CFP (drops ~Jun 2026)
- [ ] Confirm page limit unchanged at 12
- [ ] Confirm rebuttal window length
- [ ] Confirm AE / artifact track requirements
- [ ] (Optional) Note PC chairs once announced — useful for taste calibration
