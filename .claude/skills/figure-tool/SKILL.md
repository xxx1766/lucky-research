---
name: figure-tool
description: Generate research figures — structural SVG (architecture / pipeline / concept) or data matplotlib plots — plus curate a reference-figure library. Each figure goes through a 6-step interactive flow (intent → kind → refs → size → palette → render) and lands in the correct paper or experiment scope. Triggered by /figure.
---

# figure-tool

> **Source spec:** `docs/superpowers/specs/2026-05-13-figure-tool-design.md`. Read it before
> the first invocation in any session.
>
> **Required style prelude:** also read
> `.claude/skills/paper-architect/references/latex-conventions.md` sections
> `hard-rules` (no `;`, no `---`/`--`) and `tables-and-figures` (vector PDF,
> grayscale-resilient, ≤6 colors, arrow flow, font size between body and
> caption, caption answers "what is this"). The rules apply to figure
> captions, axis labels, legend text, and any text label inside a structural
> SVG.

## Mental model

A figure is one of two **kinds** (structural / data) under one of two **scopes** (paper / experiment).

```
                       /figure new <slug>
                              │
              ┌───────────────┴───────────────┐
        scope=paper                    scope=experiment
              │                                │
   outputs/papers/<v>/<d>/         outputs/experiments/<exp>/repo/
   figures/<slug>.{svg,pdf,png}    figures/<vN.M>/<slug>.{svg,pdf,png}   (data)
                                   figures/_arch/<slug>.{svg,pdf,png}    (structural)
```

Reference figures (style inspiration) are global:
`inputs/figure-refs/<slug>/{image, note.md}` + AgentDB
`project/figure-refs/<slug>`.

## Cursor reads (always do this first)

At every `/figure ...` invocation, read both cursors:

* `mcp__claude-flow__memory_retrieve` namespace=`project`, key=`paper-context.current`
  → expect `{"venue": "...", "direction": "..."}` or absent
* `mcp__claude-flow__memory_retrieve` namespace=`project`, key=`experiment-context.current`
  → expect `{"slug": "..."}` or absent

Call `research_assistant.figures.paths.resolve_scope(paper_ctx=..., experiment_ctx=..., cli_scope=...)` (all three args are keyword-only):

* `NoScopeError` → tell the user to run `/paper venue` or `/experiment init`.
* `AmbiguousScopeError` → ask "paper or experiment?" (step 0).

## Subcommand router

| Subcommand | Action |
|---|---|
| `new <slug>` | Run the 6-step interactive flow (below). |
| `recommend` | Suggest the right academic chart type from a pasted data snippet + one-sentence intent. Reads `references/chart-recommender-prompt.md` (19-chart library) and prints a structured recommendation; hands off to `/figure new <slug>` for actual generation. |
| `list` (default) | `ls figures/*.pdf` under current scope; render a table with slug + kind + size + created. |
| `render <slug>` | `figures.export.export(svg_path)`. If the source is a matplotlib script, exec it instead. |
| `render --all` | walk current scope's `figures/**/*.svg` and `**/plot_*.py`; export each. Summary table at end. |
| `edit <slug>` | Print the absolute path of `<slug>.svg`. Do NOT modify. User opens in Inkscape. |
| `export <slug> --format jpeg --quality 90` | Re-render PNG, convert to JPEG (Pillow). Skip if user didn't pass `--format`. |
| `ref add [<file>\|--url <u>]` | See "Reference intake" below. |
| `ref list [--kind k] [--tag t]` | Read `research_assistant.figures.refs.list_refs()`, parse each via `read_ref(slug)`, filter, table. |
| `ref sync` | Walk `inputs/figure-refs/*/note.md`; for each, `to_agentdb_payload(ref)` → `mcp__claude-flow__memory_store`. |
| `ref show <slug>` | Print note.md + absolute image path. |

## `/figure recommend` flow

A read-only decision-support subcommand. Does not write any file; prints a
recommendation and surfaces the natural next call (`/figure new <slug>`).

1. Resolve scope (cursor reads above) — needed only for the palette hint in
   the recommendation. Do **not** error on `NoScopeError`; the recommender
   is useful even before a paper or experiment exists.
2. Collect inputs (plain text, no `AskUserQuestion` per the
   `feedback_decision_ui` memory):
   - **Data snippet** — paste an Excel/CSV table, or a 2–3 line description
     of variables, axes, sample count, distribution shape.
   - **Core conclusion** — one sentence on what the figure must demonstrate.
3. Read `references/chart-recommender-prompt.md` as the prompt prelude
   (it embeds the 19-chart academic library verbatim).
4. Apply the prompt with the stitched `# Input` block.
5. Print the model's four-section response (推荐方案 · 核心理由 · 视觉设计
   规范) and the hand-off line: `Next: /figure new <slug>  (kind=data,
   chart=<推荐>)`.

## `/figure new` 6-step flow

**Step 0 — scope** (only if `AmbiguousScopeError`)
Ask in plain text (per memory rule on multi-option research picks): "Paper or experiment?" — accept `paper` / `experiment`. Persist only to this invocation.

**Step 1 — intent**
Ask: "这张图要让读者一秒看懂什么？" — one sentence. Store as the future `intent:` frontmatter.

**Step 2 — kind**
Ask: "structural 还是 data?" — accept `structural` / `data`. If `data`, also ask which experiment version (defaults to the latest if scope=experiment).

**Step 3 — references**
1. Build a query from `{intent} {kind}` + intent-extracted keywords.
2. Call `mcp__claude-flow__memory_search` namespace=`project/figure-refs`, query, topK=5.
3. Show up to 3 candidates as: `[N] <slug>  tags: ...  palette: <ANSI swatches>  why: <first line of why_i_like_it>`.
4. If the library is empty, skip silently. In any case, also accept inline paths/URLs (`+ <path>` or `+ <url>`).
5. Record the selected slugs for the future `refs:` field.

**Step 4 — size**
Read venue's `_venue.md` (if it exists at `outputs/papers/<v>/_venue.md`) for column widths. Offer 4 options:

```
[1] single-column         (3.3 in × auto)
[2] double-column-half    (6.5 in × 3.0 in)
[3] double-column-full    (7.0 in × auto)
[4] custom                (you type W H in inches)
```

**Step 5 — palette**
1. Resolve via `palette.load_palette_for_direction(figures_dir, fallback=<venue-recommended>)`.
2. If the direction has `_palette.yml`, default = that palette; also offer 2 alternatives from shipped (`paper-trio`, `paper-extended`).
3. Else, offer 3 shipped palettes filtered by `kind` and `size` (heuristics: single-column → mono/trio first; multi-line ablation → extended; poster/slides → dark-on-light).
4. Render each option with `palette.ansi_swatch(spec)`.

**Step 6 — render**

For **kind=structural**:
1. Construct the prompt for SVG generation, including:
   - Inkscape conventions from spec section 5.1 (viewBox in 96 DPI inches, namespace, labelled layers, `<defs>`-centralised styles).
   - Selected refs as multimodal image inputs.
   - The palette's hex colors and slot names.
   - The intent sentence.
   - **Project conventions** (from `latex-conventions.md` section `tables-and-figures`):
     vector-only (no raster embeds), grayscale-resilient (test by removing
     color — lines stay distinguishable by dash pattern, marker shape, or
     position), ≤6 colors total consistent within functional modules (same
     color means the same role across all figures in the paper), arrows flow
     in one general direction (left-to-right or top-to-bottom), prefer visual
     encodings over text labels for repeated information, figure text size
     between body and caption (typically 7–8 pt in two-column).
   - **Architecture-diagram style** (from `references/architecture-diagram-prompt.md`):
     flat-vector aesthetic in the DeepMind / OpenAI mold — pure-white
     background, soft palette, simple icons, English-only text labels, no
     long sentences inside boxes, no 3D shadows / sketch lines / photo-realism.
     This prelude carries the visual-style guidance adapted from the
     [awesome-ai-research-writing](https://github.com/Leey21/awesome-ai-research-writing)
     "论文架构图" entry; reproduce the Visual Constraints block verbatim
     when constructing the prompt.
   - **Hard rules** for any text inside the SVG (labels, legends,
     annotations): no `;` as punctuation, no `---` or `--` as prose
     punctuation. Restructure with commas or split labels.
2. Decide D2 scaffold opt-in: if structure is genuinely auto-layout (boxes + arrows), generate a `.d2` source first, call `d2.scaffold_to_svg(...)`. If it returns `None`, fall back to raw SVG generation. If success, set `backend: d2-scaffolded`; otherwise `backend: raw-svg`.
3. Write `<slug>.svg` to the resolved figures dir.
4. Call `figures.export.export(svg_path)`. On `ExportError`, leave the SVG and tell the user to inspect.
5. Write `<slug>.note.md` via `figures.note.write_note(note_path, FigureNote(...), body="")`.
6. If `scope == "experiment"`, call `research_assistant.experiments.append_figures_to_version(slug=<exp-slug>, version=<vN.M>, figure_stems=["repo/figures/<vN.M>/<slug>"])`.
7. Print the LaTeX include snippet (see "Insert snippet" below).

For **kind=data**:
0. **Trajectory shortcut.** If the intent contains "trajectory", "training
   curve", "metric over runs", or similar, and either (a) the user said
   "send to chat / paste into HTML" or (b) `matplotlib` is unavailable,
   reach for `references/trajectory-svg-recipe.md` *instead of* matplotlib.
   That recipe is a zero-dependency pure-Python SVG (~80 lines, adapted
   from Orchestra-Research/AI-Research-SKILLs MIT
   `0-autoresearch-skill`). Write `plot_<slug>.svg.py` (driver) +
   `<slug>.svg` next to it; skip the `cairosvg` / mplstyle path; set
   `backend: trajectory-svg` in the note. For all other "metric over
   time" plots, fall through to the matplotlib path below.
1. Write `plot_<slug>.py` to the scripts dir for this scope:
   - paper: `outputs/papers/<v>/<d>/figures/_scripts/plot_<slug>.py`
   - experiment: `outputs/experiments/<exp>/repo/scripts/plot_<slug>.py`
2. Script header includes a docstring with data source (path / columns / metric) confirmed in Step 1+3.
3. Script imports `from research_assistant.figures.save import save_all` and uses `matplotlib.style.use(<absolute-path-to-mplstyle>)` for the chosen palette. `save_all` writes **`.pdf` + `.png`** (no `.svg` — for data figures the script itself is the canonical source).
3a. **Project conventions** (from `latex-conventions.md` section `tables-and-figures`):
   - Axis labels, legend entries, and tick labels obey hard rules: no `;`, no
     `---`/`--`.
   - Math inside labels uses built-in operators (`\arg\max`, `\log`) and
     `\textrm{}` for multi-letter names (`\textrm{softmax}`).
   - Use the resolved palette's colors and the palette mplstyle; do not
     hardcode hex.
   - Limit visible series to ≤6 and design for grayscale: pair each color
     with a distinct marker or dash pattern so the figure survives black-and-
     white printing.
4. Jupyter-friendly: if the user prefers to iterate in a notebook, develop in Jupyter and export to `.py` via `jupytext --to py <name>.ipynb` or `File → Save As → .py`. The committed `plot_<slug>.py` stays the source of truth; the figure-tool does not generate `.ipynb` files.
5. Execute the script (Bash: `python <path-to-plot-script>`). Pipe output; if non-zero exit, surface stderr.
6. Write `<slug>.note.md` via `write_note(...)` with `backend: matplotlib`.
7. Experiment scope: same `append_figures_to_version` link-back as structural.
8. Print the LaTeX include snippet.

## Insert snippet

After every successful `/figure new` and `/figure render`, print exactly:

```
✓ Files: <abs-path>.svg / .pdf / .png
✓ Note:  <abs-path>.note.md
✓ LaTeX include (copy into your .tex):

    \begin{figure}[t]
      \centering
      \includegraphics[width={WIDTH}]{figures/<slug>.pdf}
      \caption{<intent>}
      \label{fig:<slug>}
    \end{figure}
```

`{WIDTH}` from `size.preset`:
* `single-column` → `\columnwidth`
* `double-column-half` → `0.48\textwidth`
* `double-column-full` → `\textwidth`
* `custom` → `\columnwidth` (let user adjust)

For **experiment scope**, the include path is `repo/figures/<vN.M>/<slug>.pdf` instead.

**Caption rules** (apply when the user pastes the snippet into their `.tex`,
and again when `/paper write` drafts the surrounding section):
* The caption answers *what is this*. Let the body text answer *what does it
  mean*.
* Hard rules: no `;`, no `---` or `--`. Restructure with commas or split into
  two sentences.
* Quantify any claim that the figure shows a `good` or `better` result. State
  the metric and the magnitude.
* Define every acronym in the caption on first use within the caption.
* **Format rules** (from `paper-architect/references/latex-conventions.md`
  section `tables-and-figures` → "Caption format"): decide case by syntax —
  noun phrase = Title Case, no period; complete sentence = Sentence case,
  end with period. Don't open with `The figure shows ...` / `This diagram
  illustrates ...`. Don't use `showcase` / `depict`. No `Figure 1:` prefix
  in the source.
* **Chinese intent → English caption.** Step 1 collects `intent:` as one
  Chinese sentence. When emitting the LaTeX snippet, **polish the intent to
  an English caption per the rules above** — do not paste the raw Chinese.
  Persist both: `intent:` in `note.md` stays Chinese (for future recall);
  the `\caption{...}` argument is the polished English.

## Reference intake — `/figure ref add`

1. Resolve the input image: positional `<file>`, `--url <u>` (curl into `inputs/figure-refs/staging/`), or scan `inputs/figure-refs/staging/`.
2. Ask: slug (default = kebab of filename).
3. Ask: source citation.
4. Ask: kind (`structural` / `data` / `mixed`).
5. Auto-suggest tags + why_i_like_it: read the image multimodally, propose 1 paragraph for `why_i_like_it` and a short list of `tags`. **Show the suggestion and ask the user to confirm / edit / replace**.
6. Auto-extract palette: `palette.extract_palette_from_image(image_path, count=6)`. Show; user may override.
7. Build a `FigureRef`, call `refs.add_ref(image_path, ref)`.
8. Call `mcp__claude-flow__memory_store` with `refs.to_agentdb_payload(ref)`.

## Error policy

| Failure | Behaviour |
|---|---|
| `NoScopeError` | Refuse with hint: `先 /paper venue 或 /experiment init` |
| `AmbiguousScopeError` | Ask step-0 "paper or experiment?" |
| Slug exists in target dir | Refuse; suggest `--force` |
| Path traversal | Reject at boundary (`paths.safe_join` raises) |
| `cairosvg` raises | Print error; SVG stays; pdf/png skipped |
| `d2` missing or fails | Auto-fall-back to raw SVG; one-line info |
| AgentDB unreachable (for `ref sync` / `ref add`) | Filesystem ops complete; warn once that index is stale |

## When NOT to use this skill

* Wrappers / packaging logic for camera-ready submissions — that belongs to `paper-architect` / `ref-manager`.
* Editing already-existing SVGs by hand — print the path with `/figure edit`; the user opens in Inkscape themselves.
