"""Shared YAML-frontmatter parser for ``---\\n<yaml>\\n---\\n<body>`` markdown files.

Centralizes the split-and-parse pattern used by every plugin domain that
persists state in YAML frontmatter (boss profile, past-work, experiment
manifests/versions/feasibility/design, venue refs). Each domain validates the
returned dict into its own Pydantic model.

Two entry points:

* :func:`parse` — strict. Missing or non-mapping frontmatter raises ``ValueError``.
* :func:`parse_optional` — lenient. Returns ``(None, full_text)`` when no
  frontmatter is present, ``(dict, body)`` otherwise.
"""
from __future__ import annotations

from pathlib import Path

import yaml


def _split(text: str) -> tuple[str, str] | None:
    """Locate the ``---\\n...\\n---\\n`` block. Return ``(yaml_text, body)`` or ``None``.

    Accepts ``\\r\\n`` line endings and trailing whitespace on the opening/closing
    fences. The body is everything after the closing fence, with one leading
    newline stripped if present.
    """
    if not text.startswith("---"):
        return None
    rest = text[3:].lstrip("\r\n")
    if rest.startswith("---"):
        # empty frontmatter (`---\n---\n`): closing fence sits at offset 0.
        after = rest[3:]
        after = after.lstrip("\r")
        if after.startswith("\n"):
            after = after[1:]
        return "", after
    end = rest.find("\n---")
    if end == -1:
        return None
    yaml_text = rest[:end].rstrip()
    after = rest[end + len("\n---"):]
    after = after.lstrip("\r")
    if after.startswith("\n"):
        after = after[1:]
    return yaml_text, after


def parse_optional(path: Path | str) -> tuple[dict | None, str]:
    """Read ``path`` and split frontmatter. Tolerant — no frontmatter is fine.

    Returns ``(None, full_text)`` when the file does not start with ``---``,
    otherwise ``(frontmatter_dict, body)``. A frontmatter block whose YAML is
    empty (``--- ---``) yields an empty dict, not ``None``.

    Raises ``ValueError`` if frontmatter is present but the YAML is malformed
    or does not parse to a mapping.
    """
    text = Path(path).read_text(encoding="utf-8")
    split = _split(text)
    if split is None:
        return None, text
    yaml_text, body = split
    try:
        data = yaml.safe_load(yaml_text) if yaml_text.strip() else {}
    except yaml.YAMLError as e:
        raise ValueError(f"malformed YAML frontmatter in {path}: {e}") from e
    if data is None:
        data = {}
    if not isinstance(data, dict):
        raise ValueError(f"frontmatter in {path} must be a YAML mapping, got {type(data).__name__}")
    return data, body


def parse(path: Path | str) -> tuple[dict, str]:
    """Read ``path`` and require YAML frontmatter. Strict variant.

    Returns ``(frontmatter_dict, body)``. Raises ``ValueError`` when the file
    has no frontmatter, has malformed YAML, or has frontmatter that is not a
    mapping.
    """
    data, body = parse_optional(path)
    if data is None:
        raise ValueError(f"missing YAML frontmatter in {path}")
    return data, body


def split_blocks(text: str) -> list[tuple[dict, str]]:
    """Parse repeated ``---\\n<yaml>\\n---\\n<body>`` sections in one string.

    Returns a list of ``(frontmatter_dict, body)`` pairs, one per block. The
    body for each block ends where the next block's opening ``---`` begins (or
    at end-of-text). Blocks with malformed YAML or non-mapping frontmatter are
    skipped — this is intentionally lenient because callers (e.g.
    ``parse_data_index``) read user-edited registries that may have partial
    entries.

    A string that does not start with ``---`` returns ``[]``.
    """
    blocks: list[tuple[dict, str]] = []
    remaining = text
    while True:
        split = _split(remaining)
        if split is None:
            return blocks
        yaml_text, after = split
        next_fence = after.find("\n---")
        if next_fence == -1:
            body = after
            remaining = ""
        else:
            body = after[:next_fence].rstrip("\r\n")
            remaining = after[next_fence + 1:]
        try:
            data = yaml.safe_load(yaml_text) if yaml_text.strip() else {}
        except yaml.YAMLError:
            if not remaining:
                return blocks
            continue
        if isinstance(data, dict):
            blocks.append((data, body))
        if not remaining:
            return blocks
