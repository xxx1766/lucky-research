# Pseudocode Style Guide

Imported (and trimmed) from
https://github.com/HuiyuLi-2000/gen-pseudocode-skill `references/style_guide.md`
(MIT license). The hardcoded `algorithm2e` examples below are kept because they
match `algorithm2e` syntax precisely; the `algpseudocode` analog is provided
inline.

## Package choice (venue-driven)

| Family | Preamble lines | Body syntax | Default for |
|---|---|---|---|
| `algpseudocode` (with `algorithm` for the float) | `\usepackage{algorithm}`<br>`\usepackage{algpseudocode}` | `\Require`, `\Ensure`, `\State`, `\For ... \EndFor`, `\Comment{...}` | ICML, NeurIPS, ICLR, CVPR, ECCV, ACL/EMNLP/NAACL (default) |
| `algorithm2e` | `\usepackage[ruled,vlined,linesnumbered]{algorithm2e}` | `\KwIn`, `\KwOut`, `\For{}{}`, `\tcp{...}` | TPAMI, TKDE, TNNLS (when opted in via `_venue.md`) |

Opt into `algorithm2e` per-venue by adding to `outputs/papers/<venue>/_venue.md`:

```yaml
---
pseudocode-package: algorithm2e
---
```

`pseudocode.preamble.read_venue_package(...)` reads this; the default is
`algpseudocode`.

## Minimal compilable templates

### algpseudocode

```latex
\documentclass{article}
\usepackage{amsmath,amssymb}
\usepackage{algorithm}
\usepackage{algpseudocode}
\begin{document}

\begin{algorithm}[H]
\caption{Algorithm Title}\label{alg:slug}
\begin{algorithmic}[1]
\Require Input description
\Ensure  Output description
\For{$x \in \mathcal{X}$}
  \State $y \leftarrow f(x)$
\EndFor
\State \Return $y$
\end{algorithmic}
\end{algorithm}

\end{document}
```

### algorithm2e

```latex
\documentclass{article}
\usepackage[ruled,vlined,linesnumbered]{algorithm2e}
\usepackage{amsmath,amssymb}
\begin{document}

\begin{algorithm}[H]
\caption{Algorithm Title}\label{alg:slug}
\KwIn{Input description}
\KwOut{Output description}
\ForEach{$x \in \mathcal{X}$}{
    $y \leftarrow f(x)$\;
}
\Return{$y$}
\end{algorithm}

\end{document}
```

## Key commands

### algpseudocode

| Command | Purpose |
|---------|---------|
| `\Require ...` | Input |
| `\Ensure ...` | Output |
| `\State ...` | One statement |
| `\For{cond} ... \EndFor` | For loop |
| `\ForAll{cond} ... \EndFor` | For-each loop |
| `\While{cond} ... \EndWhile` | While loop |
| `\If{cond} ... \EndIf` | If |
| `\If{cond} ... \Else ... \EndIf` | If-else |
| `\Repeat ... \Until{cond}` | Repeat-until |
| `\Return ...` | Return |
| `\Comment{...}` | Inline comment |
| `\Procedure{name}{args} ... \EndProcedure` | Named procedure |
| `\Call{name}{args}` | Procedure call |

### algorithm2e

| Command | Purpose |
|---------|---------|
| `\KwIn{...}` | Input |
| `\KwOut{...}` | Output |
| `\ForEach{cond}{body}` | For-each loop |
| `\For{cond}{body}` | For loop |
| `\While{cond}{body}` | While loop |
| `\If{cond}{body}` | If |
| `\eIf{cond}{then}{else}` | If-else |
| `\Repeat{cond}{body}` | Repeat-until |
| `\Return{...}` | Return |
| `\tcp{...}` | Inline comment |
| `\tcc{...}` | Block comment |
| `\lForEach{cond}{stmt}` | Line-level for-each |
| `\lFor{cond}{stmt}` | Line-level for |
| `\lIf{cond}{stmt}` | Line-level if |

## Venue-specific notes

### NeurIPS / ICML / ICLR / CVPR
- Compact single-algorithm presentation for the core method.
- Multi-algorithm acceptable for multi-stage methods (preprocess → train → infer).
- Caption: concise, descriptive.
- Input/Output: always present.
- Default: `algorithm + algpseudocode`.

### AAAI / KDD / WWW
- More procedural detail acceptable.
- Data preprocessing can be a separate algorithm.
- Complexity discussion in surrounding text, not in pseudocode.

### TPAMI / TKDE / TNNLS
- Formal mathematical notation.
- Line-by-line justification.
- Convergence properties in surrounding text.
- Multi-algorithm (training + inference) common.
- Often `algorithm2e`.

### JAMIA / NPJ Digital Medicine
- Domain-specific clinical terminology.
- Algorithm names should reflect clinical workflow.
- Include data preprocessing as separate step when relevant.

## Anti-Patterns

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

The `pseudocode.lint` module flags every `optimizer.*`, `.backward()`,
`.to(device)`, `DataLoader`, and `torch.*` token automatically.

### Good: Method-Level Abstraction

```latex
\ForEach{mini-batch $(\mathbf{X}, \mathbf{y}) \sim \mathcal{D}$}{
    $\hat{\mathbf{y}} \leftarrow f_\theta(\mathbf{X})$\;
    $\mathcal{L} \leftarrow \mathcal{L}(\hat{\mathbf{y}}, \mathbf{y}) + \lambda \|\theta\|_2^2$\;
    $\theta \leftarrow \theta - \eta \nabla_\theta \mathcal{L}$\;
}
```

## Multi-Algorithm Structure

When a paper naturally decomposes into stages:

```
Algorithm 1: Data Preprocessing and Graph Construction
Algorithm 2: Model Training with [Method Name]
Algorithm 3: Inference and Prediction
```

Each lands in its own `.tex` file under `algorithms/`. The writing section
`\input{}`s them in order.

When the user requests "full algorithm" → one unified pipeline (`kind: unified`).
When the user requests a specific component → generate only that component
(`kind: train` / `inference` / `preprocess`).

## Line ending rules (algorithm2e)

- Every statement ends with `\;`.
- Control flow headers (`\For`, `\While`, `\If`) do NOT end with `\;`.
- `\Return{...}` ends with `\;`.
- Line-level commands (`\lFor`, `\lIf`, `\lForEach`) do NOT need `\;`.

For `algpseudocode`, no `\;` terminator is needed — each `\State` is its own line.
