"""Anti-pattern detector for algorithm .tex snippets.

Enforces the most important convention imported from gen-pseudocode-skill:
**method-level abstraction, not code translation**. Surfaces framework-API and
implementation-primitive smells that should be replaced with mathematical
notation (cross-references the local notation table).

This is intentionally a regex-based linter — pseudocode .tex bodies are short
and we want zero LaTeX parsing dependencies. Findings are advisory; the skill
prompt decides what to surface to the user.
"""
from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class LintFinding:
    line: int          # 1-based line number into the input text
    smell: str         # one of the SMELL_* constants below
    snippet: str       # the offending substring (trimmed)
    fix_hint: str      # human-readable replacement suggestion


# Smell categories
SMELL_FRAMEWORK_CALL = "framework-call"
SMELL_TENSOR_LIB = "tensor-library"
SMELL_PYTHON_PRIMITIVE = "python-primitive"
SMELL_HASH_COMMENT = "hash-comment"
SMELL_MISSING_KWIN = "missing-input-decl"
SMELL_MISSING_KWOUT = "missing-output-decl"


# Patterns that should never appear in pseudocode (these are implementation, not method).
_FRAMEWORK_PATTERNS: tuple[tuple[re.Pattern[str], str, str], ...] = (
    (
        re.compile(r"optimizer\.(step|zero_grad)\s*\("),
        SMELL_FRAMEWORK_CALL,
        r"Drop framework calls. Use `$\theta \leftarrow \theta - \eta \nabla_\theta \mathcal{L}$` instead.",
    ),
    (
        re.compile(r"\.backward\s*\("),
        SMELL_FRAMEWORK_CALL,
        r"Replace `.backward()` with `$\nabla_\theta \mathcal{L}$` (see notation.md → gradient).",
    ),
    (
        re.compile(r"\.cuda\s*\(|\.to\s*\(\s*device"),
        SMELL_FRAMEWORK_CALL,
        "Device placement is implementation, not method. Delete this line.",
    ),
    (
        re.compile(r"\bmodel\.(train|eval)\s*\("),
        SMELL_FRAMEWORK_CALL,
        "Mode toggles are implementation. Indicate phase via the algorithm name / caption.",
    ),
    (
        re.compile(r"\b(zero_grad|requires_grad_?)\b"),
        SMELL_FRAMEWORK_CALL,
        "Framework bookkeeping — remove. Pseudocode operates on $\\theta$ directly.",
    ),
)

_TENSOR_LIB_PATTERNS: tuple[tuple[re.Pattern[str], str, str], ...] = (
    (
        re.compile(r"\b(torch|tf|np|jnp|F)\.[A-Za-z_]+"),
        SMELL_TENSOR_LIB,
        r"Replace tensor-library calls with math notation (see references/notation.md).",
    ),
    (
        re.compile(r"\bDataLoader\b"),
        SMELL_TENSOR_LIB,
        r"Use `mini-batch $(\mathbf{X}, \mathbf{y}) \sim \mathcal{D}$` instead of DataLoader.",
    ),
)

_PYTHON_PRIMITIVE_PATTERNS: tuple[tuple[re.Pattern[str], str, str], ...] = (
    (
        re.compile(r"^\s*(import\s+\w+|from\s+\w+\s+import\b)"),
        SMELL_PYTHON_PRIMITIVE,
        "Remove `import` lines — pseudocode is language-agnostic.",
    ),
    (
        re.compile(r"\brange\s*\(\s*len\s*\("),
        SMELL_PYTHON_PRIMITIVE,
        r"Replace `range(len(X))` with `$i = 1, \dots, |X|$` (see notation.md → index).",
    ),
    (
        re.compile(r"\benumerate\s*\("),
        SMELL_PYTHON_PRIMITIVE,
        r"Replace `enumerate(...)` with explicit indexing `$\mathbf{x}_i$`.",
    ),
)

# `#` comments leak from copy-pasted Python; LaTeX pseudocode uses `\tcp{}` / `\tcc{}`
# (algorithm2e) or `\Comment{}` (algpseudocode).
_HASH_COMMENT = re.compile(r"^(?P<lead>\s*[^%\n]*?)\s#\s.+$", re.MULTILINE)


def _scan_pattern_set(
    text: str,
    patterns: tuple[tuple[re.Pattern[str], str, str], ...],
) -> list[LintFinding]:
    findings: list[LintFinding] = []
    for pat, smell, hint in patterns:
        for m in pat.finditer(text):
            line = text.count("\n", 0, m.start()) + 1
            snippet = m.group(0).strip()
            findings.append(LintFinding(line=line, smell=smell, snippet=snippet, fix_hint=hint))
    return findings


def scan(text: str) -> list[LintFinding]:
    """Return all lint findings for an algorithm .tex snippet body."""
    findings: list[LintFinding] = []
    findings.extend(_scan_pattern_set(text, _FRAMEWORK_PATTERNS))
    findings.extend(_scan_pattern_set(text, _TENSOR_LIB_PATTERNS))
    findings.extend(_scan_pattern_set(text, _PYTHON_PRIMITIVE_PATTERNS))

    # `#`-style comments (but allow `%` LaTeX comments and ignore `#` inside math `$...$`).
    for m in _HASH_COMMENT.finditer(text):
        # crude math-mode guard: skip if the offending `#` is on a line that contains
        # an unmatched `$` before it (heuristic — pseudocode rarely uses `#` legitimately).
        line_no = text.count("\n", 0, m.start()) + 1
        line_text = m.group(0)
        if line_text.count("$") % 2 == 1:
            continue
        findings.append(
            LintFinding(
                line=line_no,
                smell=SMELL_HASH_COMMENT,
                snippet=line_text.strip(),
                fix_hint="Use `\\tcp{...}` (algorithm2e) or `\\Comment{...}` (algpseudocode) instead of `# ...`.",
            )
        )

    # Required declarations: at least one input + output marker must appear.
    has_input = bool(re.search(r"\\KwIn\b|\\Require\b", text))
    has_output = bool(re.search(r"\\KwOut\b|\\Ensure\b|\\Return\b", text))
    if not has_input:
        findings.append(
            LintFinding(
                line=1,
                smell=SMELL_MISSING_KWIN,
                snippet="(top of algorithm)",
                fix_hint=r"Add `\KwIn{...}` (algorithm2e) or `\Require ...` (algpseudocode).",
            )
        )
    if not has_output:
        findings.append(
            LintFinding(
                line=1,
                smell=SMELL_MISSING_KWOUT,
                snippet="(top of algorithm)",
                fix_hint=r"Add `\KwOut{...}` (algorithm2e) or `\Ensure ...` (algpseudocode), or end with `\Return`.",
            )
        )

    findings.sort(key=lambda f: (f.line, f.smell))
    return findings


def scan_file(path: Path) -> list[LintFinding]:
    return scan(path.read_text(encoding="utf-8"))


def format_findings(findings: list[LintFinding], *, source: Path | None = None) -> str:
    """Render a human-readable summary for the skill prompt to print."""
    if not findings:
        return "no smells — algorithm reads as method-level pseudocode."
    src = str(source) if source else "<input>"
    lines = [f"{len(findings)} smell(s):"]
    for f in findings:
        lines.append(f"  {src}:{f.line}  [{f.smell}]  {f.snippet}")
        lines.append(f"      → {f.fix_hint}")
    return "\n".join(lines)
