"""Import-time collision policy.

Default rule (the "never overwrite" rule the user asked for): the archive's
copy never wins. If a destination file already exists, the archive's copy is
written **next to it** with a ``.from-migrate-<timestamp>`` suffix; the user
can compare and merge by hand. For SQLite DBs we use a dedicated suffix
``.from-migrate.db`` (no per-extract timestamp, because the DB is one shot
and the source-machine timestamp is in :class:`SourceInfo`).
"""
from __future__ import annotations

import zipfile
from datetime import datetime
from pathlib import Path

from research_assistant.common.io import REPO_ROOT
from research_assistant.migrate.archive import (
    ArchiveEntry,
    extract_to,
    is_db_file,
    is_db_sidecar,
)
from research_assistant.migrate.manifest import ImportEntry, ImportVerdict


def _suffix_path(dest: Path, ts: str) -> Path:
    """Return ``<stem>.from-migrate-<ts><ext>`` next to ``dest``."""
    return dest.with_name(f"{dest.stem}.from-migrate-{ts}{dest.suffix}")


def _db_sidecar_path(dest: Path) -> Path:
    """Return ``<stem>.from-migrate.db`` next to ``dest``.

    DB destination paths always end with ``.db``; the rule strips the
    extension and appends the marker so ``ruvector.db`` →
    ``ruvector.from-migrate.db``.
    """
    return dest.with_name(f"{dest.stem}.from-migrate.db")


def _dest_for(arcname: str, *, repo_root: Path) -> Path:
    """Map an archive's repo-relative arcname to its destination on disk."""
    # Defensive: refuse absolute paths and parent-traversal in archive entries.
    p = Path(arcname)
    if p.is_absolute() or ".." in p.parts:
        raise ValueError(f"unsafe archive entry: {arcname}")
    return repo_root / p


def _verdict_for_file(
    zf: zipfile.ZipFile,
    entry: ArchiveEntry,
    *,
    repo_root: Path,
    ts: str,
    dry_run: bool,
) -> ImportEntry:
    dest = _dest_for(entry.arcname, repo_root=repo_root)
    if dest.exists() and dest.is_file():
        sidecar = _suffix_path(dest, ts)
        if not dry_run:
            extracted_sha = extract_to(zf, entry.arcname, sidecar)
        else:
            extracted_sha = entry.expected_sha256 or ""
        note = None
        verdict: ImportVerdict = "collision"
        if entry.expected_sha256 and extracted_sha and extracted_sha != entry.expected_sha256:
            note = (
                f"sha256 mismatch (expected {entry.expected_sha256[:12]}..., "
                f"got {extracted_sha[:12]}...)"
            )
            verdict = "checksum-warn"
        return ImportEntry(
            path=entry.arcname,
            verdict=verdict,
            sidecar_path=str(sidecar.relative_to(repo_root)),
            note=note,
        )
    if dry_run:
        return ImportEntry(path=entry.arcname, verdict="restored")
    extracted_sha = extract_to(zf, entry.arcname, dest)
    if entry.expected_sha256 and extracted_sha != entry.expected_sha256:
        return ImportEntry(
            path=entry.arcname,
            verdict="checksum-warn",
            note=(
                f"sha256 mismatch (expected {entry.expected_sha256[:12]}..., "
                f"got {extracted_sha[:12]}...)"
            ),
        )
    return ImportEntry(path=entry.arcname, verdict="restored")


def _verdict_for_db(
    zf: zipfile.ZipFile,
    entry: ArchiveEntry,
    *,
    repo_root: Path,
    dry_run: bool,
) -> ImportEntry:
    dest = _dest_for(entry.arcname, repo_root=repo_root)
    dest_size = dest.stat().st_size if dest.is_file() else 0
    if dest_size > 0:
        sidecar = _db_sidecar_path(dest)
        if not dry_run:
            extract_to(zf, entry.arcname, sidecar)
        return ImportEntry(
            path=entry.arcname,
            verdict="db-sidecar",
            sidecar_path=str(sidecar.relative_to(repo_root)),
            note="new-machine DB was non-empty; archive copy preserved alongside",
        )
    if dry_run:
        return ImportEntry(path=entry.arcname, verdict="db-restored")
    extract_to(zf, entry.arcname, dest)
    return ImportEntry(path=entry.arcname, verdict="db-restored")


def apply(
    zf: zipfile.ZipFile,
    entries: list[ArchiveEntry],
    *,
    repo_root: Path | None = None,
    dry_run: bool = False,
    now: datetime | None = None,
) -> list[ImportEntry]:
    """Materialize ``entries`` onto disk per the collision policy.

    Returns a list of :class:`ImportEntry` describing what happened to each
    arcname — feed the result into
    :meth:`research_assistant.migrate.manifest.ImportReport` for a report file.
    """
    root = (repo_root or REPO_ROOT).resolve()
    ts = (now or datetime.now()).strftime("%Y%m%d-%H%M%S")
    out: list[ImportEntry] = []
    for e in entries:
        if is_db_sidecar(e.arcname):
            # Defensive — shouldn't appear in a well-formed manifest.
            out.append(ImportEntry(
                path=e.arcname, verdict="skipped",
                note="WAL sidecar (-shm/-wal) — SQLite recreates on open",
            ))
            continue
        if e.is_db or is_db_file(e.arcname):
            out.append(_verdict_for_db(zf, e, repo_root=root, dry_run=dry_run))
        else:
            out.append(_verdict_for_file(zf, e, repo_root=root, ts=ts, dry_run=dry_run))
    return out
