---
name: pseudocode-tool
description: Generate publication-grade LaTeX algorithm pseudocode (algorithm + algpseudocode, or algorithm2e) for the current /paper or /experiment scope. Each algorithm goes through a 5-step interactive flow (intent → kind → I/O → draft → lint+render) and lands in <scope>/algorithms/<slug>.{tex,note.md,pdf}. Triggered by /pseudocode. Notation and venue conventions imported from https://github.com/HuiyuLi-2000/gen-pseudocode-skill (MIT).
---

# pseudocode-tool

A sibling of `figure-tool`. Both are scope-aware asset writers; `paper-architect`
pulls their products into `sections/*.tex` at write time. Read `figure-tool/SKILL.md`
if you want the structural analog — this skill mirrors it line-for-line.

## Mental model

```
                     /pseudocode new <slug>
                              │
              ┌───────────────┴───────────────┐
        scope=paper                    scope=experiment
              │                                │
   outputs/papers/<v>/<d>/        outputs/experiments/<exp>/repo/
   algorithms/                    algorithms/<vN.M>/
     <slug>.tex                     <slug>.tex
     <slug>.note.md                 <slug>.note.md
     <slug>.pdf                     <slug>.pdf  (standalone preview)
```

Two LaTeX packages are supported; the choice is **venue-driven**:

- **`algpseudocode`** (default) — pairs with `algorithm` for the float. Used by
  ICML / NeurIPS / ICLR / CVPR templates. Syntax: `\Require`, `\Ensure`,
  `\State`, `\For ... \EndFor`, `\Comment{}`.
- **`algorithm2e`** — opt-in via `pseudocode-package: algorithm2e` in the
  venue's `_venue.md` frontmatter. Syntax: `\KwIn{}`, `\KwOut{}`, `\For{}{}`,
  `\tcp{}`. Common in TPAMI / TKDE / TNNLS.

The skill picks one at write time from `outputs/papers/<v>/_venue.md` via
`research_assistant.pseudocode.preamble.read_venue_package(_venue_md_path)`.

## Cursor reads (always do this first)

At every `/pseudocode ...` invocation, read both cursors:

* `mcp__claude-flow__memory_retrieve` namespace=`project`, key=`paper-context.current`
  → expect `{"venue": "...", "direction": "..."}` or absent
* `mcp__claude-flow__memory_retrieve` namespace=`project`, key=`experiment-context.current`
  → expect `{"slug": "..."}` or absent

Then call
`research_assistant.pseudocode.paths.resolve_scope(paper_ctx=..., experiment_ctx=..., cli_scope=...)`
(all three keyword-only):

* `NoScopeError` → tell the user: `先 /paper venue 或 /experiment init`
* `AmbiguousScopeError` → ask plain text: "paper or experiment?" (step 0)

## Subcommand router

| Subcommand | Action |
|---|---|
| `new <slug>` | The 5-step flow (below). |
| `list` (default) | Walk current scope's `algorithms/*.note.md`; render a table: slug · kind · package · time · space · created. |
| `render <slug>` | Recompile `algorithms/<slug>.tex` to standalone `<slug>.pdf` via `pseudocode.compile.compile_snippet(snippet_path, package=<from note.md>)`. |
| `render --all` | Walk current scope's `algorithms/*.tex`; render each; summary table at end. |
| `check <slug>` | Read the snippet, call `pseudocode.lint.scan(text)`, print `lint.format_findings(findings, source=<path>)`. |
| `check --all` | Lint every algorithm in current scope; non-zero count fails the call. |
| `notation [--grep <q>]` | Print `references/notation.md` (full, or filtered by case-insensitive substring). |

## `/pseudocode new <slug>` — 5-step interactive flow

**Step 0 — scope** (only if `AmbiguousScopeError`)
Plain text (per memory rule on multi-option research picks): "Paper or experiment?"
— accept `paper` / `experiment`. Persist only to this invocation.

**Step 1 — intent**
Ask: "这个算法要让评审一秒看懂什么 novelty？" — one sentence. Stored as
`note.md`'s `intent:`. Use the answer to also pre-fill the `\caption{}`.

**Step 2 — kind**
Ask: "`unified` (single pipeline) / `train` (training procedure) / `inference`
(serving / decoding) / `preprocess` (data construction)?"

For experiment scope, also ask which version (defaults to the latest if scope=experiment).

**Step 3 — inputs / outputs / notation**

1. Read `outputs/papers/<v>/_venue.md` (if paper scope) via
   `pseudocode.preamble.read_venue_package(...)` to pin the package family. Tell
   the user which package will be used (`algpseudocode` or `algorithm2e`).
2. Ask for inputs — accept a comma-separated list. For each item, run a
   keyword-match against `references/notation.md`:
     - `"graph adjacency"` → suggest `\mathbf{A}`
     - `"learning rate"` → suggest `\eta`
     - `"dataset"` → suggest `\mathcal{D}`
   Surface the top 3 suggestions inline.
3. Ask for outputs — same flow.
4. Record `notation_used: [...]` (the row keys you suggested + the user accepted).

**Step 4 — draft + lint**

1. Generate `algorithms/<slug>.tex` containing ONLY the algorithm environment
   (no `\documentclass`, no `\begin{document}`). Use the venue's package family:

   For `algpseudocode`:
   ```latex
   \begin{algorithm}
   \caption{<intent>}
   \label{alg:<slug>}
   \begin{algorithmic}[1]
   \Require <inputs joined with `, `>
   \Ensure  <outputs joined with `, `>
   \State ...
   \For{...}
     \State ...
   \EndFor
   \State \Return ...
   \end{algorithmic}
   \end{algorithm}
   ```

   For `algorithm2e`:
   ```latex
   \begin{algorithm}
   \caption{<intent>}
   \label{alg:<slug>}
   \KwIn{<inputs>}
   \KwOut{<outputs>}
   \For{<cond>}{
     ...\;
   }
   \Return{<expr>}\;
   \end{algorithm}
   ```

2. Apply the **method-level abstraction** rule (this is the single most
   important value-add of this skill, imported from gen-pseudocode-skill):
   - NEVER write `optimizer.step()`, `.backward()`, `.to(device)`,
     `zero_grad`, `model.train()`, `model.eval()`, `loss.backward()`.
   - NEVER write `for batch in DataLoader` — write `sample mini-batch
     $(\mathbf{X}, \mathbf{y}) \sim \mathcal{D}$`.
   - NEVER write tensor-library calls (`torch.*`, `tf.*`, `np.*`, `F.*`).
   - NEVER include `import` lines or Python primitives like `range(len(...))`,
     `enumerate(...)`.
   - Use the mappings in `references/notation.md`.
   - Comments: `\tcp{...}` / `\tcc{...}` (algorithm2e) or `\Comment{...}` (algpseudocode).
3. Run `pseudocode.lint.scan_file(snippet_path)` and print
   `lint.format_findings(findings, source=snippet_path)`. **If any smells, fix
   in-place and re-scan before showing the user.**

**Step 5 — render + note**

1. Ask (optional): time complexity? space complexity? (LaTeX-math strings; may be left blank.)
2. Build a `PseudocodeNote` and call `pseudocode.note.write_note(note_path, note, body=<short rationale>)`.
3. Call `pseudocode.compile.compile_snippet(snippet_path, package=<picked>)`.
   - Success → tell the user the PDF path.
   - Failure → print the last ~40 lines of `log_tail`; leave `.tex` + `.note.md`
     in place; suggest `/pseudocode render <slug>` to retry after they install
     `tectonic` or `pdflatex`.
4. Ensure the destination paper's `main.tex` carries the package by calling
   `pseudocode.preamble.ensure_preamble(main_tex_path, venue_md_path=<...>)`.
   If `main.tex` does not yet exist (no `/paper write` done), skip silently —
   paper-architect's scaffold step will call `ensure_preamble` on first write.
5. Print the `\input{}` snippet (see "Insert snippet" below).

## Insert snippet

After every successful `/pseudocode new` and `/pseudocode render`, print exactly:

```
✓ Algorithm: <abs-path>.tex
✓ Note:      <abs-path>.note.md
✓ Preview:   <abs-path>.pdf       (engine: <tectonic|xelatex|pdflatex>)
✓ LaTeX include (paste into your section .tex):

    \input{algorithms/<slug>.tex}

  Or, if you prefer inline:

    See Algorithm~\ref{alg:<slug>}.
```

For **experiment scope**, the include path is `algorithms/<vN.M>/<slug>.tex`.

## Error policy

| Failure | Behaviour |
|---|---|
| `NoScopeError` | Refuse with: `先 /paper venue 或 /experiment init` |
| `AmbiguousScopeError` | Ask step-0 "paper or experiment?" |
| Slug exists in target dir | Refuse; suggest `--force` (manual file removal) |
| Path traversal | Reject at boundary (`paths.safe_join` raises) |
| Lint smells after draft | Fix in-place and re-scan; do NOT show smelly output to user |
| Compile fails (no engine on PATH) | Print install hint (`brew install tectonic` / `apt install texlive-latex-extra`); keep `.tex` + `.note.md` |
| Compile fails (LaTeX error) | Print last 40 lines of `log_tail`; keep `.tex`; tell user to fix |

## Method-level abstraction — the anti-pattern rule

**The single most important rule of this skill** (imported verbatim from
gen-pseudocode-skill's `style_guide.md` § "Anti-Patterns"):

### Bad: Code Translation

```latex
\ForEach{batch in DataLoader}{
    optimizer.zeroGrad()\;
    logits $\leftarrow$ model(batch)\;
    loss $\leftarrow$ criterion(logits, labels)\;
    loss.backward()\;
    optimizer.step()\;
}
```

### Good: Method-Level Abstraction

```latex
\ForEach{mini-batch $(\mathbf{X}, \mathbf{y}) \sim \mathcal{D}$}{
    $\hat{\mathbf{y}} \leftarrow f_{\theta}(\mathbf{X})$\;
    $\mathcal{L} \leftarrow \mathcal{L}(\hat{\mathbf{y}}, \mathbf{y}) + \lambda \|\theta\|_2^2$\;
    $\theta \leftarrow \theta - \eta \nabla_{\theta} \mathcal{L}$\;
}
```

The good version:
- Uses math notation for forward pass (`f_\theta`), loss (`\mathcal{L}`), and
  parameter update (`\theta \leftarrow \theta - \eta \nabla_\theta \mathcal{L}`).
- Drops framework bookkeeping (`zero_grad`, `.backward`, `.step`).
- Names the novelty (the regularizer `\lambda \|\theta\|_2^2` in this example).

`pseudocode.lint.scan()` flags every framework-call / tensor-library / Python
primitive automatically.

## Venue conventions (from `references/style_guide.md`)

- **NeurIPS / ICML / ICLR** — compact single-algorithm; concise caption; `\KwIn`
  / `\KwOut` always present.
- **AAAI / KDD / WWW** — procedural detail OK; preprocessing can be its own
  algorithm; complexity discussion in text, not pseudocode.
- **TPAMI / TKDE / TNNLS** — formal math notation, detailed line-by-line,
  multi-algorithm (training + inference) common, often `algorithm2e`.
- **JAMIA / NPJ Digital Medicine** — domain terminology; preprocessing as
  separate step when relevant.

The skill DOES NOT hard-code venue → conventions mapping. Read `_venue.md` for
the venue's own notes; use this list as background guidance only.

## When NOT to use this skill

- Code execution / verification — pseudocode is documentation, not runtime.
  Real implementations live in the experiment repo.
- General mathematical derivations — those belong in the section prose
  (`sections/method.tex`), not in an algorithm box.
- LaTeX-only typesetting fixes (e.g., spacing tweaks) — open the `.tex` directly.

## Resources

- `references/notation.md` — Symbol mapping table (programming → LaTeX-math).
  Extended from gen-pseudocode-skill with GNN / attention / probabilistic-model rows.
- `references/style_guide.md` — Per-venue style expectations, anti-pattern callouts,
  and multi-algorithm structure guidance. Trimmed from gen-pseudocode-skill.
- `examples/example_diffusion_train.tex` — Golden reference algorithm. Hand-written
  in `algpseudocode`; lints clean. Use it as a stylistic anchor when drafting.
