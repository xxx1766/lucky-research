"""Tests for the shared YAML-frontmatter helper."""
from __future__ import annotations

import pytest

from research_assistant.common.frontmatter import (
    parse,
    parse_optional,
    split_blocks,
)


def _write(tmp_path, text: str, name: str = "doc.md"):
    p = tmp_path / name
    p.write_text(text, encoding="utf-8")
    return p


def test_parse_happy_path(tmp_path):
    p = _write(tmp_path, "---\ntitle: hi\ntags: [a, b]\n---\nbody here\n")
    fm, body = parse(p)
    assert fm == {"title": "hi", "tags": ["a", "b"]}
    assert body == "body here\n"


def test_parse_optional_no_frontmatter(tmp_path):
    p = _write(tmp_path, "# just a body\n")
    fm, body = parse_optional(p)
    assert fm is None
    assert body == "# just a body\n"


def test_parse_missing_frontmatter_strict_raises(tmp_path):
    p = _write(tmp_path, "no frontmatter here\n")
    with pytest.raises(ValueError, match="missing YAML frontmatter"):
        parse(p)


def test_parse_non_mapping_raises(tmp_path):
    p = _write(tmp_path, "---\n- a\n- b\n---\n")
    with pytest.raises(ValueError, match="must be a YAML mapping"):
        parse(p)


def test_parse_empty_frontmatter_is_empty_dict(tmp_path):
    p = _write(tmp_path, "---\n---\nrest\n")
    fm, body = parse(p)
    assert fm == {}
    assert body == "rest\n"


def test_parse_malformed_yaml_raises(tmp_path):
    p = _write(tmp_path, "---\nkey: : value\n---\n")
    with pytest.raises(ValueError, match="malformed YAML"):
        parse(p)


def test_parse_crlf_line_endings(tmp_path):
    p = _write(tmp_path, "---\r\nx: 1\r\n---\r\nbody\r\n")
    fm, body = parse(p)
    assert fm == {"x": 1}
    assert "body" in body


def test_split_blocks_multiple_sections():
    text = (
        "---\nslug: a\ncategory: dataset\npath: x\n---\n"
        "first body line\n"
        "---\nslug: b\ncategory: trace\npath: y\n---\n"
        "second body\n"
    )
    blocks = split_blocks(text)
    assert len(blocks) == 2
    assert blocks[0][0]["slug"] == "a"
    assert blocks[0][1].startswith("first body")
    assert blocks[1][0]["slug"] == "b"


def test_split_blocks_empty_string():
    assert split_blocks("") == []


def test_split_blocks_no_fence_returns_empty():
    assert split_blocks("just prose, no fences\n") == []
