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
  per-entry compression strategy + AES-256 via pyzipper (``--encrypt``).
* :mod:`research_assistant.migrate.merge` — import-time collision policy
  (``*.from-migrate-<ts>.<ext>`` for files, ``*.from-migrate.db`` for DBs).
* :mod:`research_assistant.migrate.cli` — ``python -m research_assistant.migrate``
  command-line entry; hosts ``_synthesize_fetch_cmd`` + ``_resolve_passphrase``.
* :mod:`research_assistant.migrate.cli_artifacts` — ``/migrate artifacts``
  subcommand group (list / register / scan); also shelled out by
  ``/experiment artifacts``.
* :mod:`research_assistant.migrate.reindex` — JSONL payload emitter that
  walks on-disk markdown / YAML truth sources and produces
  ``mcp__claude-flow__memory_store(**payload)`` kwargs.

The top-level ``__all__`` re-exports manifest schemas only — the I/O entry
points are reached via :mod:`research_assistant.migrate.cli`.
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
