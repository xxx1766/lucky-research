"""Helpers backing the `/pseudocode` slash and the `pseudocode-tool` skill.

Bounded subpackage that owns:
  * scope-aware path resolution (paths.py)
  * the `PseudocodeNote` schema (schema.py)
  * note.md frontmatter round-trip (note.py)
  * the anti-pattern linter that enforces method-level abstraction (lint.py)
  * venue-driven LaTeX preamble injection (preamble.py)
  * standalone-snippet compilation via tectonic/xelatex/pdflatex (compile.py)

Conventions imported (with adaptation) from
https://github.com/HuiyuLi-2000/gen-pseudocode-skill (MIT).
"""
