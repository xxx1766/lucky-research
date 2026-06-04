# Stage 6 workflow detail (`/paper write [section]`)

Load this when actually drafting a section. The main SKILL has the high-level
triggers; this file has the full decision flow.

## Cross-cutting principles enforced in this stage

- **Drafting order is not IMRAD.** The default order is
  **figures → method → results → related-work → intro → abstract → title**.
  Method first because it locks the vocabulary every other section reuses; intro
  late because its funnel depends on the headline number from results; title
  last because the abstract narrows what the title can promise.
- **Title is provisional at outline time, final after abstract stabilises.**
  Stage 6 ends with a `title-revisit` step that re-reads `\title{}` against the
  now-stable abstract.
- **Funnel-gate the introduction.** Before drafting `intro`, print a plain-text
  prompt: `"Funnel check: have you discussed broad → existing → best →
  limitations → this paper's goal with your advisor? (yes / draft anyway /
  abort)"`. On `abort`, stop without writing. (Plain text, not
  `AskUserQuestion` — research picks belong in the chat.)
- **Banned phrases in intro.** After writing `sections/intro.tex`, grep
  case-insensitively for `novel`, `first ever`, `first time`,
  `paradigm-changing`, `paradigm-shifting`, `we propose`. Any hit prints a
  warning with line numbers — do not auto-rewrite, the user decides.
- **Hard-rule lint (every section).** After writing any `.tex` file in this
  stage, grep for the three project hard rules (full definitions in
  `latex-conventions.md` section `hard-rules`):
  * `;` on a line that is not pure LaTeX command and does not contain `\;`
    spacing and is not inside a `verbatim` / `lstlisting` / `minted` block →
    warn with line numbers.
  * `---` anywhere → warn with line numbers.
  * `--` not matching `\d+--\d+` (numeric range) → warn with line numbers.
  Print warnings only. Do not auto-rewrite; the user decides.
- **Chinese translation comments.** When writing or rewriting any English
  paragraph in a `.tex` file under `outputs/papers/<venue>/<direction>/` (body
  prose only — skip `algorithms/*.tex`, `refs.bib`, and the preamble), emit
  the Chinese translation immediately above the paragraph as `%` LaTeX
  comments. One `%` line per English source line, wrap to similar visual
  width. If a Chinese comment block already exists above a paragraph you
  rewrite, update the Chinese to match the new English so the two stay in
  sync. See `latex-conventions.md` section `hard-rules` for the exact shape.

## Preflight gate (run before drafting anything)

Adapted from the *hard gate* discipline in
[joshua-zyy/academic-paper-writer](https://github.com/joshua-zyy/academic-paper-writer):
a section is not drafted until its prerequisites exist on disk.

1. Resolve the section kind first (synonym map below), then call:

   ```python
   research_assistant.papers.write_preflight(
       direction_dir,            # outputs/papers/<venue>/<direction>/
       venue_dir,                # outputs/papers/<venue>/
       section_kind,             # resolved kind, or None for the outline scaffold call
       evidence_present=...,     # for results-kind: bool from
                                 # collect_experiment_results_for_paper(); else omit
   )
   ```

2. The returned `PreflightResult` carries two strengths of gate:
   - **blocking** → if `result.blocked`, print `result.render()` and **STOP**.
     The user clears the named gate (or re-runs `/paper write <section> --force`
     to override). Blocking gates:
     * `venue` — `_venue.md` missing → `/paper venue <slug>`.
     * `focus` — `focused-problem.md` missing → `/paper focus`.
     * `literature` — drafting `intro` / `related-work` with an empty
       `related-papers/` and no `literature_exempt: true` in `expert.md` →
       `/paper scout` (or set the exempt flag).
   - **warning** → drafting proceeds, but echo `result.render()` so the user
     sees it. The one warning gate:
     * `evidence` — a `results` section with no experiment result yet. Allowed,
       but every reported number MUST be a `[DATA_NEEDED: …]` placeholder until
       `/experiment version add` lands a real value.

3. `--force` skips the **blocking** check only (warnings still print). Use it
   when the user knowingly drafts ahead of a prerequisite.

## Placeholder tokens (evidence-first)

**Never fabricate a citation, a number, or a result.** When the support for a
claim is not yet on hand, leave an explicit token instead of an invented fact —
the gap is tracked as a *debt* that a later stage closes:

| Token | Use when | Closed by |
|---|---|---|
| `[REF_NEEDED: <what to cite>]` | a claim needs a citation you don't have a `\cite{slug}` for | `/paper scout` + `/cite` |
| `[FIGURE_NEEDED: <what it shows>]` | a figure is referenced but not yet rendered | `/figure new <slug>` |
| `[DATA_NEEDED: <which number, from where>]` | a result/number needs an experiment version | `/experiment version add` |
| `[CLAIM_UNVERIFIED: <the assertion>]` | an assertion you have not checked | `/paper verify` (batch 2) / manual |

Rules:
- A token is plain bracketed text in the prose (it renders visibly in the PDF —
  that visibility is the point). Do **not** hide a gap in a `%` comment.
- Prefer a real `\cite{slug}` over `[REF_NEEDED]` whenever a matching
  `papers/<slug>` exists — the token is only for genuinely missing support.
- Once a token's support lands, replace the token with the real citation /
  `\includegraphics` / number.

## Workflow

### If no section given (first write call)

1. Generate `outline.md` — section-by-section plan grounded in `expert.md` +
   `focused-problem.md` + `experiments/`. Markdown, not LaTeX.
2. Scaffold the LaTeX skeleton if missing:
   - `<direction>/main.tex` — `\documentclass` pointing at `../_template/`,
     `\input`s each `sections/<name>.tex`, sets `\bibliography{refs}`.
   - `<direction>/sections/` — empty directory.
   - `<direction>/refs.bib` — empty file.
   - Call `research_assistant.pseudocode.preamble.ensure_preamble(<direction>/main.tex, venue_md_path=<venue>/_venue.md)`
     so the algorithm package (`algorithm + algpseudocode` by default, or
     `algorithm2e` if the venue opts in) is in the preamble from day one.
     Idempotent — safe to call on every write.
3. **Surface unmade figures.** Read `outline.md`'s figure table; for every row
   whose source figure isn't in `figures/` (or, for experiment-scope figures,
   `repo/figures/<vN.M>/`), print `→ /figure new <slug>` so figures land before
   Method drafting (figures lock the vocabulary the prose then quotes).
4. **Print the recommended next-call sequence** in the blog's order, mapped
   onto the outline's actual section names. Use the synonym map in
   `section-heuristics.md` (`design`/`approach` → `method` kind,
   `evaluation`/`eval` → `results` kind, …). Example output:

   ```
   Recommended drafting order:
     1. /paper write design        # method kind
     2. /paper write evaluation    # results kind
     3. /paper write related-work
     4. /paper write discussion
     5. /paper write intro         # funnel-gated
     6. /paper write abstract
     7. /paper write title         # revisit \title{}
   ```

   One section per invocation — the skill does not auto-loop.

### If section given (`intro` / `method` / `results` / `discussion` / ...)

1. **Resolve the section's kind** via the synonym map in
   `section-heuristics.md` and read the matching `## section: <kind>` block.
   If no match, use `## section: default`. **Also layer the family block** —
   read the matching `## family: <family>` → `### <kind>` sub-block (when one
   exists) and treat its Extra Do / Extra Don't / Extra Beats items as
   additions to the default kind block. The default kind block always
   applies; the family block stacks on top.
2. **Read the cross-cutting block** plus `expert.md`, `focused-problem.md`,
   `experiments/*`, `related-papers/`, `outline.md`'s block for this section,
   and any existing `sections/*.tex` for tone + terminology consistency.

   2.5. **For `results`-kind sections, pull in bound-experiment outputs.**
   Call `research_assistant.papers.collect_experiment_results_for_paper(venue, direction)`
   to enumerate every experiment bound to this direction, paired with its
   latest mirrored `outputs/experiments/<slug>/results/<latest>/`. For each
   hit:
   - If `analysis_tex` is set, **read it** and treat it as the experiment's
     authoritative result paragraphs — designed to be pasted under
     `\section{Results}` with no rewriting. `/experiment analyze` enforces
     the no-`\textbf` / no-`\emph` / `\paragraph{Title Case}` shape.
   - If `analysis_md` is set, read it too — that's the audit log with
     Chinese translation that lets you spot-check numbers you reuse.
   - If `results_dir` is set but `analysis_tex` is `None`, the user has
     run `version add` but not yet `/experiment analyze`. Print a one-line
     hint (`→ /experiment analyze` for `<slug>`) and continue drafting
     from the raw mirrored files in `other_files`.
   - If `latest_version` is `None`, the experiment is bound but no version
     has been registered. Skip it for prose; surface a hint instead.
3. **Intro gate.** If kind is `intro`, run the funnel check above; on
   `abort`, stop.
4. **Title revisit.** If kind is `title`, do not draft a new section file —
   instead: read the current `\title{}` from `main.tex` and the abstract from
   `sections/abstract.tex`; propose 3 revised titles (8–12 English words,
   concise + specific, no banned padding); let the user pick (plain text) or
   reply with their own; rewrite `\title{...}` in `main.tex`. Skip the
   `% TODO` block and the figure/algorithm includes (none apply to titles).
5. **Draft `<direction>/sections/<section>.tex`.** Prepend the heuristics
   block's Do / Don't / Beats lists at the top of your reasoning before
   writing — every paragraph should be traceable to a beat. **Cite directly
   as `\cite{<slug>}`** (no `[@cite:]` placeholder). `<slug>` should match
   `papers/<slug>` in AgentDB so `/cite` can resolve it into `refs.bib`.
   **Evidence-first:** for any claim whose support is not yet on hand, leave a
   placeholder token (`[REF_NEEDED]` / `[FIGURE_NEEDED]` / `[DATA_NEEDED]` /
   `[CLAIM_UNVERIFIED]`, see "Placeholder tokens" above) — never invent a
   citation, number, or result to fill the gap.
6. **Banned-phrase scan.** If kind is `intro`, after writing the file run
   `grep -niE 'novel|first ever|first time|paradigm-(changing|shifting)|we propose' sections/intro.tex`
   and print each hit; suggest a rewrite but leave the file as-is.
7. Append a `% TODO:` LaTeX comment block listing experiments still needed.
8. **Placeholder audit.** Call
   `research_assistant.papers.scan_placeholders(direction_dir)` and, if the
   list is non-empty, print a short table (`token · file:line · hint`) so the
   user sees exactly which debts this draft opened. This is reporting only — do
   not rewrite. The same debts roll up into the progress footer (see below).

### Auto-render after every successful section write

1. Verify `outputs/papers/<venue>/_template/` exists and is non-empty. If
   missing, print the expected drop location and **skip** the render — the
   `.tex` write itself still succeeded.
2. Shell out to `tectonic` (preferred) or fall back to `latexmk -pdf`. Run
   from the direction directory so `../_template/` resolves.
3. On success: tell the user the path to `main.pdf`.
4. On build failure: print the last ~40 lines of the log; do **not** undo
   the write. User fixes the `.tex` and runs `/paper render` to retry.
5. If neither toolchain is on PATH: print install hints
   (`brew install tectonic` / `cargo install tectonic` /
   `apt install texlive-latex-extra`) and skip the render.

**Drift snapshot (for the mentor).** After a successful write, refresh the
lightweight outline snapshot the weekly check-in reads as a paper-activity
signal:

```
mcp__claude-flow__memory_store(
    namespace="drafts", key=f"{venue}/{direction}",
    value=<outline.md contents, or the section list + \title{} if no outline yet>,
    metadata={"venue": venue, "direction": direction,
              "sections": [<section names written>]},
)
```

`research-mentor`'s `/mentor` check-in searches `drafts/*` to detect a paper
that's been quiet; without this write that signal is always empty. Skip it only
if AgentDB is unreachable (warn once, continue).

After everything above (whether the render fired or not), print the footer
**with the debt roll-up** so any tokens just opened are visible:
`render_progress_footer(venue, direction, stage_status(direction_dir), debt_summary(direction_dir))`.

## Figure inclusion

When the section being drafted needs a figure:

1. List `figures/*.pdf` in the current direction.
2. If a slug matches the section's keyword (read the corresponding
   `<slug>.note.md` `intent:` field for the match), pick it; otherwise list
   the available slugs and ask the user.
3. Emit the include block exactly in this form (no `\graphicspath`, explicit
   path with `.pdf` extension):

```latex
\begin{figure}[t]
  \centering
  \includegraphics[width=<W>]{figures/<slug>.pdf}
  \caption{<polished English caption — see Caption format below>}
  \label{fig:<slug>}
\end{figure}
```

The caption argument follows `latex-conventions.md` section
`tables-and-figures` → "Caption format": noun phrase = Title Case (no
period), complete sentence = Sentence case (with period); no
`The figure shows ...` openers; no `showcase` / `depict`. When the figure's
`note.md` `intent:` is Chinese, polish it to an English caption per those
rules before pasting — don't emit raw Chinese into `\caption{...}`.

`<W>` is chosen from the figure's `size.preset`:

* `single-column` → `\columnwidth`
* `double-column-half` → `0.48\textwidth`
* `double-column-full` → `\textwidth`
* `custom` → `\columnwidth`

If no matching `figures/<slug>.pdf` exists, suggest the user runs
`/figure new <slug>` first — do not synthesise a placeholder include.

For **experiment-scope** figures (referenced from a paper section discussing
that experiment), the include path uses `repo/figures/<vN.M>/<slug>.pdf` —
read the experiment's `versions/<vN.M>.md` `figures:` list (populated by
`/figure new --scope experiment`) to enumerate.

## Algorithm inclusion

When the section being drafted needs an algorithm (method / approach
sections almost always do):

1. List `algorithms/*.tex` in the current direction.
2. If a slug matches a section keyword (read the corresponding
   `<slug>.note.md` `intent:` field for the match), pick it; otherwise list
   the available slugs and ask the user. Each algorithm `.tex` is
   self-contained — it already carries `\begin{algorithm} ... \end{algorithm}`,
   so the section just `\input{}`s it (no extra wrapping).
3. Emit the include block exactly in this form:

```latex
\input{algorithms/<slug>.tex}
```

   Or, if the section refers to the algorithm in prose without immediately
   placing it, use `See Algorithm~\ref{alg:<slug>}.` and `\input{...}` the
   algorithm at the natural reading position.

4. If no matching `algorithms/<slug>.tex` exists, suggest the user runs
   `/pseudocode new <slug>` first — do not synthesise a placeholder algorithm
   box. Pseudocode is method-level documentation; it must be authored
   deliberately, not auto-generated from incomplete context.

5. The required `\usepackage` lines are kept in `main.tex` by
   `pseudocode.preamble.ensure_preamble(...)` (called during scaffold and on
   first `/pseudocode new`). No action needed here.

For **experiment-scope** algorithms (referenced from a paper section
discussing that experiment), the include path is
`algorithms/<vN.M>/<slug>.tex`. Surface this only when the algorithm is
intrinsically tied to one experiment version (e.g. an ablated sampler);
otherwise prefer the paper-scope variant.
