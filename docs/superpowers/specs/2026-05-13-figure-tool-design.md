---
title: Figure Tool — Design Spec
date: 2026-05-13
status: drafted — awaiting user review
owner: anne.x@gmicloud.ai
---

# `/figure` — Research-Assistant Drawing Tool

## 1 · Mission

A 6th MVP capability for `lucky-research`: **科研绘图**. Covers two figure kinds
the user produces while writing papers + running experiments:

| Kind | Examples | Source format | Generation path |
|---|---|---|---|
| **Structural** | architecture, pipeline, conceptual | hand-editable SVG | Claude writes raw `<svg>`; optional one-shot D2 scaffold |
| **Data** | accuracy curves, ablation bars, distribution plots | matplotlib `.py` script | Claude writes the script; user re-runs to refresh |

Plus a curated collection of **reference figures** (good paper figures the user
admires) under `inputs/figure-refs/`, indexed in AgentDB, that feed back into
generation as multimodal style references.

Output format depends on kind:

* **Structural figures** are produced as a **triple `{svg, pdf, png}`** — the
  SVG is the editable source (Claude writes it, the user iterates in Inkscape),
  the PDF + PNG are derived via cairosvg.
* **Data figures** are produced as a **pair `{pdf, png}`** — the matplotlib
  script `plot_<slug>.py` is the canonical source; no SVG is emitted.

LaTeX cites the `.pdf` explicitly (`\includegraphics{figures/<slug>.pdf}`), so
camera-ready packaging can grep that pattern and tar the referenced files
without ambiguity.

## 2 · Architecture

```
.claude/
  skills/figure-tool/SKILL.md       # the orchestration prompt
  commands/figure.md                # /figure slash entry

src/research_assistant/figures/
  __init__.py                       # public exports
  schema.py                         # Pydantic: FigureNote, FigureRef, PaletteSpec
  paths.py                          # cursor resolution + scope-aware paths
  export.py                         # svg → pdf/png (cairosvg); idempotent
  save.py                           # matplotlib save_all(fig, dir, slug) helper
  palettes.py                       # load palette presets + venue overrides
  refs.py                           # /figure ref add/list/sync/show
  d2.py                             # optional D2 scaffold helper
  styles/                           # PACKAGE-SHIPPED defaults
    palette/
      paper-mono.yml
      paper-trio.yml
      paper-extended.yml
      dark-on-light.yml
    mpl/
      paper-mono.mplstyle
      paper-trio.mplstyle
      paper-extended.mplstyle
      dark-on-light.mplstyle
    svg/
      defs.base.svg                 # shared arrow markers, gradients, fonts

docs/
  figure-note-template.md           # frontmatter template for <slug>.note.md
  figure-ref-template.md            # frontmatter template for inputs/figure-refs/*/note.md
  figure-palette-template.yml       # template for per-direction _palette.yml override

tests/
  test_figures_paths.py
  test_figures_export.py
  test_figures_refs.py
  test_figures_palettes.py
```

Module boundaries follow the existing DDD style (`experiments/`, `papers/`,
`mentor/`): figures has its own subpackage; everything cross-cutting goes
through `common/io.py`.

## 3 · Storage layout

### 3.1 Paper scope

```
outputs/papers/<venue>/<direction>/figures/
  <slug>.svg          # STRUCTURAL ONLY — source; Claude writes / user hand-edits in Inkscape
  <slug>.pdf          # structural: cairosvg-derived | data: matplotlib direct. LaTeX uses this.
  <slug>.png          # 300 DPI raster — slides / poster / raster-only journals
  <slug>.note.md      # YAML frontmatter (intent, refs, palette, size, backend, created)
  _palette.yml        # OPTIONAL — direction-scoped palette override
  _styles/defs.svg    # OPTIONAL — direction-scoped shared <defs>
  _scripts/           # for data-kind figures whose source is matplotlib
    plot_<slug>.py    # the canonical source for data figures (no .svg companion)
```

### 3.2 Experiment scope (inside bound repo)

```
outputs/experiments/<slug>/repo/   # ← user's bound GitHub repo, already cloned
  figures/
    <vN.M>/                        # versioned by experiment semver
      <plot>.svg                   # STRUCTURAL ONLY
      <plot>.pdf                   # structural: cairosvg-derived | data: matplotlib direct
      <plot>.png                   # 300 DPI raster
      <plot>.note.md
    _arch/                         # NON-versioned: pipeline / system diagrams
      <slug>.svg
      <slug>.pdf
      <slug>.png
      <slug>.note.md
  scripts/
    plot_<plot>.py                 # data-kind generator (sibling to existing
                                   #  plot_m3.py / plot_m4.py pattern)
```

Figures travel with the bound repo via `git push` — no extra mirror layer.
`/paper write` reads directly from `outputs/experiments/<slug>/repo/figures/<vN.M>/`
because the repo is already cloned locally.

### 3.3 Reference figures (gitignored, global)

```
inputs/figure-refs/<slug>/
  image.{png,pdf,jpg}     # the captured figure
  note.md                 # YAML frontmatter (source, kind, tags, palette, why_i_like_it)
```

Indexed in AgentDB namespace `project/figure-refs/<slug>`; vectorized text =
`source + kind + tags + why_i_like_it`. Global (cross-venue), parallel to
`inputs/past-work/` and `inputs/boss-profile/`.

### 3.4 Per-figure metadata `<slug>.note.md`

```yaml
---
slug: weightlet-arch
kind: structural               # structural | data
scope: paper                   # paper | experiment
anchor: papers/iclr-2026/main-direction   # or experiments/<exp-slug>/v1.2
intent: "用一张图让读者一秒看懂 weightlet 怎么在 attention head 之间共享参数"
size:
  width_in: 6.5
  height_in: 3.0
  preset: double-column-half   # single-column | double-column-half | double-column-full | custom
palette: paper-trio            # name from package-shipped or _palette.yml override
refs: [vaswani-transformer-arch, moe-shazeer-routing]
backend: raw-svg               # raw-svg | d2-scaffolded | matplotlib
created: 2026-05-13
---

Optional human notes / hand-tweak log below the frontmatter.
```

### 3.5 Reference-figure metadata `inputs/figure-refs/<slug>/note.md`

```yaml
---
slug: vaswani-transformer-arch
source: "Vaswani et al. 2017 (NeurIPS), Fig 1"
kind: structural               # structural | data | mixed
tags: [architecture, encoder-decoder, dual-column, callouts]
palette: ["#1f77b4", "#ff7f0e", "#2ca02c", "#d62728"]  # auto-extracted; user-editable
why_i_like_it: |
  - encoder/decoder 用左右对称布局，互照应
  - 用浅灰底色把 sub-layer 边界温柔区分
  - position encoding 这种"附加流"用细虚线，主流用粗实线
---
```

## 4 · User-facing surface

### 4.1 Slash command — `/figure`

```
/figure new <slug>                  # 6-step interactive generation
/figure list                        # current cursor's figures (paper or experiment)
/figure render <slug>               # re-derive pdf/png from edited svg
/figure render --all                # batch re-render current cursor's scope
/figure edit <slug>                 # print absolute path so user opens in Inkscape
/figure export <slug> --format jpeg --quality 90    # opt-in jpeg
/figure ref add [<file> | --url <u>]
/figure ref list [--kind structural|data] [--tag <t>]
/figure ref sync
/figure ref show <slug>
/figure                             # = list
```

### 4.2 `/figure new` interactive flow (6 steps)

| Step | Prompt | Mechanics |
|---|---|---|
| 0 | scope (only when both paper + experiment cursors exist) | persisted to this call only; not to cursor state |
| 1 | intent ("这张图要让读者一秒看懂什么？") | single sentence, written into `note.md` |
| 2 | kind (structural / data) | drives backend choice |
| 3 | refs | search `project/figure-refs/` for top-5 by intent+kind, show up to 3 (skip silently if empty), allow extra paths/URLs |
| 4 | size | preset suggestions derived from venue's `_venue.md` (column widths) + custom |
| 5 | palette | direction `_palette.yml` first if present, otherwise 3 from package defaults filtered by venue/kind; show ANSI swatches |
| (gen) | Claude generates source → `export()` → print LaTeX snippet | snippet always uses `\includegraphics{figures/<slug>.pdf}` |

### 4.3 Cursor resolution

- Paper cursor: AgentDB key `project/paper-context.current = (venue, direction)`
- Experiment cursor: AgentDB key `project/experiment-context.current = <exp-slug>`
- Both keys read at command start; if both present, step 0 asks for scope.
- Neither present → error: "先 `/paper venue` 或 `/experiment init`."

## 5 · Generation backends

### 5.1 Structural — raw SVG

Claude writes `<svg>` directly, obeying three repo conventions so the output is
Inkscape-friendly:

1. **viewBox in 96 DPI inches**: `viewBox="0 0 {W*96} {H*96}"`, where `W,H` come
   from step 4 size.
2. **Inkscape namespace + labeled layers**: every top-level `<g>` carries
   `inkscape:label="Layer/<purpose>"` (e.g. `Layer/boxes`, `Layer/arrows`,
   `Layer/labels`).
3. **Centralized styling**: colors, arrow markers, fonts go in `<defs>`
   (referenced by `<use>` or CSS classes) — never inline. So switching palette
   later edits one block.

### 5.2 Structural — D2 scaffold (optional fallback)

When Claude judges the figure is "boxes-with-auto-layout + arrows" (a
recognizable subset of system diagrams), it may:

1. Write a `.d2` source.
2. Shell `d2 -t 200 file.d2 file.svg`.
3. **Delete the `.d2`** (single source of truth = SVG from this point on).
4. Set `backend: d2-scaffolded` in `note.md`.

`d2` binary is **optional** — if not installed, the workflow gracefully
degrades to raw SVG.

### 5.3 Data — matplotlib

- One generator script per figure: `plot_<slug>.py` (paper scope `_scripts/` or
  experiment scope `scripts/`). **The script is the canonical source** —
  iterate by editing the script, not the rendered figure.
- Data source declared in the script's header docstring (path + columns +
  metric definition).
- Helper `figures.save.save_all(fig, dir, slug)` writes **`.pdf` and `.png`**
  in one call. **No SVG is produced** for data figures — the script is the
  source.
- Jupyter workflow: develop in a notebook if preferred, then export to `.py`
  via `jupytext --to py <name>.ipynb` or `File → Save As → .py`. The figure
  tool does not generate `.ipynb` files; the committed `plot_<slug>.py` is
  what the experiment / paper consumes.
- No `plotly` (HTML output incompatible with camera-ready). `seaborn` is
  permitted opportunistically (it sits on matplotlib).

### 5.4 Export pipeline

```python
# src/research_assistant/figures/export.py
def export(svg_path: Path, *, dpi: int = 300) -> tuple[Path, Path]:
    """Idempotent. Overwrites <svg_path>.pdf and .png from the SVG source.
    Returns (pdf_path, png_path)."""
```

- Called automatically at the end of `/figure new`.
- Called by `/figure render <slug>` after user hand-edits the SVG.
- Called by `/figure render --all` (recommended before submission).
- Failure on a single file is logged + non-fatal in `--all` mode.

## 6 · Palette system

### 6.1 Package-shipped presets (4)

| Name | Slots | Sequence | Use |
|---|---|---|---|
| `paper-mono` | black + 2 grays + 1 accent | 4 colors | safest single-column figs |
| `paper-trio` | primary/accent/baseline + highlight | 3 colors (Okabe-Ito subset, colorblind-safe) | standard 3-way comparisons |
| `paper-extended` | full Okabe-Ito | 8 colors | many-line ablations |
| `dark-on-light` | high-contrast white-bg | 4 colors | poster + slides reuse |

Each shipped as a `.yml` (color slots + named sequence) and a paired
`.mplstyle` (matplotlib rcParams), so SVG figures and matplotlib plots in the
same paper use identical colors.

### 6.2 Per-direction override

`outputs/papers/<venue>/<dir>/figures/_palette.yml` overrides for one
direction. `/figure new` step 5 detects this and offers it as the default
choice with 2 contrast alternatives.

### 6.3 Reference-figure palette extraction

`/figure ref add` runs `colorthief` on the captured image to pre-fill
`palette:` (top-6 dominant colors). User confirms / edits before the entry is
saved.

## 7 · Reference-figure workflow

### 7.1 `/figure ref add` intake

1. Locate input: positional file path, `--url <u>`, or scan
   `inputs/figure-refs/staging/`.
2. Prompt for slug (default: kebab-cased filename).
3. Prompt for source (paper citation + figure number).
4. Prompt for kind (`structural | data | mixed`).
5. Auto-suggest tags + `why_i_like_it` (Claude reads the image multimodally,
   proposes a draft, user edits inline).
6. Auto-extract palette via colorthief.
7. Write `inputs/figure-refs/<slug>/{image.<ext>, note.md}`.
8. Upsert into AgentDB `project/figure-refs/<slug>`.

### 7.2 How refs reach the generator

At `/figure new` step 3:

1. Build query: `{intent} {kind}` + intent-extracted style hints.
2. `memory_search` on `project/figure-refs/`, top-5.
3. Show top-3 with their `tags`, `why_i_like_it` excerpt, and palette swatches.
4. Accept user selection (numeric subset, `none`, or paths/URLs to add inline).
5. Pass selected ref images **as multimodal inputs to Claude** at generation
   time — Claude sees the actual pixels, not just the metadata.
6. Selected ref `palette` arrays get merged into step 5's palette candidate
   pool (user may want to mimic a ref's colors directly).
7. Record selected slugs in the new figure's `note.md` `refs:` field.

## 8 · Integration points

### 8.1 `/paper write` consumes figures

When drafting LaTeX that needs a figure, `/paper write`:

1. Lists `figures/*.pdf` in the current paper direction.
2. Matches by slug (intent / section keyword) or asks the user.
3. Emits the snippet **always** as:
   ```latex
   \begin{figure}[t]
     \centering
     \includegraphics[width=\columnwidth]{figures/<slug>.pdf}
     \caption{<from note.md intent, user-editable>}
     \label{fig:<slug>}
   \end{figure}
   ```
4. Width chosen from `size.preset`:
   - `single-column` → `\columnwidth`
   - `double-column-half` → `0.48\textwidth`
   - `double-column-full` → `\textwidth`
   - `custom` → `\columnwidth` (default; user adjusts)

### 8.2 `/experiment version add` link-back

When `/figure new --scope experiment` writes into
`repo/figures/<vN.M>/`, the helper appends to that version's
`versions/<vN.M>.md` frontmatter:

```yaml
figures:                                 # paths are extension-less stems;
  - repo/figures/v1.2/perf-vs-baseline   # consumers append .pdf / .svg / .png
  - repo/figures/v1.2/memory-breakdown   # depending on what they need
```

So `/experiment status`, `/experiment analyze`, and `/paper write` (when
referencing an experiment) can enumerate available figures.

### 8.3 Camera-ready packaging compatibility (future)

This spec does **not** implement camera-ready packaging — that belongs to
`paper-architect` / `ref-manager`. We only guarantee compatibility:

- All figures referenced from `.tex` use the literal pattern
  `\includegraphics{figures/<slug>.pdf}` (or `[opts]{figures/<slug>.pdf}`).
- Future `/paper render --camera-ready` can `grep -roP
  '\\includegraphics(\[[^\]]*\])?\{\K[^}]+(?=\})'` and tar exactly those files.

## 9 · Dependencies

| Purpose | Tool | Install | Required? |
|---|---|---|---|
| SVG → PDF/PNG export | `cairosvg` | pip | yes |
| Palette extraction from images | `colorthief` | pip | yes |
| matplotlib plots | `matplotlib` | pip (already in `pyproject.toml`) | yes (data figs only) |
| D2 scaffolding | `d2` binary | brew/curl install | **no** — graceful degrade |
| Inkscape (user, for hand-edit) | `inkscape` | OS package | no — user choice |

`cairosvg` + `colorthief` are pure-Python; we add them to `pyproject.toml`
under the main dependencies (not `[dev]`), and gate `figures.d2` with a
runtime check that prints "install d2: …" if missing.

## 10 · Error handling

| Failure | Behavior |
|---|---|
| No cursor set | Refuse with concrete next-step hint (`先 /paper venue …`) |
| Slug already exists in target dir | Refuse; suggest existing-or-new (`use --force to overwrite`) |
| Path traversal in user-supplied paths | Reject at boundary (mirror `experiments.py` guard) |
| `cairosvg` raises on malformed SVG | Print xml-lint location; SVG stays on disk; pdf/png skipped |
| `d2` binary missing in D2 path | Auto-fallback to raw SVG; warn once |
| `colorthief` fails on PDF input | Skip palette auto-extract; ask user to type colors manually |
| AgentDB unavailable | All ref operations degrade to file-only (slow but functional); warn once |
| Render --all has partial failures | Print summary table; non-zero exit if any failed |

## 11 · Testing strategy

- **Pure-function tests** (TDD London, mock filesystem): `slugify`, path
  resolution per scope, frontmatter parse/serialize round-trip, palette load
  + override hierarchy.
- **Export tests**: smoke-test `cairosvg` on a fixture SVG; verify `.pdf` and
  `.png` exist and are non-empty. Skip if `cairosvg` import fails (CI marker).
- **Refs tests**: temp `inputs/figure-refs/`, run add/list/sync round-trip,
  assert AgentDB upserts (mock the MCP client).
- **No integration test for D2** — gated by binary presence; document as
  manual verification.
- **No integration test for the Claude generation step** — the SVG-writing
  prompt is in `SKILL.md`; tested by skill review, not pytest.

## 12 · Non-goals (YAGNI)

- ❌ SVG live-preview server (VSCode renders SVG inline).
- ❌ PPT / Keynote import or export.
- ❌ Figure diff / version history beyond `git`.
- ❌ AI-driven figure-quality scoring.
- ❌ Sketch-to-SVG / handwriting upload (current multimodal quality is
  unreliable for paper figures).
- ❌ Auto-translation of palette to/from venue style guides beyond the 4
  shipped presets.
- ❌ Interactive WYSIWYG editor — defer to Inkscape, which the user already
  uses comfortably.

## 13 · Open questions (resolved during brainstorming)

| # | Question | Resolution |
|---|---|---|
| 1 | Where do figures live? | Paper scope `outputs/papers/<v>/<d>/figures/` + experiment scope inside bound repo `outputs/experiments/<slug>/repo/figures/<vN.M>/`. Refs collection at `inputs/figure-refs/`. |
| 2 | Structural backend? | Raw SVG primary; D2 optional one-shot scaffold, then drop the `.d2`. No Mermaid. |
| 3 | Data backend? | matplotlib; helper `save_all()` ships svg+pdf+png. |
| 4 | Default palettes? | 4: paper-mono / paper-trio / paper-extended / dark-on-light. |
| 5 | LaTeX include convention? | Explicit: `\includegraphics{figures/<slug>.pdf}`. |
| 6 | Mirror experiment figures? | No — repo path is already locally stable. |
| 7 | Auto-suggest tags + why_i_like_it on ref add? | Yes, Claude proposes; user edits. |
| 8 | Link figures back to experiment version? | Yes, append `figures:` to `versions/<vN.M>.md` frontmatter. |
| 9 | JPEG by default? | No — opt-in via `/figure export --format jpeg`. |

## 14 · Implementation phases (handoff to writing-plans)

The implementation plan will sequence:

1. **Module skeleton**: `src/research_assistant/figures/` package + Pydantic
   schemas + paths helper + tests for those.
2. **Export pipeline**: `export.py` + `save.py` + tests.
3. **Palette system**: load + 4 shipped presets + per-direction override +
   tests.
4. **References**: `refs.py` + `/figure ref *` flow + AgentDB integration +
   tests.
5. **Skill + slash command**: `.claude/skills/figure-tool/SKILL.md` +
   `.claude/commands/figure.md` with the 6-step interactive flow.
6. **Integration**:
   - `paper-architect` updated to enumerate `figures/*.pdf` and emit the
     fixed `\includegraphics` snippet.
   - `experiments.versions.append_figures()` hook.
7. **Dependencies**: add `cairosvg`, `colorthief` to `pyproject.toml`;
   document optional `d2` install in `SKILL.md`.
8. **Smoke test**: end-to-end on a real paper + a real experiment slug from
   the user's workspace.

---

**Status**: Spec written 2026-05-13, all 9 design questions resolved during
brainstorming. Awaiting user review before invoking `superpowers:writing-plans`.
