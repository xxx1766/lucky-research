"""Project-level research notes — state.yaml + findings.md + log.md triplet.

Adapted from Orchestra-Research/AI-Research-SKILLs (MIT) `0-autoresearch-skill`.
The Orchestra design separates *per-experiment* state (which lucky-research
already handles under ``outputs/experiments/<slug>/``) from *project-level*
state — the running synthesis above individual experiments. That's the gap
this module fills.

A project lives at ``outputs/research-notes/<slug>/`` with three files:

* ``state.yaml``   — machine-readable state (the
  :class:`ResearchNotesState` shape). Holds the hypothesis tree, the
  experiments registry, and the outer-loop cycle counter.
* ``findings.md``  — running synthesis. Updated by ``/mentor project
  finding`` and during weekly check-ins.
* ``log.md``       — append-only decision timeline (one row per call to
  ``/mentor project log``).

Slug convention matches the rest of the package — kebab-case English,
non-alphanumerics collapsed to hyphens.

The skill body (``research-mentor/SKILL.md``) is responsible for the AgentDB
cursor (``project/research-notes-context``). The helpers here are pure
filesystem so they remain easy to unit-test offline.
"""
from __future__ import annotations

import re
from datetime import date
from pathlib import Path
from typing import Literal

import yaml
from pydantic import BaseModel, Field

from research_assistant.common.frontmatter import parse as parse_fm
from research_assistant.common.io import OUTPUTS_DIR

RESEARCH_NOTES_DIR = OUTPUTS_DIR / "research-notes"

_SLUG_CLEAN = re.compile(r"[^a-z0-9]+")
_TEMPLATES = Path(__file__).resolve().parents[3] / "docs"

LogKind = Literal[
    "bootstrap", "inner-loop", "outer-loop", "pivot", "report", "conclude"
]


# ---------- models ----------


class KeyPaper(BaseModel):
    slug: str
    title: str | None = None
    year: int | None = None
    relevance: str | None = None


class Hypothesis(BaseModel):
    id: str
    statement: str
    parent: str | None = None
    status: Literal[
        "pending", "active", "supported", "refuted", "inconclusive"
    ] = "pending"
    priority: Literal["high", "medium", "low"] = "medium"
    motivation: str | None = None


class ProjectMeta(BaseModel):
    slug: str
    title: str
    question: str = ""
    status: Literal["active", "paused", "concluded"] = "active"
    started: str = ""
    domain: str = ""


class Literature(BaseModel):
    key_papers: list[KeyPaper] = Field(default_factory=list)
    open_problems: list[str] = Field(default_factory=list)
    evidence_gaps: list[str] = Field(default_factory=list)


class ExperimentsBlock(BaseModel):
    proxy_metric: str = ""
    baseline_value: float | None = None
    best_value: float | None = None
    total_runs: int = 0
    bound_slugs: list[str] = Field(default_factory=list)


class OuterLoop(BaseModel):
    cycle: int = 0
    last_direction: Literal["deepen", "broaden", "pivot", "conclude"] | None = None
    last_reflection: str = ""


class Workspace(BaseModel):
    findings: str = "findings.md"
    log: str = "log.md"
    paper_direction: str | None = None


class ResearchNotesState(BaseModel):
    project: ProjectMeta
    literature: Literature = Field(default_factory=Literature)
    hypotheses: list[Hypothesis] = Field(default_factory=list)
    experiments: ExperimentsBlock = Field(default_factory=ExperimentsBlock)
    outer_loop: OuterLoop = Field(default_factory=OuterLoop)
    workspace: Workspace = Field(default_factory=Workspace)


# ---------- slug + path helpers ----------


def slugify(title: str) -> str:
    cleaned = _SLUG_CLEAN.sub("-", title.lower()).strip("-")
    if not cleaned:
        raise ValueError(f"empty research-notes slug for title={title!r}")
    return cleaned


def project_dir(slug: str) -> Path:
    if not slug or "/" in slug or slug.startswith("."):
        raise ValueError(f"invalid research-notes slug: {slug!r}")
    return RESEARCH_NOTES_DIR / slug


def state_path(slug: str) -> Path:
    return project_dir(slug) / "state.yaml"


def findings_path(slug: str) -> Path:
    return project_dir(slug) / "findings.md"


def log_path(slug: str) -> Path:
    return project_dir(slug) / "log.md"


def list_projects() -> list[str]:
    """Return slugs of every project under ``outputs/research-notes/``."""
    if not RESEARCH_NOTES_DIR.is_dir():
        return []
    return sorted(
        p.name for p in RESEARCH_NOTES_DIR.iterdir()
        if p.is_dir() and not p.name.startswith(".")
        and (p / "state.yaml").is_file()
    )


# ---------- init / read / write ----------


def init_project(slug: str, title: str, question: str = "") -> Path:
    """Create ``outputs/research-notes/<slug>/`` with the three template files.

    Refuses to overwrite an existing project. Returns the project directory.
    """
    pdir = project_dir(slug)
    if pdir.exists():
        raise FileExistsError(f"research-notes project already exists: {pdir}")
    pdir.mkdir(parents=True, exist_ok=False)

    state = ResearchNotesState(
        project=ProjectMeta(
            slug=slug, title=title, question=question,
            started=date.today().isoformat(),
        )
    )
    write_state(slug, state)

    findings_template = (_TEMPLATES / "research-notes-findings-template.md").read_text(
        encoding="utf-8"
    )
    findings_path(slug).write_text(
        findings_template.replace("{{title}}", title), encoding="utf-8"
    )

    log_template = (_TEMPLATES / "research-notes-log-template.md").read_text(
        encoding="utf-8"
    )
    log_path(slug).write_text(
        log_template.replace("{{title}}", title), encoding="utf-8"
    )

    return pdir


def read_state(slug: str) -> ResearchNotesState:
    path = state_path(slug)
    if not path.is_file():
        raise FileNotFoundError(f"no state.yaml for project {slug!r}")
    data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    if not isinstance(data, dict):
        raise ValueError(f"state.yaml for {slug!r} is not a mapping")
    return ResearchNotesState.model_validate(data)


def write_state(slug: str, state: ResearchNotesState) -> None:
    path = state_path(slug)
    path.parent.mkdir(parents=True, exist_ok=True)
    text = yaml.safe_dump(
        state.model_dump(exclude_none=False, mode="json"),
        sort_keys=False, allow_unicode=True,
    )
    path.write_text(text, encoding="utf-8")


# ---------- mutations: log + finding ----------


def append_log(slug: str, kind: LogKind, summary: str, *, today: date | None = None) -> int:
    """Append one row to ``log.md``. Returns the new row number.

    The log table sits between the first ``|`` line and the closing
    ``<!-- Entry types: -->`` comment. Rows are numbered starting at 1.
    """
    if kind not in {"bootstrap", "inner-loop", "outer-loop", "pivot", "report", "conclude"}:
        raise ValueError(f"unknown log kind: {kind!r}")
    summary = summary.strip().replace("|", "\\|")
    if not summary:
        raise ValueError("empty log summary")
    today = today or date.today()

    path = log_path(slug)
    if not path.is_file():
        raise FileNotFoundError(f"no log.md for project {slug!r}")
    text = path.read_text(encoding="utf-8")

    lines = text.splitlines(keepends=False)
    # Find the header row "|---|" and the blank placeholder row "| | | | |".
    sep_idx = next(
        (i for i, line in enumerate(lines) if line.startswith("|---")), None
    )
    if sep_idx is None:
        raise ValueError(f"log.md for {slug!r} missing header separator")

    # Count existing data rows (lines after separator that look like "| N | ...").
    row_re = re.compile(r"^\|\s*(\d+)\s*\|")
    last_n = 0
    insert_idx = sep_idx + 1
    for i in range(sep_idx + 1, len(lines)):
        m = row_re.match(lines[i])
        if m:
            last_n = max(last_n, int(m.group(1)))
            insert_idx = i + 1
            continue
        # Treat the empty placeholder row "| | | | |" as not-a-row.
        if lines[i].strip() == "| | | | |":
            # Skip the placeholder; insert *before* it on first real append.
            if last_n == 0:
                insert_idx = i
            continue
        if lines[i].strip().startswith("|"):
            # Some other table-shaped line; keep skipping.
            continue
        # Stop at the first non-table line (blank / HTML comment / heading).
        break

    new_n = last_n + 1
    new_row = f"| {new_n} | {today.isoformat()} | {kind} | {summary} |"
    new_lines = lines[:insert_idx] + [new_row] + lines[insert_idx:]
    # Drop the original placeholder row if we just inserted the first real row.
    if new_n == 1:
        new_lines = [
            line for line in new_lines if line.strip() != "| | | | |"
        ]
    path.write_text("\n".join(new_lines) + "\n", encoding="utf-8")
    return new_n


def append_finding(slug: str, section: str, body: str) -> Path:
    """Append a markdown paragraph under the named ``## <section>`` heading.

    ``section`` is matched case-insensitively. If the heading is missing,
    a new ``## <section>`` is appended at end of file. The body is written
    verbatim (the caller decides whether to add a leading bullet, etc.).
    """
    section = section.strip()
    if not section:
        raise ValueError("empty section name")
    body = body.rstrip()
    if not body:
        raise ValueError("empty finding body")

    path = findings_path(slug)
    if not path.is_file():
        raise FileNotFoundError(f"no findings.md for project {slug!r}")
    text = path.read_text(encoding="utf-8")
    lines = text.splitlines(keepends=False)

    target = section.lower()
    heading_idx = next(
        (i for i, line in enumerate(lines)
         if line.startswith("## ") and line[3:].strip().lower() == target),
        None,
    )
    if heading_idx is None:
        # Append a new section at end.
        tail = [""] if lines and lines[-1] != "" else []
        lines.extend(tail + [f"## {section}", "", body, ""])
    else:
        # Find the next heading or end.
        end_idx = next(
            (i for i in range(heading_idx + 1, len(lines))
             if lines[i].startswith("## ")),
            len(lines),
        )
        # Insert just before that next heading; drop trailing blank lines first.
        insertion = end_idx
        while insertion > heading_idx + 1 and lines[insertion - 1].strip() == "":
            insertion -= 1
        prefix = [""] if insertion > heading_idx + 1 else [""]
        lines = lines[:insertion] + prefix + [body, ""] + lines[insertion:]
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return path


# ---------- parser convenience (for /mentor project show) ----------


def parse_log(slug: str) -> list[dict]:
    """Read ``log.md`` and return the rows as ``[{n, date, kind, summary}, ...]``.

    Skips the empty placeholder row and ignores malformed lines.
    """
    path = log_path(slug)
    if not path.is_file():
        return []
    text = path.read_text(encoding="utf-8")
    rows: list[dict] = []
    row_re = re.compile(r"^\|\s*(\d+)\s*\|\s*([^|]+?)\s*\|\s*([^|]+?)\s*\|\s*(.+?)\s*\|\s*$")
    for line in text.splitlines():
        m = row_re.match(line)
        if not m:
            continue
        rows.append({
            "n": int(m.group(1)),
            "date": m.group(2),
            "kind": m.group(3),
            "summary": m.group(4),
        })
    return rows


def to_agentdb_payload(state: ResearchNotesState) -> dict:
    """Format a project state for ``mcp__claude-flow__memory_store``.

    Mirrors the same pattern as ``past_work.to_agentdb_payload`` — flat
    metadata only, no long prose. Used by ``/mentor project sync``.
    """
    return {
        "kind": "research_notes",
        "slug": state.project.slug,
        "title": state.project.title,
        "question": state.project.question,
        "status": state.project.status,
        "started": state.project.started,
        "domain": state.project.domain,
        "hypothesis_count": len(state.hypotheses),
        "outer_loop_cycle": state.outer_loop.cycle,
        "last_direction": state.outer_loop.last_direction,
        "bound_experiments": list(state.experiments.bound_slugs),
    }


# Re-export parse_fm symbol so callers that already import from this module
# don't need a second import line.
__all__ = [
    "RESEARCH_NOTES_DIR",
    "ResearchNotesState",
    "ProjectMeta",
    "Literature",
    "KeyPaper",
    "Hypothesis",
    "ExperimentsBlock",
    "OuterLoop",
    "Workspace",
    "slugify",
    "project_dir",
    "state_path",
    "findings_path",
    "log_path",
    "list_projects",
    "init_project",
    "read_state",
    "write_state",
    "append_log",
    "append_finding",
    "parse_log",
    "to_agentdb_payload",
    "parse_fm",
]
