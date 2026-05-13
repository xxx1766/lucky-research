"""Figure-tool helpers — schema + I/O + export + palette + refs.

Each figure lives under either:
  * paper scope:      outputs/papers/<venue>/<direction>/figures/<slug>.{svg,pdf,png}
  * experiment scope: outputs/experiments/<slug>/repo/figures/<vN.M>/<slug>.{svg,pdf,png}
                      (or repo/figures/_arch/<slug>.{svg,pdf,png} for non-versioned)

Reference figures (the curated "good paper figures" collection) live at
inputs/figure-refs/<slug>/ — gitignored, indexed in AgentDB project/figure-refs/<slug>.

Mirrors three patterns already in the codebase:
  * research_assistant.papers for stage status + path resolution.
  * research_assistant.mentor.past_work for Pydantic models + AgentDB payload defer.
  * research_assistant.experiments for path-traversal guards + slugify.
"""
from __future__ import annotations
