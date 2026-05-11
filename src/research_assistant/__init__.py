"""lucky-research: Claude Code research-assistant plugin.

Five MVP capabilities — each exposed as a Claude Code Skill under `.claude/skills/`:
- lit-summarize    (literature summarization)
- idea-validate    (horizontal comparison + vertical deep-dive)
- paper-architect  (outline + section drafting)
- ref-manager      (BibTeX + Markdown/LaTeX/docx)
- research-mentor  (long-running trajectory tracking)

This Python package holds the deterministic helpers (PDF parse, BibTeX, pandoc shell-outs,
trajectory diff). Skills invoke these helpers; Claude handles prose/reasoning.
"""

__version__ = "0.0.1"
