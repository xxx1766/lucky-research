"""Tests for the brain-library knowledge index."""
from __future__ import annotations

from research_assistant.ideas.knowledge import (
    KnowledgeIndex,
    KnowledgeItem,
    render_knowledge_md,
    to_agentdb_payload,
)


def test_render_has_all_four_sections():
    idx = KnowledgeIndex()
    md = render_knowledge_md(idx)
    assert "## Foundations" in md
    assert "## Key papers" in md
    assert "## Tools & datasets" in md
    assert "## Adjacent areas" in md


def test_empty_section_renders_placeholder():
    md = render_knowledge_md(KnowledgeIndex())
    assert md.count("_(no entries yet") == 4


def test_entries_render_topic_why_and_link():
    idx = KnowledgeIndex(
        foundations=[
            KnowledgeItem(
                topic="Contrastive learning",
                why_it_matters="re-ranking signal model",
                reading_url="https://arxiv.org/abs/2002.05709",
            ),
        ],
    )
    md = render_knowledge_md(idx)
    assert "**Contrastive learning**" in md
    assert "re-ranking signal model" in md
    assert "https://arxiv.org/abs/2002.05709" in md


def test_agentdb_payload_round_trip_shape():
    idx = KnowledgeIndex(
        foundations=[KnowledgeItem(topic="A", why_it_matters="x")],
        key_papers=[KnowledgeItem(topic="B", why_it_matters="y")],
        tools_and_datasets=[KnowledgeItem(topic="C", why_it_matters="z")],
        adjacent_areas=[KnowledgeItem(topic="D", why_it_matters="w")],
    )
    payload = to_agentdb_payload(idx)
    assert set(payload.keys()) == {
        "foundations", "key_papers", "tools_and_datasets", "adjacent_areas",
    }
    assert payload["foundations"][0]["topic"] == "A"
    assert payload["key_papers"][0]["why_it_matters"] == "y"
