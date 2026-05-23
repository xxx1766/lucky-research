"""Cross-machine state migration — `/migrate export` / `/migrate import`.

Bundles per-user state (inputs/, outputs/, ruvector.db, .swarm/memory.db,
.claude/settings.local.json, .claude-flow/config.yaml) into a single zip so
the user can move between machines. Excludes externally reproducible artifacts
(HF base-model shards, etc.) registered via per-experiment
``external-artifacts.md`` files.

Module layout:

* :mod:`research_assistant.migrate.manifest` — Pydantic schemas + YAML/JSON I/O
  for ``external-artifacts.md`` and the archive-level ``MANIFEST.json``.
* :mod:`research_assistant.migrate.scan` — repo walk + classification.
* :mod:`research_assistant.migrate.archive` — zip create / extract with
  per-entry compression strategy.
* :mod:`research_assistant.migrate.merge` — import-time collision policy.
* :mod:`research_assistant.migrate.cli` — ``python -m research_assistant.migrate``
  command-line entry.
"""

from research_assistant.migrate.manifest import (
    ArchiveManifest,
    ArtifactRecord,
    ExcludedArtifact,
    ExternalArtifacts,
    FileEntry,
    ImportReport,
    SourceInfo,
    external_artifacts_path,
    read_external_artifacts,
    write_external_artifacts,
)

__all__ = [
    "ArchiveManifest",
    "ArtifactRecord",
    "ExcludedArtifact",
    "ExternalArtifacts",
    "FileEntry",
    "ImportReport",
    "SourceInfo",
    "external_artifacts_path",
    "read_external_artifacts",
    "write_external_artifacts",
]
