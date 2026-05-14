# Notation Mapping

Programming → scientific LaTeX-math mapping for `/pseudocode`. Use these when
drafting `algorithms/<slug>.tex` so the algorithm reads like a method, not a
codebase. Imported (with extensions for GNN / attention / probabilistic models)
from https://github.com/HuiyuLi-2000/gen-pseudocode-skill `references/notation.md`
(MIT license).

## Core

| Programming | LaTeX | Context |
|-------------|-------|---------|
| `sigmoid(x)` | `\sigma(x)` | Activation |
| `softmax(x)` | `\mathrm{softmax}(x)` | Activation |
| `relu(x)` | `\mathrm{ReLU}(x)` | Activation |
| `gelu(x)` | `\mathrm{GELU}(x)` | Activation |
| `silu(x)` / `swish(x)` | `\mathrm{SiLU}(x)` | Activation |
| `prediction` | `\hat{y}` | Output |
| `label` | `y` | Ground truth |
| `loss` | `\mathcal{L}` | Objective |
| `loss_fn(pred, label)` | `\mathcal{L}(\hat{y}, y)` | Loss evaluation |
| `optimizer.step()` | `\theta \leftarrow \theta - \eta \nabla_\theta \mathcal{L}` | Update step |
| `learning_rate` | `\eta` | Hyperparameter |
| `epoch` | `t` (or `T` for total) | Iteration |
| `step` | `s` (or `S` for total) | Inner iteration |
| `batch_size` | `B` | Batch |
| `hidden_dim` | `d` | Dimensionality |
| `num_layers` | `L` | Architecture |
| `embedding(x)` | `\mathbf{e}_x` or `f_{\mathrm{emb}}(x)` | Embedding |
| `weights` | `\mathbf{W}` | Parameter matrix |
| `bias` | `\mathbf{b}` | Parameter vector |
| `features` | `\mathbf{X}` | Feature matrix |
| `mask` | `\mathbf{M}` | Mask matrix |
| `logits` | `\mathbf{z}` | Pre-activation |
| `gradient` | `\nabla_\theta` | Gradient |
| `params` | `\theta` | Parameter set |
| `model(x)` | `f_\theta(\mathbf{x})` | Forward pass |
| `train_set` | `\mathcal{D}_{\mathrm{train}}` | Dataset |
| `test_set` | `\mathcal{D}_{\mathrm{test}}` | Dataset |
| `val_set` | `\mathcal{D}_{\mathrm{val}}` | Dataset |
| `data_loader` | `\mathcal{D}` | Dataset reference |
| `sample` | `\mathbf{x}_i` | Data point |
| `index` | `i` | Index |
| `num_classes` | `C` | Classification |
| `temperature` | `\tau` | Temperature |
| `alpha`, `beta` | `\alpha`, `\beta` | Coefficients |
| `lambda` | `\lambda` | Regularization weight |
| `epsilon` | `\epsilon` | Small constant |
| `delta` | `\delta` | Perturbation |

## Graphs & GNNs (extension)

| Programming | LaTeX | Context |
|-------------|-------|---------|
| `adjacency` | `\mathbf{A}` | Graph structure |
| `degree_matrix` | `\mathbf{D}` | Degree |
| `laplacian` | `\mathbf{L} = \mathbf{D} - \mathbf{A}` | Laplacian |
| `normalized_laplacian` | `\tilde{\mathbf{L}} = \mathbf{I} - \mathbf{D}^{-1/2} \mathbf{A} \mathbf{D}^{-1/2}` | Symmetric normalization |
| `node_features` | `\mathbf{H}^{(\ell)}` | Layer-`\ell` node features |
| `edge_set` | `\mathcal{E}` | Edges |
| `node_set` | `\mathcal{V}` | Nodes |
| `neighbors(v)` | `\mathcal{N}(v)` | Neighborhood |
| `message(u, v)` | `\mathbf{m}_{u \to v}` | Message |
| `aggregate({m_uv : u in N(v)})` | `\bigoplus_{u \in \mathcal{N}(v)} \mathbf{m}_{u \to v}` | Aggregation |
| `update(h_v, m_v)` | `\mathbf{h}_v \leftarrow \phi(\mathbf{h}_v, \mathbf{m}_v)` | Update |

## Attention (extension)

| Programming | LaTeX | Context |
|-------------|-------|---------|
| `query` | `\mathbf{Q}` | Query matrix |
| `key` | `\mathbf{K}` | Key matrix |
| `value` | `\mathbf{V}` | Value matrix |
| `attention_scores` | `\mathbf{S} = \mathbf{Q} \mathbf{K}^\top / \sqrt{d_k}` | Scaled dot-product |
| `attention_weights` | `\mathbf{A} = \mathrm{softmax}(\mathbf{S})` | Softmax weights |
| `attention_output` | `\mathbf{O} = \mathbf{A} \mathbf{V}` | Output |
| `num_heads` | `H` | Multi-head count |
| `head_dim` | `d_k = d / H` | Per-head dim |

## Probabilistic Models (extension)

| Programming | LaTeX | Context |
|-------------|-------|---------|
| `prior` | `p(\mathbf{z})` | Prior |
| `posterior` | `q(\mathbf{z} \mid \mathbf{x})` | Variational posterior |
| `likelihood` | `p(\mathbf{x} \mid \mathbf{z})` | Likelihood |
| `kl_divergence` | `\mathrm{KL}\!\left(q \;\|\; p\right)` | KL |
| `elbo` | `\mathcal{L}_{\mathrm{ELBO}} = \mathbb{E}_q[\log p(\mathbf{x}, \mathbf{z}) - \log q(\mathbf{z}\mid\mathbf{x})]` | ELBO |
| `sample_from(q)` | `\mathbf{z} \sim q(\mathbf{z} \mid \mathbf{x})` | Sampling |
| `noise_schedule[t]` | `\beta_t` (or `\alpha_t`) | Diffusion schedule |
| `noisy(x, t)` | `\mathbf{x}_t \sim q(\mathbf{x}_t \mid \mathbf{x}_0)` | Forward diffusion |
| `denoise(x_t, t)` | `\hat{\mathbf{x}}_0 = f_\theta(\mathbf{x}_t, t)` | Reverse step |

## Notation Conventions

### Sets and Spaces
- Sets: calligraphic `\mathcal{S}`
- Probability: `p(\cdot)`, `\mathbb{E}[\cdot]`
- Spaces: `\mathbb{R}^d`

### Vectors and Matrices
- Vectors: bold lowercase `\mathbf{x}`
- Matrices: bold uppercase `\mathbf{W}`
- Scalars: italic `x`, `n`, `d`
- Tensors of order > 2: bold sans-serif if ambiguous; otherwise just `\mathbf{X}`.

### Operations
- Argmin / argmax: `\arg\min_x`, `\arg\max_x`
- Norm: `\|\mathbf{x}\|`, `\|\mathbf{x}\|_2`
- Inner product: `\langle \mathbf{a}, \mathbf{b} \rangle`
- Element-wise: `\odot` (Hadamard), `\otimes` (Kronecker)
- Concatenation: `[\mathbf{a}; \mathbf{b}]` or `\mathbf{a} \mathbin\| \mathbf{b}`
- Assignment: `\leftarrow`
- Definition: `\triangleq` or `\coloneqq`

### Distributions
- Gaussian: `\mathcal{N}(\mu, \sigma^2)`
- Uniform: `\mathcal{U}(a, b)`
- Categorical: `\mathrm{Cat}(\boldsymbol{\pi})`

### Common Phrases
- "for each" → `\forall`
- "exists" → `\exists`
- "such that" → `\text{s.t.}`
- "i.i.d." → `\mathrm{i.i.d.}`
- "w.r.t." → `\mathrm{w.r.t.}`
