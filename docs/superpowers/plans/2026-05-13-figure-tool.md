# Figure Tool Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Implement the `/figure` slash command and `figure-tool` skill so users can generate structural SVG figures + matplotlib data plots, plus curate a reference-figure library — all integrated with `/paper` and `/experiment`.

**Architecture:** New Python subpackage `src/research_assistant/figures/` (DDD style, parallels `papers/` and `experiments/`). Pure-Python deterministic helpers (cairosvg export, matplotlib save, palette load, frontmatter I/O, path/scope resolution, reference indexing payload). AgentDB I/O lives in the skill prompt, not Python — Python helpers raise `NotImplementedError` for AgentDB and provide `to_agentdb_payload()` formatters. One new `.claude/skills/figure-tool/SKILL.md` + `.claude/commands/figure.md` drives the 6-step interactive flow.

**Tech Stack:** Python 3.12, Pydantic v2, cairosvg, colorthief, matplotlib, PyYAML. Optional: `d2` binary (graceful fallback). Tests in pytest, mocking filesystem and AgentDB.

**Source spec:** `docs/superpowers/specs/2026-05-13-figure-tool-design.md`

---

## File Map

**Create (Python package):**
- `src/research_assistant/figures/__init__.py` — re-exports
- `src/research_assistant/figures/schema.py` — Pydantic models (`FigureNote`, `FigureRef`, `PaletteSpec`)
- `src/research_assistant/figures/paths.py` — scope/cursor → output dir resolution; slugify
- `src/research_assistant/figures/note.py` — read/write per-figure YAML frontmatter
- `src/research_assistant/figures/palette.py` — load palette YAML, render ANSI swatch, colorthief extract
- `src/research_assistant/figures/export.py` — `export(svg_path)` via cairosvg
- `src/research_assistant/figures/save.py` — matplotlib `save_all(fig, dir, slug)` helper
- `src/research_assistant/figures/refs.py` — figure-refs intake + `to_agentdb_payload`
- `src/research_assistant/figures/d2.py` — optional D2 scaffold with graceful fallback

**Create (shipped style assets):**
- `src/research_assistant/figures/styles/palette/{paper-mono,paper-trio,paper-extended,dark-on-light}.yml` (4 files)
- `src/research_assistant/figures/styles/mpl/{paper-mono,paper-trio,paper-extended,dark-on-light}.mplstyle` (4 files)
- `src/research_assistant/figures/styles/svg/defs.base.svg`

**Create (templates):**
- `docs/figure-note-template.md`
- `docs/figure-ref-template.md`
- `docs/figure-palette-template.yml`

**Create (skill + slash):**
- `.claude/skills/figure-tool/SKILL.md`
- `.claude/commands/figure.md`

**Create (tests):**
- `tests/test_figures_paths.py`
- `tests/test_figures_note.py`
- `tests/test_figures_palette.py`
- `tests/test_figures_export.py`
- `tests/test_figures_refs.py`
- `tests/test_figures_d2.py`

**Modify:**
- `pyproject.toml` — add `cairosvg>=2.7`, `colorthief>=0.2.1`, `matplotlib>=3.8`, `pyyaml>=6.0`
- `src/research_assistant/common/io.py` — add `FIGURE_REFS_DIR` constant + include in `ensure_dirs`
- `src/research_assistant/experiments/__init__.py` — add `append_figure_to_version(slug, version, fig_stem)` helper
- `.claude/skills/paper-architect/SKILL.md` — extend `write` stage to list figures + emit standard `\includegraphics` snippet
- `CLAUDE.md` — add `/figure` row to MVP table

---

## Task 1: Add Python dependencies + figures package skeleton

**Files:**
- Modify: `pyproject.toml:8-15`
- Create: `src/research_assistant/figures/__init__.py`

- [ ] **Step 1: Edit `pyproject.toml` to add the new dependencies**

Replace the `dependencies = [...]` block (currently 6 lines) with:

```toml
dependencies = [
    "pymupdf>=1.24",       # PDF text extraction for lit-summarize
    "arxiv>=2.1",          # arXiv metadata + PDF fetch
    "openreview-py>=1.0",  # Venue-aware paper sourcing (ICLR/NeurIPS/COLM/TMLR)
    "bibtexparser>=1.4",   # BibTeX parse/merge for ref-manager
    "pypandoc>=1.13",      # Markdown / LaTeX / docx conversion
    "pydantic>=2.7",       # Typed schemas for summaries, ideas, project state
    "cairosvg>=2.7",       # SVG → PDF/PNG export for figure-tool
    "colorthief>=0.2.1",   # Palette auto-extract from reference images
    "matplotlib>=3.8",     # Data figures (figure-tool data kind)
    "pyyaml>=6.0",         # YAML frontmatter parse/serialize
]
```

- [ ] **Step 2: Install the new deps**

Run: `pip install -e ".[dev]"`
Expected: succeeds; `python -c "import cairosvg, colorthief, matplotlib, yaml; print('ok')"` prints `ok`.

- [ ] **Step 3: Create the package skeleton**

Write `src/research_assistant/figures/__init__.py`:

```python
"""Figure-tool helpers — schema + I/O + export + palette + refs.

Each figure lives under either:
  * paper scope:      outputs/papers/<venue>/<direction>/figures/<slug>.{svg,pdf,png}
  * experiment scope: outputs/experiments/<slug>/repo/figures/<vN.M>/<slug>.{svg,pdf,png}
                      (or repo/figures/_arch/<slug>.{svg,pdf,png} for non-versioned)

Reference figures (the curated "good paper figures" collection) live at
inputs/figure-refs/<slug>/ — gitignored, indexed in AgentDB project/figure-refs/<slug>.

Mirrors three patterns already in the codebase:
  * research_assistant.papers for stage status + path resolution.
  * research_assistant.mentor.past_work for Pydantic models + AgentDB payload defer.
  * research_assistant.experiments for path-traversal guards + slugify.
"""
from __future__ import annotations
```

- [ ] **Step 4: Verify the package imports**

Run: `python -c "import research_assistant.figures; print('ok')"`
Expected: prints `ok`.

- [ ] **Step 5: Commit**

```bash
git add pyproject.toml src/research_assistant/figures/__init__.py
git commit -m "feat(figures): add cairosvg/colorthief/matplotlib/pyyaml deps + package skeleton"
```

---

## Task 2: Define Pydantic schemas

**Files:**
- Create: `src/research_assistant/figures/schema.py`
- Create: `tests/test_figures_schema.py`

- [ ] **Step 1: Write the failing test**

Write `tests/test_figures_schema.py`:

```python
"""Schema round-trip and validation tests for figure-tool models."""
from datetime import date

import pytest
from pydantic import ValidationError

from research_assistant.figures.schema import (
    FigureNote,
    FigureRef,
    FigureSize,
    PaletteSpec,
)


def test_figure_size_round_trip():
    size = FigureSize(width_in=6.5, height_in=3.0, preset="double-column-half")
    assert size.width_in == 6.5
    assert size.preset == "double-column-half"


def test_figure_size_rejects_negative():
    with pytest.raises(ValidationError):
        FigureSize(width_in=-1.0, height_in=3.0, preset="custom")


def test_figure_note_minimum_valid():
    note = FigureNote(
        slug="weightlet-arch",
        kind="structural",
        scope="paper",
        anchor="papers/iclr-2026/main",
        intent="One-second comprehension of weightlet sharing.",
        size=FigureSize(width_in=6.5, height_in=3.0, preset="double-column-half"),
        palette="paper-trio",
        refs=["vaswani-transformer-arch"],
        backend="raw-svg",
        created=date(2026, 5, 13),
    )
    assert note.slug == "weightlet-arch"
    assert note.backend == "raw-svg"


def test_figure_note_rejects_unknown_kind():
    with pytest.raises(ValidationError):
        FigureNote(
            slug="x", kind="cartoon", scope="paper", anchor="a", intent="i",
            size=FigureSize(width_in=1.0, height_in=1.0, preset="custom"),
            palette="paper-mono", refs=[], backend="raw-svg",
            created=date(2026, 5, 13),
        )


def test_figure_ref_minimum_valid():
    ref = FigureRef(
        slug="vaswani-transformer-arch",
        source="Vaswani et al. 2017 (NeurIPS), Fig 1",
        kind="structural",
        tags=["architecture", "encoder-decoder"],
        palette=["#1f77b4", "#ff7f0e"],
        why_i_like_it="Symmetric layout.",
    )
    assert ref.slug == "vaswani-transformer-arch"
    assert ref.kind == "structural"


def test_palette_spec_load():
    p = PaletteSpec(
        name="paper-trio",
        slots={"primary": "#0072B2", "accent": "#D55E00"},
        sequence=["#0072B2", "#D55E00", "#009E73"],
        colorblind_safe=True,
        suggested_for=["single-column"],
    )
    assert p.name == "paper-trio"
    assert p.colorblind_safe is True
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_figures_schema.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'research_assistant.figures.schema'`.

- [ ] **Step 3: Write the schemas**

Write `src/research_assistant/figures/schema.py`:

```python
"""Pydantic models for figure-tool: FigureNote, FigureRef, PaletteSpec, FigureSize.

Source of truth on disk:
  * <slug>.note.md per generated figure (YAML frontmatter parses into FigureNote)
  * inputs/figure-refs/<slug>/note.md (parses into FigureRef)
  * src/research_assistant/figures/styles/palette/<name>.yml (parses into PaletteSpec)
"""
from __future__ import annotations

from datetime import date
from typing import Literal

from pydantic import BaseModel, Field, field_validator


FigureKind = Literal["structural", "data", "mixed"]
FigureScope = Literal["paper", "experiment"]
FigureBackend = Literal["raw-svg", "d2-scaffolded", "matplotlib"]
SizePreset = Literal[
    "single-column", "double-column-half", "double-column-full", "custom"
]


class FigureSize(BaseModel):
    width_in: float = Field(gt=0)
    height_in: float = Field(gt=0)
    preset: SizePreset


class FigureNote(BaseModel):
    """Frontmatter of <slug>.note.md next to every generated figure."""

    slug: str
    kind: FigureKind
    scope: FigureScope
    anchor: str   # papers/<v>/<d> or experiments/<exp>/v1.2
    intent: str
    size: FigureSize
    palette: str  # palette name (matches a PaletteSpec.name)
    refs: list[str] = Field(default_factory=list)
    backend: FigureBackend
    created: date

    @field_validator("kind")
    @classmethod
    def kind_excludes_mixed(cls, v: str) -> str:
        # Generated figures are either structural or data; "mixed" reserved for refs.
        if v == "mixed":
            raise ValueError("FigureNote.kind must be 'structural' or 'data'; 'mixed' is for FigureRef only")
        return v


class FigureRef(BaseModel):
    """Frontmatter of inputs/figure-refs/<slug>/note.md."""

    slug: str
    source: str
    kind: FigureKind   # structural | data | mixed
    tags: list[str] = Field(default_factory=list)
    palette: list[str] = Field(default_factory=list)   # hex colors
    why_i_like_it: str = ""


class PaletteSpec(BaseModel):
    """Palette loaded from styles/palette/<name>.yml."""

    name: str
    slots: dict[str, str]
    sequence: list[str]
    colorblind_safe: bool = False
    suggested_for: list[str] = Field(default_factory=list)
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_figures_schema.py -v`
Expected: 6 tests PASS.

- [ ] **Step 5: Commit**

```bash
git add src/research_assistant/figures/schema.py tests/test_figures_schema.py
git commit -m "feat(figures): Pydantic schemas — FigureNote / FigureRef / PaletteSpec / FigureSize"
```

---

## Task 3: Path resolution + scope cursor handling

**Files:**
- Modify: `src/research_assistant/common/io.py:18-30` (add `FIGURE_REFS_DIR`)
- Create: `src/research_assistant/figures/paths.py`
- Create: `tests/test_figures_paths.py`

- [ ] **Step 1: Extend `common/io.py` with `FIGURE_REFS_DIR`**

Edit `src/research_assistant/common/io.py`. After the `FLEET_INPUT_PATH = ...` line (around line 18), add:

```python
FIGURE_REFS_DIR = INPUTS_DIR / "figure-refs"
FIGURE_REFS_STAGING_DIR = FIGURE_REFS_DIR / "staging"
```

In `ensure_dirs()`, append `FIGURE_REFS_DIR` and `FIGURE_REFS_STAGING_DIR` to the iterable.

- [ ] **Step 2: Write the failing test**

Write `tests/test_figures_paths.py`:

```python
"""Path / slug / scope-resolution tests for figures package."""
from pathlib import Path

import pytest

from research_assistant.figures import paths as fp


def test_slugify_kebab_case():
    assert fp.slugify("Weightlet Architecture") == "weightlet-architecture"
    assert fp.slugify("CNN vs. Transformer") == "cnn-vs-transformer"
    assert fp.slugify("  spaced  ") == "spaced"


def test_slugify_rejects_empty():
    with pytest.raises(ValueError):
        fp.slugify("   ")


def test_paper_figures_dir(tmp_path, monkeypatch):
    fake_papers = tmp_path / "papers"
    monkeypatch.setattr(fp, "PAPERS_DIR", fake_papers)
    out = fp.paper_figures_dir("ICLR-2026", "main-direction")
    assert out == fake_papers / "ICLR-2026" / "main-direction" / "figures"


def test_experiment_figures_dir_versioned(tmp_path, monkeypatch):
    fake_exp = tmp_path / "experiments"
    monkeypatch.setattr(fp, "EXPERIMENTS_DIR", fake_exp)
    out = fp.experiment_figures_dir("weightlet-motivation", version="v1.2")
    assert out == fake_exp / "weightlet-motivation" / "repo" / "figures" / "v1.2"


def test_experiment_figures_dir_arch(tmp_path, monkeypatch):
    fake_exp = tmp_path / "experiments"
    monkeypatch.setattr(fp, "EXPERIMENTS_DIR", fake_exp)
    out = fp.experiment_figures_dir("weightlet-motivation", version=None)
    assert out == fake_exp / "weightlet-motivation" / "repo" / "figures" / "_arch"


def test_resolve_scope_paper_only():
    out = fp.resolve_scope(
        paper_ctx=("ICLR-2026", "main"),
        experiment_ctx=None,
        cli_scope=None,
    )
    assert out == "paper"


def test_resolve_scope_experiment_only():
    out = fp.resolve_scope(
        paper_ctx=None,
        experiment_ctx="weightlet-motivation",
        cli_scope=None,
    )
    assert out == "experiment"


def test_resolve_scope_both_requires_explicit():
    with pytest.raises(fp.AmbiguousScopeError):
        fp.resolve_scope(
            paper_ctx=("ICLR-2026", "main"),
            experiment_ctx="weightlet-motivation",
            cli_scope=None,
        )


def test_resolve_scope_both_with_cli_choice():
    out = fp.resolve_scope(
        paper_ctx=("ICLR-2026", "main"),
        experiment_ctx="weightlet-motivation",
        cli_scope="experiment",
    )
    assert out == "experiment"


def test_resolve_scope_neither_errors():
    with pytest.raises(fp.NoScopeError):
        fp.resolve_scope(paper_ctx=None, experiment_ctx=None, cli_scope=None)


def test_safe_join_blocks_traversal(tmp_path):
    with pytest.raises(ValueError):
        fp.safe_join(tmp_path, "../escape")
    with pytest.raises(ValueError):
        fp.safe_join(tmp_path, "/absolute/path")
```

- [ ] **Step 3: Run test to verify it fails**

Run: `pytest tests/test_figures_paths.py -v`
Expected: FAIL with `ModuleNotFoundError`.

- [ ] **Step 4: Write the implementation**

Write `src/research_assistant/figures/paths.py`:

```python
"""Path + slug + scope-cursor resolution for figure-tool.

The "scope" decision (paper vs experiment) is made by the skill MD by reading
AgentDB cursors (project/paper-context.current, project/experiment-context.current)
and calling :func:`resolve_scope` with the read values.
"""
from __future__ import annotations

import re
from pathlib import Path
from typing import Literal

from research_assistant.common.io import EXPERIMENTS_DIR, PAPERS_DIR

_SLUG_CLEAN = re.compile(r"[^a-z0-9]+")


class NoScopeError(RuntimeError):
    """Neither paper nor experiment cursor is set — user must run /paper venue or /experiment init."""


class AmbiguousScopeError(RuntimeError):
    """Both cursors set; caller must supply cli_scope to disambiguate."""


def slugify(title: str) -> str:
    cleaned = _SLUG_CLEAN.sub("-", title.lower()).strip("-")
    if not cleaned:
        raise ValueError(f"empty figure slug for title={title!r}")
    return cleaned


def paper_figures_dir(venue: str, direction: str) -> Path:
    return PAPERS_DIR / venue / direction / "figures"


def experiment_figures_dir(slug: str, *, version: str | None) -> Path:
    base = EXPERIMENTS_DIR / slug / "repo" / "figures"
    return base / version if version else base / "_arch"


def resolve_scope(
    *,
    paper_ctx: tuple[str, str] | None,
    experiment_ctx: str | None,
    cli_scope: Literal["paper", "experiment"] | None,
) -> Literal["paper", "experiment"]:
    """Decide which scope a /figure new is targeting.

    paper_ctx     — (venue, direction) tuple if /paper cursor is set
    experiment_ctx — exp slug if /experiment cursor is set
    cli_scope     — explicit override from --scope (or step-0 answer)
    """
    if cli_scope is not None:
        if cli_scope not in ("paper", "experiment"):
            raise ValueError(f"cli_scope must be 'paper' or 'experiment', got {cli_scope!r}")
        return cli_scope
    if paper_ctx and experiment_ctx:
        raise AmbiguousScopeError(
            "Both /paper and /experiment cursors are set; ask the user which scope this figure belongs to."
        )
    if paper_ctx:
        return "paper"
    if experiment_ctx:
        return "experiment"
    raise NoScopeError(
        "No paper or experiment cursor is set. Run /paper venue or /experiment init first."
    )


def safe_join(base: Path, user_relative: str) -> Path:
    """Reject path traversal and absolute paths. Mirrors the experiments.py guard."""
    if user_relative.startswith("/") or user_relative.startswith("\\"):
        raise ValueError(f"absolute paths are not allowed: {user_relative!r}")
    resolved = (base / user_relative).resolve()
    base_resolved = base.resolve()
    try:
        resolved.relative_to(base_resolved)
    except ValueError as e:
        raise ValueError(f"path escapes base: {user_relative!r}") from e
    return resolved
```

- [ ] **Step 5: Run test to verify it passes**

Run: `pytest tests/test_figures_paths.py tests/test_smoke.py -v`
Expected: paths tests PASS; smoke test still passes (no regressions in io.py).

- [ ] **Step 6: Commit**

```bash
git add src/research_assistant/common/io.py src/research_assistant/figures/paths.py tests/test_figures_paths.py
git commit -m "feat(figures): path + scope resolver + FIGURE_REFS_DIR"
```

---

## Task 4: Frontmatter read/write for `<slug>.note.md`

**Files:**
- Create: `src/research_assistant/figures/note.py`
- Create: `tests/test_figures_note.py`

- [ ] **Step 1: Write the failing test**

Write `tests/test_figures_note.py`:

```python
"""Per-figure frontmatter round-trip tests."""
from datetime import date
from pathlib import Path

import pytest

from research_assistant.figures import note as fn
from research_assistant.figures.schema import FigureNote, FigureSize


def _sample() -> FigureNote:
    return FigureNote(
        slug="weightlet-arch",
        kind="structural",
        scope="paper",
        anchor="papers/iclr-2026/main",
        intent="One-second comprehension of weightlet sharing.",
        size=FigureSize(width_in=6.5, height_in=3.0, preset="double-column-half"),
        palette="paper-trio",
        refs=["vaswani-transformer-arch"],
        backend="raw-svg",
        created=date(2026, 5, 13),
    )


def test_write_and_parse_round_trip(tmp_path: Path):
    path = tmp_path / "weightlet-arch.note.md"
    fn.write_note(path, _sample(), body="Optional human notes.\n")
    loaded = fn.read_note(path)
    assert loaded.note == _sample()
    assert loaded.body.strip() == "Optional human notes."


def test_write_overwrites(tmp_path: Path):
    path = tmp_path / "x.note.md"
    fn.write_note(path, _sample(), body="first")
    fn.write_note(path, _sample(), body="second")
    assert "second" in path.read_text()
    assert "first" not in path.read_text()


def test_read_note_rejects_no_frontmatter(tmp_path: Path):
    path = tmp_path / "bad.note.md"
    path.write_text("no frontmatter here\n")
    with pytest.raises(ValueError):
        fn.read_note(path)


def test_read_note_rejects_bad_yaml(tmp_path: Path):
    path = tmp_path / "bad.note.md"
    path.write_text("---\nslug: x\nkind: invalid-kind\n---\n")
    with pytest.raises(Exception):  # ValidationError from pydantic
        fn.read_note(path)
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_figures_note.py -v`
Expected: FAIL with `ModuleNotFoundError`.

- [ ] **Step 3: Write the implementation**

Write `src/research_assistant/figures/note.py`:

```python
"""Read/write per-figure <slug>.note.md (YAML frontmatter + free body)."""
from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path

import yaml

from research_assistant.figures.schema import FigureNote

_FM_RE = re.compile(r"^---\n(.*?)\n---\n?(.*)$", re.DOTALL)


@dataclass
class LoadedNote:
    note: FigureNote
    body: str


def write_note(path: Path, note: FigureNote, *, body: str = "") -> None:
    """Write a <slug>.note.md atomically. Overwrites if present."""
    payload = note.model_dump(mode="json")
    yaml_text = yaml.safe_dump(payload, sort_keys=False, allow_unicode=True).rstrip("\n")
    text = f"---\n{yaml_text}\n---\n"
    if body:
        text += f"\n{body.rstrip()}\n"
    path.write_text(text, encoding="utf-8")


def read_note(path: Path) -> LoadedNote:
    """Parse a <slug>.note.md into a typed LoadedNote."""
    text = path.read_text(encoding="utf-8")
    m = _FM_RE.match(text)
    if not m:
        raise ValueError(f"{path} has no YAML frontmatter")
    fm = yaml.safe_load(m.group(1)) or {}
    note = FigureNote.model_validate(fm)
    body = m.group(2).strip()
    return LoadedNote(note=note, body=body)
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_figures_note.py -v`
Expected: 4 tests PASS.

- [ ] **Step 5: Commit**

```bash
git add src/research_assistant/figures/note.py tests/test_figures_note.py
git commit -m "feat(figures): frontmatter read/write for <slug>.note.md"
```

---

## Task 5: Ship the 4 palette + mplstyle assets and base SVG defs

**Files:**
- Create: `src/research_assistant/figures/styles/palette/{paper-mono,paper-trio,paper-extended,dark-on-light}.yml`
- Create: `src/research_assistant/figures/styles/mpl/{paper-mono,paper-trio,paper-extended,dark-on-light}.mplstyle`
- Create: `src/research_assistant/figures/styles/svg/defs.base.svg`

- [ ] **Step 1: Write `paper-mono.yml`**

```yaml
# src/research_assistant/figures/styles/palette/paper-mono.yml
name: paper-mono
slots:
  primary: "#000000"
  baseline: "#808080"
  baseline_alt: "#BFBFBF"
  accent: "#D55E00"
sequence: ["#000000", "#808080", "#BFBFBF", "#D55E00"]
colorblind_safe: true
suggested_for: [single-column, IEEE, ACM, monochrome-print]
```

- [ ] **Step 2: Write `paper-trio.yml`**

```yaml
# src/research_assistant/figures/styles/palette/paper-trio.yml
name: paper-trio
slots:
  primary: "#0072B2"
  accent: "#D55E00"
  baseline: "#909090"
  highlight: "#E69F00"
sequence: ["#0072B2", "#D55E00", "#009E73"]
colorblind_safe: true
suggested_for: [single-column, IEEE, ACM]
```

- [ ] **Step 3: Write `paper-extended.yml`**

```yaml
# src/research_assistant/figures/styles/palette/paper-extended.yml
name: paper-extended
slots:
  primary: "#0072B2"
  accent: "#D55E00"
  baseline: "#909090"
  highlight: "#E69F00"
sequence: ["#000000", "#E69F00", "#56B4E9", "#009E73", "#F0E442", "#0072B2", "#D55E00", "#CC79A7"]
colorblind_safe: true
suggested_for: [multi-line-ablation, double-column, supplementary]
```

- [ ] **Step 4: Write `dark-on-light.yml`**

```yaml
# src/research_assistant/figures/styles/palette/dark-on-light.yml
name: dark-on-light
slots:
  primary: "#1F2937"
  accent: "#DC2626"
  baseline: "#6B7280"
  highlight: "#EAB308"
sequence: ["#1F2937", "#DC2626", "#16A34A", "#7C3AED"]
colorblind_safe: false
suggested_for: [poster, slides, talk-figures]
```

- [ ] **Step 5: Write the 4 matching `.mplstyle` files**

Each `.mplstyle` sits next to its palette and pins matplotlib rcParams. Write `paper-mono.mplstyle`:

```
# src/research_assistant/figures/styles/mpl/paper-mono.mplstyle
axes.prop_cycle: cycler('color', ['000000', '808080', 'BFBFBF', 'D55E00'])
axes.spines.top: False
axes.spines.right: False
axes.grid: True
grid.color: "#E5E5E5"
grid.linewidth: 0.5
font.family: serif
font.size: 9
axes.labelsize: 9
xtick.labelsize: 8
ytick.labelsize: 8
legend.fontsize: 8
figure.dpi: 150
savefig.bbox: tight
savefig.transparent: False
```

Write `paper-trio.mplstyle`:

```
# src/research_assistant/figures/styles/mpl/paper-trio.mplstyle
axes.prop_cycle: cycler('color', ['0072B2', 'D55E00', '009E73'])
axes.spines.top: False
axes.spines.right: False
axes.grid: True
grid.color: "#E5E5E5"
grid.linewidth: 0.5
font.family: serif
font.size: 9
axes.labelsize: 9
xtick.labelsize: 8
ytick.labelsize: 8
legend.fontsize: 8
figure.dpi: 150
savefig.bbox: tight
savefig.transparent: False
```

Write `paper-extended.mplstyle`:

```
# src/research_assistant/figures/styles/mpl/paper-extended.mplstyle
axes.prop_cycle: cycler('color', ['000000', 'E69F00', '56B4E9', '009E73', 'F0E442', '0072B2', 'D55E00', 'CC79A7'])
axes.spines.top: False
axes.spines.right: False
axes.grid: True
grid.color: "#E5E5E5"
grid.linewidth: 0.5
font.family: serif
font.size: 9
axes.labelsize: 9
xtick.labelsize: 8
ytick.labelsize: 8
legend.fontsize: 8
figure.dpi: 150
savefig.bbox: tight
savefig.transparent: False
```

Write `dark-on-light.mplstyle`:

```
# src/research_assistant/figures/styles/mpl/dark-on-light.mplstyle
axes.prop_cycle: cycler('color', ['1F2937', 'DC2626', '16A34A', '7C3AED'])
axes.spines.top: False
axes.spines.right: False
axes.grid: False
font.family: sans-serif
font.size: 11
axes.labelsize: 11
xtick.labelsize: 10
ytick.labelsize: 10
legend.fontsize: 10
figure.dpi: 200
savefig.bbox: tight
savefig.transparent: False
```

- [ ] **Step 6: Write `defs.base.svg`**

Write `src/research_assistant/figures/styles/svg/defs.base.svg`:

```xml
<?xml version="1.0" encoding="UTF-8"?>
<svg xmlns="http://www.w3.org/2000/svg" xmlns:inkscape="http://www.inkscape.org/namespaces/inkscape">
  <defs>
    <!-- Arrow marker — closed triangle, scales with line width -->
    <marker id="arrow-closed" viewBox="0 0 10 10" refX="9" refY="5"
            markerWidth="6" markerHeight="6" orient="auto-start-reverse">
      <path d="M 0 0 L 10 5 L 0 10 z" fill="currentColor"/>
    </marker>
    <!-- Arrow marker — open V, for secondary flows -->
    <marker id="arrow-open" viewBox="0 0 10 10" refX="9" refY="5"
            markerWidth="6" markerHeight="6" orient="auto-start-reverse">
      <path d="M 0 0 L 10 5 L 0 10" fill="none" stroke="currentColor" stroke-width="1.5"/>
    </marker>
    <!-- Dash pattern for "auxiliary / secondary" connections -->
    <pattern id="dash-aux" patternUnits="userSpaceOnUse" width="6" height="1">
      <line x1="0" y1="0" x2="3" y2="0" stroke="currentColor" stroke-width="1"/>
    </pattern>
  </defs>
</svg>
```

- [ ] **Step 7: Verify all 9 files exist**

Run: `ls src/research_assistant/figures/styles/palette/*.yml src/research_assistant/figures/styles/mpl/*.mplstyle src/research_assistant/figures/styles/svg/defs.base.svg | wc -l`
Expected: `9`.

- [ ] **Step 8: Commit**

```bash
git add src/research_assistant/figures/styles/
git commit -m "feat(figures): ship 4 palette presets (yml + mplstyle) + base SVG defs"
```

---

## Task 6: Palette loader + ANSI swatch + per-direction override

**Files:**
- Create: `src/research_assistant/figures/palette.py`
- Create: `tests/test_figures_palette.py`

- [ ] **Step 1: Write the failing test**

Write `tests/test_figures_palette.py`:

```python
"""Palette load, override, and ANSI swatch tests."""
from pathlib import Path

import pytest

from research_assistant.figures import palette as fp
from research_assistant.figures.schema import PaletteSpec


def test_load_shipped_palettes_all_four():
    for name in ("paper-mono", "paper-trio", "paper-extended", "dark-on-light"):
        spec = fp.load_palette(name)
        assert isinstance(spec, PaletteSpec)
        assert spec.name == name
        assert len(spec.sequence) >= 3


def test_load_unknown_palette_raises():
    with pytest.raises(FileNotFoundError):
        fp.load_palette("does-not-exist")


def test_list_shipped_palettes():
    names = fp.list_shipped_palettes()
    assert set(names) == {"paper-mono", "paper-trio", "paper-extended", "dark-on-light"}


def test_direction_override_takes_precedence(tmp_path: Path):
    direction_dir = tmp_path / "papers" / "ICLR-2026" / "main"
    fig_dir = direction_dir / "figures"
    fig_dir.mkdir(parents=True)
    (fig_dir / "_palette.yml").write_text(
        "name: custom-direction\n"
        "slots: {primary: '#111111'}\n"
        "sequence: ['#111111', '#222222']\n"
        "colorblind_safe: false\n"
        "suggested_for: []\n"
    )
    spec = fp.load_palette_for_direction(fig_dir, fallback="paper-trio")
    assert spec.name == "custom-direction"


def test_direction_override_falls_back_to_shipped(tmp_path: Path):
    fig_dir = tmp_path / "figures"
    fig_dir.mkdir()
    spec = fp.load_palette_for_direction(fig_dir, fallback="paper-trio")
    assert spec.name == "paper-trio"


def test_ansi_swatch_contains_color_blocks():
    spec = fp.load_palette("paper-trio")
    swatch = fp.ansi_swatch(spec)
    # ANSI true-color escape: ESC[48;2;R;G;Bm
    assert "\x1b[48;2;" in swatch
    # Reset sequence
    assert "\x1b[0m" in swatch
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_figures_palette.py -v`
Expected: FAIL with `ModuleNotFoundError`.

- [ ] **Step 3: Write the implementation**

Write `src/research_assistant/figures/palette.py`:

```python
"""Palette loading: shipped presets + per-direction overrides + ANSI swatch rendering."""
from __future__ import annotations

from pathlib import Path

import yaml

from research_assistant.figures.schema import PaletteSpec

_SHIPPED_DIR = Path(__file__).parent / "styles" / "palette"


def list_shipped_palettes() -> list[str]:
    return sorted(p.stem for p in _SHIPPED_DIR.glob("*.yml"))


def load_palette(name: str) -> PaletteSpec:
    path = _SHIPPED_DIR / f"{name}.yml"
    if not path.exists():
        raise FileNotFoundError(f"palette '{name}' not found in {_SHIPPED_DIR}")
    data = yaml.safe_load(path.read_text(encoding="utf-8"))
    return PaletteSpec.model_validate(data)


def load_palette_for_direction(figures_dir: Path, *, fallback: str) -> PaletteSpec:
    """Look for `_palette.yml` in the direction's figures/ dir; fall back to a shipped name."""
    override = figures_dir / "_palette.yml"
    if override.exists():
        data = yaml.safe_load(override.read_text(encoding="utf-8"))
        return PaletteSpec.model_validate(data)
    return load_palette(fallback)


def ansi_swatch(spec: PaletteSpec, *, width: int = 4) -> str:
    """Render the palette's sequence as ANSI true-color background blocks.

    Used by /figure new step 5 to show palette options in the terminal.
    """
    blocks = []
    for hex_color in spec.sequence:
        r, g, b = _hex_to_rgb(hex_color)
        blocks.append(f"\x1b[48;2;{r};{g};{b}m{' ' * width}\x1b[0m")
    return "".join(blocks) + f"  {spec.name}"


def _hex_to_rgb(hex_color: str) -> tuple[int, int, int]:
    h = hex_color.lstrip("#")
    if len(h) != 6:
        raise ValueError(f"expected #RRGGBB, got {hex_color!r}")
    return int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16)
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_figures_palette.py -v`
Expected: 6 tests PASS.

- [ ] **Step 5: Commit**

```bash
git add src/research_assistant/figures/palette.py tests/test_figures_palette.py
git commit -m "feat(figures): palette loader + per-direction override + ANSI swatch"
```

---

## Task 7: Colorthief palette extraction for reference figures

**Files:**
- Modify: `src/research_assistant/figures/palette.py` (append `extract_palette_from_image`)
- Modify: `tests/test_figures_palette.py` (append extraction test)

- [ ] **Step 1: Add the failing test**

Append to `tests/test_figures_palette.py`:

```python
def test_extract_palette_creates_hex_strings(tmp_path: Path):
    # Build a tiny synthetic PNG to feed colorthief.
    from PIL import Image
    img_path = tmp_path / "fixture.png"
    Image.new("RGB", (60, 60), (255, 0, 0)).save(img_path)
    palette = fp.extract_palette_from_image(img_path, count=3)
    assert len(palette) == 3
    for hex_color in palette:
        assert hex_color.startswith("#")
        assert len(hex_color) == 7


def test_extract_palette_rejects_missing_file(tmp_path: Path):
    with pytest.raises(FileNotFoundError):
        fp.extract_palette_from_image(tmp_path / "no-such-file.png", count=3)
```

The fixture creation needs `Pillow` — `colorthief` depends on it transitively, so no new dep.

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_figures_palette.py::test_extract_palette_creates_hex_strings -v`
Expected: FAIL with `AttributeError: module ... has no attribute 'extract_palette_from_image'`.

- [ ] **Step 3: Append the implementation**

Append to `src/research_assistant/figures/palette.py`:

```python
def extract_palette_from_image(image_path: Path, *, count: int = 6) -> list[str]:
    """Use colorthief to pull dominant hex colors from a raster image.

    Falls back to FileNotFoundError if image_path doesn't exist. Returns up to
    `count` hex strings (#RRGGBB).
    """
    if not image_path.exists():
        raise FileNotFoundError(image_path)
    from colorthief import ColorThief
    ct = ColorThief(str(image_path))
    rgb_tuples = ct.get_palette(color_count=count, quality=10)
    return [f"#{r:02x}{g:02x}{b:02x}".upper() for r, g, b in rgb_tuples[:count]]
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_figures_palette.py -v`
Expected: 8 tests PASS (the 6 prior + 2 new).

- [ ] **Step 5: Commit**

```bash
git add src/research_assistant/figures/palette.py tests/test_figures_palette.py
git commit -m "feat(figures): colorthief palette extraction for reference images"
```

---

## Task 8: SVG → PDF + PNG export via cairosvg

**Files:**
- Create: `src/research_assistant/figures/export.py`
- Create: `tests/test_figures_export.py`

- [ ] **Step 1: Write the failing test**

Write `tests/test_figures_export.py`:

```python
"""SVG → PDF/PNG export tests."""
from pathlib import Path

import pytest

from research_assistant.figures import export as fe

_MINIMAL_SVG = """<?xml version="1.0" encoding="UTF-8"?>
<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 100 100" width="100" height="100">
  <rect x="10" y="10" width="80" height="80" fill="#0072B2"/>
  <text x="50" y="55" text-anchor="middle" fill="white" font-size="14">ok</text>
</svg>
"""


def test_export_creates_pdf_and_png(tmp_path: Path):
    svg = tmp_path / "fig.svg"
    svg.write_text(_MINIMAL_SVG, encoding="utf-8")
    pdf, png = fe.export(svg)
    assert pdf.exists() and pdf.stat().st_size > 0
    assert png.exists() and png.stat().st_size > 0
    assert pdf.suffix == ".pdf"
    assert png.suffix == ".png"


def test_export_is_idempotent(tmp_path: Path):
    svg = tmp_path / "fig.svg"
    svg.write_text(_MINIMAL_SVG, encoding="utf-8")
    fe.export(svg)
    first_pdf_size = (svg.with_suffix(".pdf")).stat().st_size
    fe.export(svg)
    second_pdf_size = (svg.with_suffix(".pdf")).stat().st_size
    # Re-running overwrites cleanly; sizes equal (deterministic input).
    assert first_pdf_size == second_pdf_size


def test_export_rejects_missing_svg(tmp_path: Path):
    with pytest.raises(FileNotFoundError):
        fe.export(tmp_path / "missing.svg")


def test_export_malformed_svg_raises(tmp_path: Path):
    svg = tmp_path / "bad.svg"
    svg.write_text("<not really svg", encoding="utf-8")
    with pytest.raises(fe.ExportError):
        fe.export(svg)
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_figures_export.py -v`
Expected: FAIL with `ModuleNotFoundError`.

- [ ] **Step 3: Write the implementation**

Write `src/research_assistant/figures/export.py`:

```python
"""SVG → PDF + PNG export pipeline (cairosvg). Idempotent."""
from __future__ import annotations

from pathlib import Path


class ExportError(RuntimeError):
    """Raised when cairosvg cannot render the SVG (malformed, unsupported feature)."""


def export(svg_path: Path, *, dpi: int = 300) -> tuple[Path, Path]:
    """Render <svg_path> to a sibling <stem>.pdf and <stem>.png. Returns the two paths.

    Idempotent — re-runs overwrite outputs. PNG is rendered at the given DPI;
    PDF is vector and DPI-independent.
    """
    import cairosvg

    if not svg_path.exists():
        raise FileNotFoundError(svg_path)

    pdf_path = svg_path.with_suffix(".pdf")
    png_path = svg_path.with_suffix(".png")

    try:
        cairosvg.svg2pdf(url=str(svg_path), write_to=str(pdf_path))
        cairosvg.svg2png(url=str(svg_path), write_to=str(png_path), dpi=dpi)
    except Exception as e:
        raise ExportError(f"cairosvg failed to render {svg_path}: {e}") from e

    return pdf_path, png_path
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_figures_export.py -v`
Expected: 4 tests PASS.

- [ ] **Step 5: Commit**

```bash
git add src/research_assistant/figures/export.py tests/test_figures_export.py
git commit -m "feat(figures): cairosvg-based SVG→PDF/PNG export pipeline"
```

---

## Task 9: matplotlib `save_all` helper

**Files:**
- Create: `src/research_assistant/figures/save.py`
- Create: `tests/test_figures_save.py`

- [ ] **Step 1: Write the failing test**

Write `tests/test_figures_save.py`:

```python
"""matplotlib save_all helper tests."""
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import pytest

from research_assistant.figures import save as fs


def test_save_all_writes_three_files(tmp_path: Path):
    fig, ax = plt.subplots(figsize=(4, 3))
    ax.plot([0, 1, 2], [0, 1, 4])
    paths = fs.save_all(fig, tmp_path, "demo")
    plt.close(fig)
    assert paths.svg.exists() and paths.svg.suffix == ".svg"
    assert paths.pdf.exists() and paths.pdf.suffix == ".pdf"
    assert paths.png.exists() and paths.png.suffix == ".png"
    for p in (paths.svg, paths.pdf, paths.png):
        assert p.stat().st_size > 0


def test_save_all_respects_dpi(tmp_path: Path):
    fig, ax = plt.subplots(figsize=(4, 3))
    ax.plot([0, 1, 2], [0, 1, 4])
    paths = fs.save_all(fig, tmp_path, "demo", dpi=72)
    plt.close(fig)
    small = paths.png.stat().st_size
    fig2, ax2 = plt.subplots(figsize=(4, 3))
    ax2.plot([0, 1, 2], [0, 1, 4])
    paths2 = fs.save_all(fig2, tmp_path, "demo-hi", dpi=300)
    plt.close(fig2)
    assert paths2.png.stat().st_size > small
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_figures_save.py -v`
Expected: FAIL with `ModuleNotFoundError`.

- [ ] **Step 3: Write the implementation**

Write `src/research_assistant/figures/save.py`:

```python
"""matplotlib `save_all` helper — drop-in to write svg + pdf + png in one call."""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class SavedFigure:
    svg: Path
    pdf: Path
    png: Path


def save_all(fig, out_dir: Path, slug: str, *, dpi: int = 300) -> SavedFigure:
    """Write `<out_dir>/<slug>.{svg,pdf,png}` from a matplotlib Figure.

    All three formats use `bbox_inches='tight'`. PNG uses the supplied dpi;
    SVG and PDF are vector.
    """
    out_dir.mkdir(parents=True, exist_ok=True)
    svg_path = out_dir / f"{slug}.svg"
    pdf_path = out_dir / f"{slug}.pdf"
    png_path = out_dir / f"{slug}.png"
    fig.savefig(svg_path, bbox_inches="tight")
    fig.savefig(pdf_path, bbox_inches="tight")
    fig.savefig(png_path, bbox_inches="tight", dpi=dpi)
    return SavedFigure(svg=svg_path, pdf=pdf_path, png=png_path)
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_figures_save.py -v`
Expected: 2 tests PASS.

- [ ] **Step 5: Commit**

```bash
git add src/research_assistant/figures/save.py tests/test_figures_save.py
git commit -m "feat(figures): matplotlib save_all helper — svg + pdf + png in one call"
```

---

## Task 10: Reference-figure intake (`/figure ref add` core logic)

**Files:**
- Create: `src/research_assistant/figures/refs.py`
- Create: `tests/test_figures_refs.py`

- [ ] **Step 1: Write the failing test**

Write `tests/test_figures_refs.py`:

```python
"""Reference-figure intake + AgentDB payload tests."""
import shutil
from pathlib import Path

import pytest
from PIL import Image

from research_assistant.figures import refs as fr
from research_assistant.figures.schema import FigureRef


@pytest.fixture
def fake_refs_dir(tmp_path: Path, monkeypatch):
    refs_dir = tmp_path / "figure-refs"
    refs_dir.mkdir()
    monkeypatch.setattr(fr, "FIGURE_REFS_DIR", refs_dir)
    return refs_dir


@pytest.fixture
def sample_image(tmp_path: Path):
    img_path = tmp_path / "ref.png"
    Image.new("RGB", (80, 80), (30, 120, 200)).save(img_path)
    return img_path


def test_add_ref_creates_dir_and_note(fake_refs_dir: Path, sample_image: Path):
    ref = FigureRef(
        slug="vaswani-arch",
        source="Vaswani et al. 2017 (NeurIPS), Fig 1",
        kind="structural",
        tags=["architecture", "encoder-decoder"],
        palette=["#1F77B4"],
        why_i_like_it="Symmetric layout.",
    )
    fr.add_ref(sample_image, ref)
    entry_dir = fake_refs_dir / "vaswani-arch"
    assert (entry_dir / "image.png").exists()
    assert (entry_dir / "note.md").exists()


def test_add_ref_rejects_duplicate_without_force(fake_refs_dir: Path, sample_image: Path):
    ref = FigureRef(slug="dup", source="s", kind="structural")
    fr.add_ref(sample_image, ref)
    with pytest.raises(FileExistsError):
        fr.add_ref(sample_image, ref)


def test_add_ref_force_overwrites(fake_refs_dir: Path, sample_image: Path):
    ref = FigureRef(slug="force-me", source="s", kind="structural")
    fr.add_ref(sample_image, ref)
    fr.add_ref(sample_image, ref, force=True)  # should not raise


def test_list_refs_excludes_staging(fake_refs_dir: Path, sample_image: Path):
    (fake_refs_dir / "staging").mkdir()
    ref = FigureRef(slug="real", source="s", kind="structural")
    fr.add_ref(sample_image, ref)
    slugs = fr.list_refs()
    assert "real" in slugs
    assert "staging" not in slugs


def test_to_agentdb_payload_includes_search_text():
    ref = FigureRef(
        slug="vaswani-arch",
        source="Vaswani et al. 2017",
        kind="structural",
        tags=["architecture", "callouts"],
        why_i_like_it="Symmetric layout.",
    )
    payload = fr.to_agentdb_payload(ref)
    assert payload["namespace"] == "project/figure-refs"
    assert payload["key"] == "vaswani-arch"
    text = payload["text"]
    assert "Vaswani" in text
    assert "structural" in text
    assert "architecture" in text
    assert "Symmetric layout" in text


def test_read_ref_round_trip(fake_refs_dir: Path, sample_image: Path):
    ref = FigureRef(
        slug="round-trip",
        source="Doe 2026",
        kind="data",
        tags=["dual-axis"],
        palette=["#000000", "#FFFFFF"],
        why_i_like_it="Clean baseline.",
    )
    fr.add_ref(sample_image, ref)
    loaded = fr.read_ref("round-trip")
    assert loaded == ref
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_figures_refs.py -v`
Expected: FAIL with `ModuleNotFoundError`.

- [ ] **Step 3: Write the implementation**

Write `src/research_assistant/figures/refs.py`:

```python
"""Reference-figure library — inputs/figure-refs/<slug>/ intake + AgentDB payload.

The Python helpers are filesystem-only. AgentDB upsert is performed by the
skill MD via `mcp__claude-flow__memory_store`, using the dict returned by
:func:`to_agentdb_payload`.
"""
from __future__ import annotations

import re
import shutil
from pathlib import Path

import yaml

from research_assistant.common.io import FIGURE_REFS_DIR
from research_assistant.figures.schema import FigureRef

_FM_RE = re.compile(r"^---\n(.*?)\n---\n?(.*)$", re.DOTALL)
_STAGING_NAME = "staging"


def add_ref(image_path: Path, ref: FigureRef, *, force: bool = False) -> Path:
    """Materialise inputs/figure-refs/<slug>/ from the image + parsed metadata.

    Returns the entry directory. Raises FileExistsError on conflict unless force=True.
    """
    if not image_path.exists():
        raise FileNotFoundError(image_path)
    entry_dir = FIGURE_REFS_DIR / ref.slug
    if entry_dir.exists():
        if not force:
            raise FileExistsError(entry_dir)
        shutil.rmtree(entry_dir)
    entry_dir.mkdir(parents=True)
    target_image = entry_dir / f"image{image_path.suffix.lower()}"
    shutil.copy2(image_path, target_image)
    _write_note(entry_dir / "note.md", ref)
    return entry_dir


def read_ref(slug: str) -> FigureRef:
    """Parse inputs/figure-refs/<slug>/note.md back into a FigureRef."""
    note_path = FIGURE_REFS_DIR / slug / "note.md"
    text = note_path.read_text(encoding="utf-8")
    m = _FM_RE.match(text)
    if not m:
        raise ValueError(f"{note_path} has no YAML frontmatter")
    fm = yaml.safe_load(m.group(1)) or {}
    return FigureRef.model_validate(fm)


def list_refs() -> list[str]:
    """Return all reference slugs (excluding the staging/ drop-zone)."""
    if not FIGURE_REFS_DIR.is_dir():
        return []
    return sorted(
        p.name
        for p in FIGURE_REFS_DIR.iterdir()
        if p.is_dir() and p.name != _STAGING_NAME
    )


def to_agentdb_payload(ref: FigureRef) -> dict:
    """Format a FigureRef for `mcp__claude-flow__memory_store`."""
    text = " | ".join([
        f"source: {ref.source}",
        f"kind: {ref.kind}",
        f"tags: {', '.join(ref.tags)}" if ref.tags else "tags: (none)",
        f"why_i_like_it: {ref.why_i_like_it}",
    ])
    return {
        "namespace": "project/figure-refs",
        "key": ref.slug,
        "text": text,
        "metadata": {
            "source": ref.source,
            "kind": ref.kind,
            "tags": ref.tags,
            "palette": ref.palette,
        },
    }


def _write_note(path: Path, ref: FigureRef) -> None:
    payload = ref.model_dump(mode="json")
    yaml_text = yaml.safe_dump(payload, sort_keys=False, allow_unicode=True).rstrip("\n")
    path.write_text(f"---\n{yaml_text}\n---\n", encoding="utf-8")
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_figures_refs.py -v`
Expected: 6 tests PASS.

- [ ] **Step 5: Commit**

```bash
git add src/research_assistant/figures/refs.py tests/test_figures_refs.py
git commit -m "feat(figures): reference-figure intake + AgentDB payload formatter"
```

---

## Task 11: Optional D2 scaffold helper with graceful fallback

**Files:**
- Create: `src/research_assistant/figures/d2.py`
- Create: `tests/test_figures_d2.py`

- [ ] **Step 1: Write the failing test**

Write `tests/test_figures_d2.py`:

```python
"""Optional D2 scaffold tests — graceful fallback if `d2` binary is missing."""
import shutil
from pathlib import Path

import pytest

from research_assistant.figures import d2 as fd2


def test_d2_available_returns_bool():
    out = fd2.d2_available()
    assert isinstance(out, bool)


def test_scaffold_returns_none_when_binary_missing(monkeypatch, tmp_path: Path):
    monkeypatch.setattr(fd2, "_which_d2", lambda: None)
    out = fd2.scaffold_to_svg(d2_source="boxA -> boxB", out_path=tmp_path / "x.svg")
    assert out is None  # caller falls back to raw SVG


def test_scaffold_invokes_d2_when_present(monkeypatch, tmp_path: Path):
    """Mock subprocess.run so we don't depend on `d2` actually being installed."""
    monkeypatch.setattr(fd2, "_which_d2", lambda: "/usr/local/bin/d2")
    called = {}
    def fake_run(cmd, **kw):
        called["cmd"] = cmd
        # Simulate d2 writing the output file.
        Path(cmd[-1]).write_text("<svg/>")
        class R:
            returncode = 0
            stderr = ""
        return R()
    monkeypatch.setattr(fd2.subprocess, "run", fake_run)
    out_path = tmp_path / "x.svg"
    result = fd2.scaffold_to_svg(d2_source="boxA -> boxB", out_path=out_path)
    assert result == out_path
    assert out_path.exists()
    assert called["cmd"][0] == "/usr/local/bin/d2"


def test_scaffold_returns_none_on_d2_failure(monkeypatch, tmp_path: Path):
    monkeypatch.setattr(fd2, "_which_d2", lambda: "/usr/local/bin/d2")
    def fake_run(cmd, **kw):
        class R:
            returncode = 1
            stderr = "syntax error"
        return R()
    monkeypatch.setattr(fd2.subprocess, "run", fake_run)
    out = fd2.scaffold_to_svg(d2_source="!!! bad !!!", out_path=tmp_path / "x.svg")
    assert out is None
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_figures_d2.py -v`
Expected: FAIL with `ModuleNotFoundError`.

- [ ] **Step 3: Write the implementation**

Write `src/research_assistant/figures/d2.py`:

```python
"""Optional D2 scaffold — writes .d2 source, shells `d2`, returns the produced SVG.

If the `d2` binary is missing or the render fails, returns None so the caller
can fall back to raw-SVG generation.
"""
from __future__ import annotations

import shutil
import subprocess
import tempfile
from pathlib import Path

_RENDER_TIMEOUT_S = 30


def d2_available() -> bool:
    return _which_d2() is not None


def _which_d2() -> str | None:
    return shutil.which("d2")


def scaffold_to_svg(
    d2_source: str, out_path: Path, *, theme_id: int = 200
) -> Path | None:
    """Render `d2_source` to `out_path` (SVG). Returns out_path or None on failure.

    The `.d2` source is deliberately NOT persisted — once the SVG is in place,
    it becomes the single source of truth (the user / Claude iterates on the
    SVG from here). Caller is responsible for setting `backend: d2-scaffolded`
    in the figure's note.md.
    """
    binary = _which_d2()
    if not binary:
        return None
    with tempfile.NamedTemporaryFile("w", suffix=".d2", delete=False) as tmp:
        tmp.write(d2_source)
        tmp_path = Path(tmp.name)
    try:
        result = subprocess.run(
            [binary, "-t", str(theme_id), str(tmp_path), str(out_path)],
            capture_output=True,
            text=True,
            timeout=_RENDER_TIMEOUT_S,
        )
        if result.returncode != 0:
            return None
        return out_path
    finally:
        try:
            tmp_path.unlink()
        except OSError:
            pass
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_figures_d2.py -v`
Expected: 4 tests PASS.

- [ ] **Step 5: Commit**

```bash
git add src/research_assistant/figures/d2.py tests/test_figures_d2.py
git commit -m "feat(figures): optional D2 scaffold with graceful fallback"
```

---

## Task 12: `experiments.versions` link-back — `append_figures_to_version`

**Files:**
- Modify: `src/research_assistant/experiments/__init__.py` (append a helper)
- Create: `tests/test_experiments_figures_link.py`

- [ ] **Step 1: Write the failing test**

Write `tests/test_experiments_figures_link.py`:

```python
"""Tests that /figure new --scope experiment appends to versions/<vN.M>.md."""
from pathlib import Path

import pytest

from research_assistant import experiments as exp


def test_append_figures_to_version_creates_field(tmp_path: Path, monkeypatch):
    fake_exp_dir = tmp_path / "experiments"
    monkeypatch.setattr(exp, "EXPERIMENTS_DIR", fake_exp_dir)
    versions = fake_exp_dir / "weightlet-motivation" / "versions"
    versions.mkdir(parents=True)
    (versions / "v1.2.md").write_text(
        "---\n"
        "version: v1.2\n"
        "description: baseline\n"
        "kind: minor\n"
        "---\n"
        "body text\n"
    )
    exp.append_figures_to_version(
        slug="weightlet-motivation",
        version="v1.2",
        figure_stems=["repo/figures/v1.2/perf", "repo/figures/v1.2/mem"],
    )
    text = (versions / "v1.2.md").read_text()
    assert "figures:" in text
    assert "repo/figures/v1.2/perf" in text
    assert "repo/figures/v1.2/mem" in text


def test_append_figures_dedupes(tmp_path: Path, monkeypatch):
    fake_exp_dir = tmp_path / "experiments"
    monkeypatch.setattr(exp, "EXPERIMENTS_DIR", fake_exp_dir)
    versions = fake_exp_dir / "w" / "versions"
    versions.mkdir(parents=True)
    (versions / "v1.0.md").write_text(
        "---\nversion: v1.0\nfigures:\n  - repo/figures/v1.0/perf\n---\nbody\n"
    )
    exp.append_figures_to_version(
        slug="w", version="v1.0", figure_stems=["repo/figures/v1.0/perf"]
    )
    text = (versions / "v1.0.md").read_text()
    # No duplicate
    assert text.count("repo/figures/v1.0/perf") == 1


def test_append_figures_missing_version_errors(tmp_path: Path, monkeypatch):
    fake_exp_dir = tmp_path / "experiments"
    monkeypatch.setattr(exp, "EXPERIMENTS_DIR", fake_exp_dir)
    (fake_exp_dir / "w" / "versions").mkdir(parents=True)
    with pytest.raises(FileNotFoundError):
        exp.append_figures_to_version(
            slug="w", version="v9.9", figure_stems=["x"]
        )
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_experiments_figures_link.py -v`
Expected: FAIL with `AttributeError: module 'research_assistant.experiments' has no attribute 'append_figures_to_version'`.

- [ ] **Step 3: Append the helper to `experiments/__init__.py`**

Locate the file, scroll to the bottom of the public API (just before any underscore-prefixed private helpers, after `current_commit_sha`). Append:

```python
def append_figures_to_version(
    *, slug: str, version: str, figure_stems: list[str]
) -> Path:
    """Append `figures:` list to versions/<version>.md frontmatter. Idempotent.

    figure_stems are repo-relative path stems WITHOUT extension (consumers
    append `.pdf` / `.svg` / `.png` as needed). Mirrors the spec's 8.2
    "experiment version add link-back".
    """
    import yaml
    version_path = EXPERIMENTS_DIR / slug / "versions" / f"{version}.md"
    if not version_path.exists():
        raise FileNotFoundError(version_path)
    text = version_path.read_text(encoding="utf-8")
    fm_match = re.match(r"^---\n(.*?)\n---\n?(.*)$", text, re.DOTALL)
    if not fm_match:
        raise ValueError(f"{version_path} has no YAML frontmatter")
    fm = yaml.safe_load(fm_match.group(1)) or {}
    body = fm_match.group(2)
    existing = fm.get("figures") or []
    merged = list(dict.fromkeys([*existing, *figure_stems]))   # dedupe, preserve order
    fm["figures"] = merged
    new_yaml = yaml.safe_dump(fm, sort_keys=False, allow_unicode=True).rstrip("\n")
    version_path.write_text(f"---\n{new_yaml}\n---\n{body}", encoding="utf-8")
    return version_path
```

The `re` module is already imported at the top of `experiments/__init__.py`. The `yaml` import is intentionally local to avoid widening the module's top-level import set.

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_experiments_figures_link.py tests/test_experiments.py -v`
Expected: 3 new tests PASS; existing experiments tests still PASS.

- [ ] **Step 5: Commit**

```bash
git add src/research_assistant/experiments/__init__.py tests/test_experiments_figures_link.py
git commit -m "feat(experiments): append_figures_to_version helper for /figure ↔ /experiment link-back"
```

---

## Task 13: Templates under `docs/`

**Files:**
- Create: `docs/figure-note-template.md`
- Create: `docs/figure-ref-template.md`
- Create: `docs/figure-palette-template.yml`

- [ ] **Step 1: Write `docs/figure-note-template.md`**

```markdown
---
slug: <kebab-case-slug>
kind: structural        # structural | data
scope: paper            # paper | experiment
anchor: papers/<venue>/<direction>            # or experiments/<exp-slug>/v1.2
intent: "<one sentence: what the reader should grasp in one second>"
size:
  width_in: 6.5
  height_in: 3.0
  preset: double-column-half                   # single-column | double-column-half | double-column-full | custom
palette: paper-trio                            # name from shipped or direction _palette.yml
refs: []                                       # list of figure-refs slugs used as style inspiration
backend: raw-svg                               # raw-svg | d2-scaffolded | matplotlib
created: 2026-05-13
---

<!-- Optional: free-form notes about hand-tweaks, palette deviations, or version history. -->
```

- [ ] **Step 2: Write `docs/figure-ref-template.md`**

```markdown
---
slug: <kebab-case-slug>
source: "<Authors et al. <Year> (<Venue>), Fig <N>>"
kind: structural        # structural | data | mixed
tags: []                # e.g. [architecture, callouts, dual-axis]
palette: []             # auto-extracted via colorthief; user-editable
why_i_like_it: |
  - <bullet 1>
  - <bullet 2>
---

<!-- Optional human notes below the frontmatter. -->
```

- [ ] **Step 3: Write `docs/figure-palette-template.yml`**

```yaml
# Drop-in template for a per-direction palette override.
# Place at: outputs/papers/<venue>/<direction>/figures/_palette.yml
name: <direction-name-or-arbitrary>
slots:
  primary: "#000000"
  accent: "#D55E00"
  baseline: "#909090"
sequence: ["#000000", "#D55E00", "#909090"]
colorblind_safe: true
suggested_for: []
```

- [ ] **Step 4: Verify file existence**

Run: `ls docs/figure-note-template.md docs/figure-ref-template.md docs/figure-palette-template.yml`
Expected: all three listed.

- [ ] **Step 5: Commit**

```bash
git add docs/figure-note-template.md docs/figure-ref-template.md docs/figure-palette-template.yml
git commit -m "docs(figures): note + ref + palette templates"
```

---

## Task 14: Skill prompt — `.claude/skills/figure-tool/SKILL.md`

**Files:**
- Create: `.claude/skills/figure-tool/SKILL.md`

- [ ] **Step 1: Write the skill**

Write `.claude/skills/figure-tool/SKILL.md`:

```markdown
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

Call `research_assistant.figures.paths.resolve_scope(paper_ctx, experiment_ctx, cli_scope)`:

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
```

- [ ] **Step 2: Verify file existence**

Run: `ls .claude/skills/figure-tool/SKILL.md && wc -l .claude/skills/figure-tool/SKILL.md`
Expected: file listed, around 150 lines.

- [ ] **Step 3: Commit**

```bash
git add .claude/skills/figure-tool/SKILL.md
git commit -m "feat(figures): figure-tool skill prompt — 6-step flow + ref intake + integration"
```

---

## Task 15: Slash command file — `.claude/commands/figure.md`

**Files:**
- Create: `.claude/commands/figure.md`

- [ ] **Step 1: Write the slash command**

Write `.claude/commands/figure.md`:

```markdown
---
name: figure
description: Generate / manage research figures — structural SVG (arch / pipeline / concept) or matplotlib data plots — plus curate a reference-figure library. Bound to the current /paper or /experiment cursor.
---

# /figure

Invoke the `figure-tool` skill in the mode matching `$ARGUMENTS`.

## Subcommands

- `/figure new <slug>` — interactive 6-step generation (intent → kind → refs → size → palette → render). Writes `<slug>.{svg,pdf,png}` plus `<slug>.note.md` to the resolved scope's figures dir.
- `/figure list` — table of all figures in current paper / experiment scope.
- `/figure render <slug>` — re-export PDF + PNG from the (possibly hand-edited) source SVG. For data figures, re-run `plot_<slug>.py`.
- `/figure render --all` — batch re-render every figure in the current scope.
- `/figure edit <slug>` — print the absolute path of `<slug>.svg` so you can open it in Inkscape. No automated changes.
- `/figure export <slug> --format jpeg --quality 90` — opt-in JPEG export.
- `/figure ref add [<file>|--url <u>]` — capture a reference figure: copies image into `inputs/figure-refs/<slug>/`, auto-suggests tags + colors + reasons (you confirm / edit), indexes in AgentDB.
- `/figure ref list [--kind k] [--tag t]` — filtered table of curated references.
- `/figure ref sync` — re-walk `inputs/figure-refs/*/note.md`, refresh AgentDB index.
- `/figure ref show <slug>` — print one reference's note + image path.
- `/figure` (bare) — same as `/figure list`.

## Action

1. Load the `figure-tool` skill (`.claude/skills/figure-tool/SKILL.md`).
2. Read both cursors in AgentDB (`project/paper-context.current`, `project/experiment-context.current`) and call `research_assistant.figures.paths.resolve_scope(...)` — error if neither cursor is set.
3. Parse `$ARGUMENTS` into `<subcommand> <args>`; dispatch the matching workflow stage.
4. Always end with the LaTeX include snippet (for `new` / `render`) or a status table (for `list` / `ref list`).
```

- [ ] **Step 2: Verify file existence**

Run: `ls .claude/commands/figure.md`
Expected: file listed.

- [ ] **Step 3: Commit**

```bash
git add .claude/commands/figure.md
git commit -m "feat(figures): /figure slash command surface"
```

---

## Task 16: Update `paper-architect` to enumerate figures + emit standard include

**Files:**
- Modify: `.claude/skills/paper-architect/SKILL.md` (extend the `write` stage)

- [ ] **Step 1: Read the existing `write` stage**

Run: `grep -n "^## " /data/lucky-research/.claude/skills/paper-architect/SKILL.md`
Note the line range that defines `### write` or the equivalent stage.

- [ ] **Step 2: Insert the figure-enumeration directive**

In the `write` stage section, find the bullet list that explains how Claude inserts content into `main.tex` / `sections/*.tex`. After that list, insert a new subsection:

```markdown
### Figure inclusion

When the section being drafted needs a figure:

1. List `figures/*.pdf` in the current direction.
2. If a slug matches the section's keyword (read the corresponding `<slug>.note.md`
   `intent:` field for the match), pick it; otherwise list the available slugs and
   ask the user.
3. Emit the include block **exactly** in this form (no `\graphicspath`, explicit
   path with `.pdf` extension):

```latex
\begin{figure}[t]
  \centering
  \includegraphics[width=<W>]{figures/<slug>.pdf}
  \caption{<from the figure's note.md `intent:` — user-editable>}
  \label{fig:<slug>}
\end{figure}
```

`<W>` is chosen from the figure's `size.preset`:

* `single-column` → `\columnwidth`
* `double-column-half` → `0.48\textwidth`
* `double-column-full` → `\textwidth`
* `custom` → `\columnwidth`

If no matching `figures/<slug>.pdf` exists, suggest the user runs `/figure new <slug>` first — do not synthesise a placeholder include.

For **experiment-scope** figures (referenced from a paper section discussing
that experiment), the include path uses `repo/figures/<vN.M>/<slug>.pdf` —
read the experiment's `versions/<vN.M>.md` `figures:` list (populated by
`/figure new --scope experiment`) to enumerate.
```

- [ ] **Step 3: Smoke check**

Run: `grep -c '\\includegraphics{figures/' /data/lucky-research/.claude/skills/paper-architect/SKILL.md`
Expected: at least 1.

- [ ] **Step 4: Commit**

```bash
git add .claude/skills/paper-architect/SKILL.md
git commit -m "feat(paper-architect): figure-inclusion directive — \\includegraphics{figures/<slug>.pdf}"
```

---

## Task 17: Wire `/figure` into the project's MVP table in `CLAUDE.md`

**Files:**
- Modify: `CLAUDE.md` (the MVP capabilities table)

- [ ] **Step 1: Update the MVP table**

Open `CLAUDE.md`. Find the markdown table that begins with `| Slash | Skill | Capability |`. Append a new row (preserving table alignment) right above the line that currently reads `Post-MVP (not yet scaffolded): 科研绘图.`:

```markdown
| `/figure`    | `figure-tool`            | 科研绘图 — structural SVG + matplotlib data plots + reference-figure library; scoped to current /paper or /experiment cursor. |
```

Then delete the entire line `Post-MVP (not yet scaffolded): 科研绘图.` (it no longer applies).

- [ ] **Step 2: Verify**

Run: `grep -n '/figure' /data/lucky-research/CLAUDE.md`
Expected: at least one row in the MVP table.

Run: `grep -c 'Post-MVP (not yet scaffolded)' /data/lucky-research/CLAUDE.md`
Expected: `0`.

- [ ] **Step 3: Commit**

```bash
git add CLAUDE.md
git commit -m "docs: promote 科研绘图 to MVP — /figure / figure-tool"
```

---

## Task 18: Full test sweep + lint

**Files:** none (validation step)

- [ ] **Step 1: Run the full pytest suite**

Run: `pytest -v`
Expected: all tests PASS, including any pre-existing tests (`test_smoke.py`, `test_papers.py`, `test_past_work.py`, `test_boss_profile.py`, `test_experiments.py`) plus the six new test files added in this plan.

- [ ] **Step 2: Run ruff over the new code**

Run: `ruff check src/research_assistant/figures tests/test_figures_*.py tests/test_experiments_figures_link.py`
Expected: 0 errors.

- [ ] **Step 3: Verify the slash + skill files are well-formed**

Run: `ls .claude/skills/figure-tool/SKILL.md .claude/commands/figure.md && head -5 .claude/skills/figure-tool/SKILL.md`
Expected: file paths listed; first 5 lines show valid YAML frontmatter.

- [ ] **Step 4: Manual smoke (no commit — just sanity check, OPTIONAL on CI)**

Pick the user's most-active workspace direction (read `outputs/papers/_index.md` if present). Open a Python REPL:

```python
from research_assistant.figures import palette as fpal
print(fpal.list_shipped_palettes())
spec = fpal.load_palette("paper-trio")
print(fpal.ansi_swatch(spec))
```

Expected: 4 palette names printed; ANSI swatch shows 3 colored blocks + `paper-trio`.

- [ ] **Step 5: Commit any incidental fixes**

If ruff or pytest surfaced minor fixes, commit them separately:

```bash
git add -p
git commit -m "fix(figures): post-implementation cleanup from test sweep"
```

If everything passes cleanly, skip this commit.

---

## Out of Scope (deferred per spec §15)

- LaTeX `subfigure` composition wizard step (current raw SVG supports it; not a wizard step).
- Venue-specific palettes beyond the 4 shipped.
- Pre-commit hook for automatic `/figure render --all`.
- Camera-ready packaging (`/paper render --camera-ready`) — owned by `paper-architect`; this plan only guarantees grep-compatible include paths.
