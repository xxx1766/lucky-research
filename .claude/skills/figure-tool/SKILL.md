---
name: figure-tool
description: Generate research figures — structural SVG (architecture / pipeline / concept) or data matplotlib plots — plus curate a reference-figure library. Each figure goes through a 6-step interactive flow (intent → kind → refs → size → palette → render) and lands in the correct paper or experiment scope. Triggered by /figure.
---

# figure-tool

> **Source spec:** `docs/superpowers/specs/2026-05-13-figure-tool-design.md`. Read it before
> the first invocation in any session.

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
| `list` (default) | `ls figures/*.pdf` under current scope; render a table with slug + kind + size + created. |
| `render <slug>` | `figures.export.export(svg_path)`. If the source is a matplotlib script, exec it instead. |
| `render --all` | walk current scope's `figures/**/*.svg` and `**/plot_*.py`; export each. Summary table at end. |
| `edit <slug>` | Print the absolute path of `<slug>.svg`. Do NOT modify. User opens in Inkscape. |
| `export <slug> --format jpeg --quality 90` | Re-render PNG, convert to JPEG (Pillow). Skip if user didn't pass `--format`. |
| `ref add [<file>\|--url <u>]` | See "Reference intake" below. |
| `ref list [--kind k] [--tag t]` | Read `research_assistant.figures.refs.list_refs()`, parse each via `read_ref(slug)`, filter, table. |
| `ref sync` | Walk `inputs/figure-refs/*/note.md`; for each, `to_agentdb_payload(ref)` → `mcp__claude-flow__memory_store`. |
| `ref show <slug>` | Print note.md + absolute image path. |

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
2. Decide D2 scaffold opt-in: if structure is genuinely auto-layout (boxes + arrows), generate a `.d2` source first, call `d2.scaffold_to_svg(...)`. If it returns `None`, fall back to raw SVG generation. If success, set `backend: d2-scaffolded`; otherwise `backend: raw-svg`.
3. Write `<slug>.svg` to the resolved figures dir.
4. Call `figures.export.export(svg_path)`. On `ExportError`, leave the SVG and tell the user to inspect.
5. Write `<slug>.note.md` via `figures.note.write_note(note_path, FigureNote(...), body="")`.
6. If `scope == "experiment"`, call `research_assistant.experiments.append_figures_to_version(slug=<exp-slug>, version=<vN.M>, figure_stems=["repo/figures/<vN.M>/<slug>"])`.
7. Print the LaTeX include snippet (see "Insert snippet" below).

For **kind=data**:
1. Write `plot_<slug>.py` to the scripts dir for this scope:
   - paper: `outputs/papers/<v>/<d>/figures/_scripts/plot_<slug>.py`
   - experiment: `outputs/experiments/<exp>/repo/scripts/plot_<slug>.py`
2. Script header includes a docstring with data source (path / columns / metric) confirmed in Step 1+3.
3. Script imports `from research_assistant.figures.save import save_all` and uses `matplotlib.style.use(<absolute-path-to-mplstyle>)` for the chosen palette.
4. Execute the script (Bash: `python <path-to-plot-script>`). Pipe output; if non-zero exit, surface stderr.
5. Write `<slug>.note.md` via `write_note(...)` with `backend: matplotlib`.
6. Experiment scope: same `append_figures_to_version` link-back as structural.
7. Print the LaTeX include snippet.

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
