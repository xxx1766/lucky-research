"""Brain-library knowledge index for `/idea-check knowledge`.

Produces a structured study plan for one idea: foundations to master, key
papers to read, tools/datasets to set up, adjacent areas to keep in scope.
The same payload is mirrored into AgentDB ``ideas/<slug>/knowledge`` so
``/paper write`` can later ground in it.
"""
from __future__ import annotations

from pydantic import BaseModel, Field


class KnowledgeItem(BaseModel):
    """One entry in the index — a concept, paper, tool, or adjacent area."""

    topic: str
    why_it_matters: str
    reading_url: str | None = None


class KnowledgeIndex(BaseModel):
    """Per-idea brain-library index. Empty lists are valid (just render as TBD)."""

    foundations: list[KnowledgeItem] = Field(default_factory=list)
    key_papers: list[KnowledgeItem] = Field(default_factory=list)
    tools_and_datasets: list[KnowledgeItem] = Field(default_factory=list)
    adjacent_areas: list[KnowledgeItem] = Field(default_factory=list)


def _render_section(title: str, items: list[KnowledgeItem]) -> list[str]:
    out = [f"## {title}", ""]
    if not items:
        out.append("_(no entries yet — refine with `/idea-check knowledge`)_")
        out.append("")
        return out
    for item in items:
        anchor = f" — [{item.reading_url}]({item.reading_url})" if item.reading_url else ""
        out.append(f"- **{item.topic}** — {item.why_it_matters}{anchor}")
    out.append("")
    return out


def render_knowledge_md(idx: KnowledgeIndex) -> str:
    """Render the index to ``outputs/idea-checks/<slug>/knowledge.md``."""
    lines: list[str] = ["# Brain-library index", ""]
    lines.append("This is your study plan for this idea. `/paper write` reads")
    lines.append("AgentDB `ideas/<slug>/knowledge` to ground prose in these entries.")
    lines.append("")
    lines.extend(_render_section("Foundations", idx.foundations))
    lines.extend(_render_section("Key papers", idx.key_papers))
    lines.extend(_render_section("Tools & datasets", idx.tools_and_datasets))
    lines.extend(_render_section("Adjacent areas", idx.adjacent_areas))
    return "\n".join(lines).rstrip() + "\n"


def to_agentdb_payload(idx: KnowledgeIndex) -> dict:
    """Compact payload for ``mcp__claude-flow__memory_store namespace=ideas, key=<slug>/knowledge``."""
    return {
        "foundations": [i.model_dump() for i in idx.foundations],
        "key_papers": [i.model_dump() for i in idx.key_papers],
        "tools_and_datasets": [i.model_dump() for i in idx.tools_and_datasets],
        "adjacent_areas": [i.model_dump() for i in idx.adjacent_areas],
    }
