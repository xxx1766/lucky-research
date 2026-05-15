"""Tests for the idea slug helper."""
from __future__ import annotations

import pytest

from research_assistant.ideas.slug import slugify


def test_basic_lowercase_kebab():
    assert slugify("Memory-aware RAG") == "memory-aware-rag"


def test_collapses_punctuation():
    assert slugify("Self-Improving / RL Agents!") == "self-improving-rl-agents"


def test_strips_diacritics():
    assert slugify("Café-aware retrieval") == "cafe-aware-retrieval"


def test_strips_leading_trailing_hyphens():
    assert slugify("---Foo Bar---") == "foo-bar"


def test_cjk_with_no_ascii_raises():
    with pytest.raises(ValueError):
        slugify("纯中文标题")


def test_empty_input_raises():
    with pytest.raises(ValueError):
        slugify("")


def test_whitespace_only_raises():
    with pytest.raises(ValueError):
        slugify("   \t\n")


def test_long_input_caps_at_64():
    raw = "a very long idea title that goes way past the slug length cap easily"
    s = slugify(raw)
    assert len(s) <= 64
    assert not s.endswith("-")
    # Should cut on a hyphen boundary if possible
    assert "-" in s
