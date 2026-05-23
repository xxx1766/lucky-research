"""Schemas + I/O for ``external-artifacts.md`` and archive ``MANIFEST.json``.

Two file formats live here:

1. **``outputs/experiments/<slug>/external-artifacts.md``** — per-experiment
   YAML-frontmatter file listing artifacts that are reproducible from external
   sources (HuggingFace, http, git-lfs) and should be excluded from migration
   archives. ``/experiment artifacts register|scan|list`` writes/reads this;
   ``/migrate export`` consults it for exclusion.

2. **archive ``MANIFEST.json``** — top-level JSON entry inside every migration
   zip. Records source-machine info, per-file entries (path + size + sha256 +
   compression mode), DB summaries, and the list of excluded external
   artifacts with their re-fetch commands so ``/migrate import`` can print a
   re-fetch checklist on the destination machine.
"""
from __future__ import annotations

import json
import re
from datetime import datetime
from pathlib import Path
from typing import Literal

import yaml
from pydantic import BaseModel, Field, field_validator

from research_assistant.common.io import EXPERIMENTS_DIR

# ---------- per-experiment external-artifacts.md ----------

ArtifactSourceType = Literal["huggingface", "http", "git-lfs", "s3", "other"]


class ArtifactRecord(BaseModel):
    """One reproducible-from-external-source artifact in an experiment.

    Fields:

    * ``name`` — short human label (e.g. ``llama2-7b-base``).
    * ``path`` — directory **relative to the experiment dir**, e.g.
      ``repo/motivation/m1/base``. Path-traversal rejected.
    * ``glob`` — glob (relative to ``path``) matching the files to exclude.
      Default ``*`` excludes everything under ``path``.
    * ``type`` / ``repo`` / ``revision`` — source pointer.
    * ``size_estimate`` — free-form (e.g. ``"13GB"``); informational only.
    * ``fetch_cmd`` — shell command the user runs on the destination to
      re-pull. Synthesized from ``type`` + ``repo`` if not given.
    """

    name: str
    path: str
    glob: str = "*"
    type: ArtifactSourceType = "other"
    repo: str | None = None
    revision: str | None = None
    size_estimate: str | None = None
    fetch_cmd: str | None = None

    @field_validator("path")
    @classmethod
    def _path_no_absolute_no_traversal(cls, v: str) -> str:
        if not v:
            raise ValueError("artifact path cannot be empty")
        p = Path(v)
        if p.is_absolute():
            raise ValueError(f"artifact path must be relative: {v}")
        if ".." in p.parts:
            raise ValueError(f"artifact path cannot traverse parents: {v}")
        return v.rstrip("/")

    @field_validator("name")
    @classmethod
    def _name_nonempty(cls, v: str) -> str:
        if not v or not v.strip():
            raise ValueError("artifact name cannot be empty")
        return v.strip()


class ExternalArtifacts(BaseModel):
    """The parsed contents of a single ``external-artifacts.md`` file."""

    artifacts: list[ArtifactRecord] = Field(default_factory=list)
    body: str = ""  # prose after the frontmatter, preserved on round-trip


def external_artifacts_path(slug: str) -> Path:
    """Resolve ``outputs/experiments/<slug>/external-artifacts.md``.

    Re-validates the slug against ``EXPERIMENTS_DIR`` the same way
    :func:`research_assistant.experiments.experiment_path` does, but kept
    local here to avoid a circular import (manifest is a leaf module).
    """
    if not slug:
        raise ValueError("empty experiment slug")
    candidate = (EXPERIMENTS_DIR / slug).resolve()
    root = EXPERIMENTS_DIR.resolve()
    if root != candidate and root not in candidate.parents:
        raise ValueError(f"experiment slug escapes experiments dir: {slug}")
    return candidate / "external-artifacts.md"


_FM_RE = re.compile(r"^---\r?\n(.*?)\r?\n---\r?\n?(.*)$", re.DOTALL)


def read_external_artifacts(path: Path) -> ExternalArtifacts:
    """Read a ``external-artifacts.md`` file. Missing → empty result.

    Raises :class:`ValueError` if the file exists but has no YAML
    frontmatter or fails schema validation — callers should treat that as a
    config bug, not a missing-file condition.
    """
    if not path.is_file():
        return ExternalArtifacts()
    text = path.read_text(encoding="utf-8")
    m = _FM_RE.match(text)
    if not m:
        raise ValueError(f"{path} has no YAML frontmatter")
    fm = yaml.safe_load(m.group(1)) or {}
    body = m.group(2)
    return ExternalArtifacts(
        artifacts=[ArtifactRecord(**r) for r in fm.get("artifacts", [])],
        body=body,
    )


def write_external_artifacts(path: Path, ea: ExternalArtifacts) -> None:
    """Serialize ``ea`` to ``path``. Idempotent; overwrites existing files.

    The frontmatter is rendered via ``yaml.safe_dump`` with ``sort_keys=False``
    so the on-disk order matches construction order. The prose ``body`` is
    appended verbatim.
    """
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = {"artifacts": [r.model_dump(exclude_none=True) for r in ea.artifacts]}
    fm_text = yaml.safe_dump(payload, sort_keys=False, allow_unicode=True).rstrip("\n")
    path.write_text(f"---\n{fm_text}\n---\n{ea.body}", encoding="utf-8")


# ---------- archive MANIFEST.json ----------

class SourceInfo(BaseModel):
    hostname: str
    username: str
    exported_at: datetime
    plugin_git_sha: str | None = None
    plugin_git_dirty: bool = False
    python_version: str


CompressionMode = Literal["stored", "deflated"]


class FileEntry(BaseModel):
    path: str  # repo-relative
    size: int
    sha256: str
    compression: CompressionMode


class DBEntry(BaseModel):
    path: str
    size: int
    sha256: str
    row_counts_by_namespace: dict[str, int] = Field(default_factory=dict)


class ExcludedArtifact(BaseModel):
    """One ``ArtifactRecord`` plus the experiment it belongs to.

    Embedded into the archive ``MANIFEST.json`` so ``/migrate import`` can
    print a re-fetch checklist without needing the source-machine
    ``external-artifacts.md`` files.
    """

    experiment: str
    name: str
    dest_path: str  # repo-relative, e.g. outputs/experiments/<slug>/repo/motivation/m1/base
    glob: str
    type: ArtifactSourceType
    repo: str | None = None
    revision: str | None = None
    size_estimate: str | None = None
    fetch_cmd: str | None = None


class ArchiveManifest(BaseModel):
    """Top-level ``MANIFEST.json`` inside every migration zip."""

    version: int = 1
    source: SourceInfo
    scope: list[str] = Field(default_factory=list)
    files: list[FileEntry] = Field(default_factory=list)
    dbs: list[DBEntry] = Field(default_factory=list)
    excluded_artifacts: list[ExcludedArtifact] = Field(default_factory=list)

    def to_json(self) -> str:
        return json.dumps(self.model_dump(mode="json"), indent=2, sort_keys=False)

    @classmethod
    def from_json(cls, text: str) -> ArchiveManifest:
        return cls.model_validate_json(text)


# ---------- import report ----------

ImportVerdict = Literal[
    "restored",       # file written at dest (no collision)
    "collision",      # dest existed; archive copy saved as .from-migrate-<ts>.*
    "db-restored",    # DB written at dest (dest absent / empty)
    "db-sidecar",     # dest DB non-empty; archive copy saved as .from-migrate.db
    "skipped",        # entry intentionally skipped (e.g. -shm / -wal)
    "checksum-warn",  # restored but sha256 mismatch logged
]


class ImportEntry(BaseModel):
    path: str
    verdict: ImportVerdict
    sidecar_path: str | None = None
    note: str | None = None


class ImportReport(BaseModel):
    archive: str
    imported_at: datetime
    source: SourceInfo
    entries: list[ImportEntry] = Field(default_factory=list)
    excluded_artifacts: list[ExcludedArtifact] = Field(default_factory=list)

    def to_markdown(self) -> str:
        """Render the report as Markdown for ``outputs/migrate/imports/*.report.md``."""
        lines = [
            f"# Migrate import — {self.archive}",
            "",
            f"- Imported at: {self.imported_at.isoformat(timespec='seconds')}",
            f"- Source host: {self.source.hostname} (user: {self.source.username})",
            f"- Source exported at: {self.source.exported_at.isoformat(timespec='seconds')}",
            "",
        ]
        verdicts: dict[str, int] = {}
        for e in self.entries:
            verdicts[e.verdict] = verdicts.get(e.verdict, 0) + 1
        lines.append("## Summary")
        for v in (
            "restored", "collision", "db-restored", "db-sidecar",
            "skipped", "checksum-warn",
        ):
            n = verdicts.get(v, 0)
            if n:
                lines.append(f"- **{v}**: {n}")
        lines.append("")
        if any(e.verdict == "collision" for e in self.entries):
            lines.append("## Collisions (archive copies saved as sidecars)")
            for e in self.entries:
                if e.verdict == "collision":
                    lines.append(f"- `{e.path}` → `{e.sidecar_path}`")
            lines.append("")
        if any(e.verdict == "db-sidecar" for e in self.entries):
            lines.append("## DB sidecars (new-machine DB preserved)")
            for e in self.entries:
                if e.verdict == "db-sidecar":
                    lines.append(f"- `{e.path}` → `{e.sidecar_path}`")
            lines.append("")
        if self.excluded_artifacts:
            lines.append("## External artifacts to re-fetch")
            for a in self.excluded_artifacts:
                lines.append(f"### {a.experiment} / {a.name}")
                lines.append(f"- Destination: `{a.dest_path}` (glob `{a.glob}`)")
                lines.append(f"- Source: {a.type} {a.repo or ''} @ {a.revision or 'main'}")
                if a.size_estimate:
                    lines.append(f"- Estimated size: {a.size_estimate}")
                if a.fetch_cmd:
                    lines.append("- Fetch command:")
                    lines.append("  ```")
                    for line in a.fetch_cmd.strip().splitlines():
                        lines.append(f"  {line}")
                    lines.append("  ```")
                lines.append("")
        return "\n".join(lines)
