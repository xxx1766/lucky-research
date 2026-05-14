"""Anti-pattern detector tests for the pseudocode linter."""
from research_assistant.pseudocode import lint


GOOD_ALGPSEUDOCODE = r"""
\begin{algorithm}
\caption{Sparse attention update}
\label{alg:sparse-attn}
\begin{algorithmic}[1]
\Require $\mathbf{X} \in \mathbb{R}^{B \times L \times d}$, parameters $\theta$
\Ensure updated parameters $\theta$
\For{$t = 1, \dots, T$}
  \State sample mini-batch $(\mathbf{X}, \mathbf{y}) \sim \mathcal{D}$
  \State $\hat{\mathbf{y}} \leftarrow f_\theta(\mathbf{X})$
  \State $\mathcal{L} \leftarrow \mathcal{L}(\hat{\mathbf{y}}, \mathbf{y})$
  \State $\theta \leftarrow \theta - \eta \nabla_\theta \mathcal{L}$
\EndFor
\State \Return $\theta$
\end{algorithmic}
\end{algorithm}
"""

GOOD_ALGORITHM2E = r"""
\begin{algorithm}
\caption{Sparse attention update}
\KwIn{$\mathbf{X}$, parameters $\theta$}
\KwOut{updated parameters $\theta$}
\For{$t = 1, \dots, T$}{
  $\hat{\mathbf{y}} \leftarrow f_\theta(\mathbf{X})$\;
  $\theta \leftarrow \theta - \eta \nabla_\theta \mathcal{L}$\;
}
\Return{$\theta$}\;
\end{algorithm}
"""

BAD_CODE_TRANSLATION = r"""
\begin{algorithm}
\caption{Training loop}
\begin{algorithmic}[1]
\For{batch in DataLoader}
  \State optimizer.zero_grad()
  \State logits = model(batch.to(device))
  \State loss = criterion(logits, batch.y)
  \State loss.backward()
  \State optimizer.step()
\EndFor
\end{algorithmic}
\end{algorithm}
"""


def test_clean_algpseudocode_has_no_smells():
    findings = lint.scan(GOOD_ALGPSEUDOCODE)
    assert findings == [], f"unexpected findings: {findings}"


def test_clean_algorithm2e_has_no_smells():
    findings = lint.scan(GOOD_ALGORITHM2E)
    assert findings == [], f"unexpected findings: {findings}"


def test_detects_framework_calls():
    findings = lint.scan(BAD_CODE_TRANSLATION)
    smells = {f.smell for f in findings}
    assert lint.SMELL_FRAMEWORK_CALL in smells
    assert lint.SMELL_TENSOR_LIB in smells  # DataLoader


def test_detects_optimizer_step_and_zero_grad():
    findings = lint.scan(BAD_CODE_TRANSLATION)
    snippets = " ".join(f.snippet for f in findings)
    assert "zero_grad" in snippets
    assert "optimizer.step" in snippets


def test_detects_backward_call():
    findings = lint.scan(BAD_CODE_TRANSLATION)
    assert any(".backward" in f.snippet for f in findings)


def test_detects_cuda_to_device():
    # Realistic case: user copy-pastes raw Python into the snippet.
    bad = r"\State $x = x.to(device='cuda')$"
    findings = lint.scan(bad)
    assert any(f.smell == lint.SMELL_FRAMEWORK_CALL for f in findings)


def test_detects_python_import():
    bad = "import torch\n\\State foo"
    findings = lint.scan(bad)
    assert any(f.smell == lint.SMELL_PYTHON_PRIMITIVE for f in findings)


def test_detects_range_len():
    bad = r"\For{$i \in \text{range(len(x))}$}"
    findings = lint.scan(bad)
    assert any("range(len" in f.snippet for f in findings)


def test_missing_input_decl_flagged():
    bad = r"""
\begin{algorithm}
\caption{x}
\Ensure y
\State $\theta \leftarrow \theta$
\Return $\theta$
\end{algorithm}
"""
    findings = lint.scan(bad)
    assert any(f.smell == lint.SMELL_MISSING_KWIN for f in findings)


def test_missing_output_decl_flagged():
    bad = r"""
\begin{algorithm}
\caption{x}
\Require y
\State foo
\end{algorithm}
"""
    findings = lint.scan(bad)
    assert any(f.smell == lint.SMELL_MISSING_KWOUT for f in findings)


def test_kwin_satisfies_input_check():
    text = r"\KwIn{$\mathbf{X}$}" + "\n" + r"\KwOut{$\theta$}"
    findings = [f for f in lint.scan(text) if f.smell in (lint.SMELL_MISSING_KWIN, lint.SMELL_MISSING_KWOUT)]
    assert findings == []


def test_format_findings_returns_human_text():
    out = lint.format_findings([])
    assert "no smells" in out
    out = lint.format_findings(lint.scan(BAD_CODE_TRANSLATION))
    assert "smell" in out
