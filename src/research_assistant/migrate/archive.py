"""Zip create / extract with per-entry compression strategy + atomic write.

The export side streams files into a temporary ``.zip.tmp`` and renames to
the final name only on full success, so a crashed export never leaves a
half-built archive in place that looks complete.

Per-entry compression rule:

* ``ZIP_STORED`` (no compression, just bundled) for already-compressed binary
  blobs — ``.safetensors``, ``.pdf``, ``.png``, ``.jpg``, ``.zst``, ``.gz``,
  ``.zip``, ``.parquet``. Deflate gives ~zero size reduction for these and
  costs CPU.
* ``ZIP_DEFLATED`` for everything else (``.md``, ``.tex``, ``.json``, ``.py``,
  ``.csv``, ``.db``, log/text files).
"""
from __future__ import annotations

import getpass
import hashlib
import os
import socket
import sqlite3
import subprocess
import sys
import zipfile
from collections.abc import Callable, Iterable
from datetime import datetime
from pathlib import Path
from typing import IO, NamedTuple

from research_assistant.common.io import REPO_ROOT
from research_assistant.migrate.manifest import (
    ArchiveManifest,
    CompressionMode,
    DBEntry,
    ExcludedArtifact,
    FileEntry,
    SourceInfo,
)
from research_assistant.migrate.scan import (
    DB_SIDECAR_SUFFIXES,
    FileItem,
)

ARCHIVE_MANIFEST_NAME = "MANIFEST.json"

# Extensions where ZIP_DEFLATE buys ~nothing. Stored verbatim.
_STORED_EXTS = frozenset({
    ".safetensors", ".bin",
    ".pdf", ".png", ".jpg", ".jpeg", ".gif", ".webp", ".heic",
    ".zst", ".gz", ".bz2", ".xz", ".zip", ".tar", ".7z",
    ".parquet", ".feather", ".arrow",
    ".mp3", ".mp4", ".webm", ".mov", ".avi",
    ".pkl", ".npy", ".npz",
})

_CHUNK = 1024 * 1024  # 1 MiB streaming chunks for hash + write

# Files we always treat as DBs that need WAL-checkpoint + special handling.
_DB_BASENAMES = frozenset({"ruvector.db", "memory.db"})


def _choose_compression(rel_path: str) -> CompressionMode:
    """Pick STORED vs DEFLATED based on file extension."""
    ext = Path(rel_path).suffix.lower()
    return "stored" if ext in _STORED_EXTS else "deflated"


def _zip_compression_for(mode: CompressionMode) -> int:
    return zipfile.ZIP_STORED if mode == "stored" else zipfile.ZIP_DEFLATED


def sha256_of_file(path: Path) -> str:
    """Stream-hash ``path``. Returns lowercase hex digest."""
    h = hashlib.sha256()
    with path.open("rb") as f:
        while True:
            chunk = f.read(_CHUNK)
            if not chunk:
                break
            h.update(chunk)
    return h.hexdigest()


# ---------- DB helpers ----------

def wal_checkpoint(db_path: Path) -> bool:
    """Run ``PRAGMA wal_checkpoint(TRUNCATE)`` against ``db_path``.

    Returns True on success, False on any sqlite error (caller decides whether
    a checkpoint failure is fatal — it isn't, the archive just risks pulling
    in stale -wal data that SQLite will recover on next open).
    """
    if not db_path.is_file():
        return False
    try:
        conn = sqlite3.connect(str(db_path), timeout=2.0)
        try:
            conn.execute("PRAGMA wal_checkpoint(TRUNCATE)")
            conn.commit()
        finally:
            conn.close()
        return True
    except sqlite3.Error:
        return False


def is_db_file(rel_path: str) -> bool:
    """Whether ``rel_path`` is a SQLite database we treat specially."""
    name = Path(rel_path).name
    return name in _DB_BASENAMES


def is_db_sidecar(rel_path: str) -> bool:
    """Whether ``rel_path`` is a ``-shm`` or ``-wal`` sidecar of a tracked DB."""
    name = Path(rel_path).name
    for suf in DB_SIDECAR_SUFFIXES:
        if not name.endswith(suf):
            continue
        base = name[: -len(suf)]
        if base in _DB_BASENAMES:
            return True
    return False


def db_namespace_row_counts(db_path: Path) -> dict[str, int]:
    """Best-effort: read row counts grouped by ``namespace`` from a DB.

    Inspects each user table for a ``namespace`` column; if found, runs a
    ``SELECT namespace, COUNT(*) GROUP BY``. Returns an empty dict on any
    schema we don't recognize — the field is informational only.
    """
    if not db_path.is_file():
        return {}
    out: dict[str, int] = {}
    try:
        conn = sqlite3.connect(str(db_path), timeout=2.0)
        try:
            rows = conn.execute(
                "SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%'"
            ).fetchall()
            for (table,) in rows:
                if not _is_safe_identifier(table):
                    continue
                cols = conn.execute(f'PRAGMA table_info("{table}")').fetchall()
                if not any(c[1] == "namespace" for c in cols):
                    continue
                ns_rows = conn.execute(
                    f'SELECT namespace, COUNT(*) FROM "{table}" GROUP BY namespace'
                ).fetchall()
                for ns, n in ns_rows:
                    if ns is None:
                        continue
                    key = str(ns)
                    out[key] = out.get(key, 0) + int(n)
        finally:
            conn.close()
    except sqlite3.Error:
        return {}
    return out


def _is_safe_identifier(name: str) -> bool:
    return name.replace("_", "").isalnum() and not name.startswith("sqlite_")


# ---------- source info ----------

def _plugin_git_info() -> tuple[str | None, bool]:
    """Return ``(sha, dirty)`` for the plugin checkout at ``REPO_ROOT``."""
    sha: str | None = None
    dirty = False
    try:
        out = subprocess.run(  # noqa: S603 — no shell, fixed argv
            ["git", "-C", str(REPO_ROOT), "rev-parse", "HEAD"],
            capture_output=True, text=True, timeout=5, check=False,
        )
        if out.returncode == 0:
            sha = out.stdout.strip() or None
    except (subprocess.TimeoutExpired, FileNotFoundError, OSError):
        return None, False
    try:
        st = subprocess.run(  # noqa: S603 — no shell, fixed argv
            ["git", "-C", str(REPO_ROOT), "status", "--porcelain"],
            capture_output=True, text=True, timeout=5, check=False,
        )
        if st.returncode == 0 and st.stdout.strip():
            dirty = True
    except (subprocess.TimeoutExpired, FileNotFoundError, OSError):
        dirty = False
    return sha, dirty


def make_source_info() -> SourceInfo:
    sha, dirty = _plugin_git_info()
    return SourceInfo(
        hostname=socket.gethostname(),
        username=getpass.getuser(),
        exported_at=datetime.now().astimezone(),
        plugin_git_sha=sha,
        plugin_git_dirty=dirty,
        python_version=sys.version.split()[0],
    )


# ---------- write ----------

ProgressCB = Callable[[str, int, int], None]


class WriteOutcome(NamedTuple):
    archive_path: Path
    manifest: ArchiveManifest


def write_archive(
    output_path: Path,
    items: Iterable[FileItem],
    *,
    scope: list[str],
    excluded_artifacts: list[ExcludedArtifact],
    repo_root: Path | None = None,
    progress: ProgressCB | None = None,
) -> WriteOutcome:
    """Write all ``items`` into a zip at ``output_path``.

    Writes to ``<output_path>.tmp`` and renames to ``<output_path>`` only on
    full success. ``items`` may include DBs and regular files; DB sidecars
    (``-shm`` / ``-wal``) are dropped here at the write boundary in addition
    to the scan step, defensively.
    """
    output_path.parent.mkdir(parents=True, exist_ok=True)
    tmp = output_path.with_suffix(output_path.suffix + ".tmp")
    if tmp.exists():
        tmp.unlink()

    source = make_source_info()
    manifest = ArchiveManifest(
        source=source, scope=scope, excluded_artifacts=list(excluded_artifacts)
    )
    items_list = list(items)
    total = len(items_list)

    # Pre-pass: checkpoint any DB we're about to bundle so the file we hash
    # below matches the file the user sees on the new machine after a fresh
    # SQLite open. Without this the -wal could hold uncheckpointed writes.
    seen_db_paths: set[Path] = set()
    for it in items_list:
        if is_db_file(it.rel_path):
            wal_checkpoint(it.abs_path)
            seen_db_paths.add(it.abs_path)

    try:
        with zipfile.ZipFile(tmp, "w", allowZip64=True) as zf:
            for i, it in enumerate(items_list, start=1):
                if is_db_sidecar(it.rel_path):
                    # Drop WAL sidecars — they recreate themselves on import.
                    if progress:
                        progress(it.rel_path, i, total)
                    continue
                mode = _choose_compression(it.rel_path)
                size = it.size if it.size else _safe_size(it.abs_path)
                digest = _stream_into_zip(zf, it.abs_path, it.rel_path, mode)
                if is_db_file(it.rel_path):
                    db_path = it.abs_path
                    manifest.dbs.append(DBEntry(
                        path=it.rel_path, size=size, sha256=digest,
                        row_counts_by_namespace=db_namespace_row_counts(db_path),
                    ))
                else:
                    manifest.files.append(FileEntry(
                        path=it.rel_path, size=size, sha256=digest, compression=mode,
                    ))
                if progress:
                    progress(it.rel_path, i, total)
            # Write the manifest last so it always reflects the actual file set.
            zf.writestr(
                ARCHIVE_MANIFEST_NAME,
                manifest.to_json(),
                compress_type=zipfile.ZIP_DEFLATED,
            )
    except BaseException:
        # Any failure (including KeyboardInterrupt) — leave no half-written .zip.
        if tmp.exists():
            tmp.unlink()
        raise

    os.replace(tmp, output_path)
    return WriteOutcome(archive_path=output_path, manifest=manifest)


def _stream_into_zip(
    zf: zipfile.ZipFile, src: Path, arcname: str, mode: CompressionMode
) -> str:
    """Copy ``src`` into ``zf`` at ``arcname`` and return its sha256 digest.

    We hash and write in the same chunk loop so we touch the file once.
    """
    info = zipfile.ZipInfo.from_file(str(src), arcname=arcname)
    info.compress_type = _zip_compression_for(mode)
    h = hashlib.sha256()
    with zf.open(info, "w", force_zip64=True) as dst, src.open("rb") as f:
        while True:
            chunk = f.read(_CHUNK)
            if not chunk:
                break
            h.update(chunk)
            dst.write(chunk)
    return h.hexdigest()


def _safe_size(p: Path) -> int:
    try:
        return p.stat().st_size
    except OSError:
        return 0


# ---------- read ----------

class ArchiveEntry(NamedTuple):
    """One item from an archive, paired with the manifest entry that describes it."""

    arcname: str
    is_db: bool
    expected_sha256: str | None
    info: zipfile.ZipInfo


def open_archive(path: Path) -> zipfile.ZipFile:
    """Open ``path`` as a ZipFile in read mode. Caller is responsible for closing."""
    return zipfile.ZipFile(path, "r", allowZip64=True)


def read_manifest(zf: zipfile.ZipFile) -> ArchiveManifest:
    """Read and parse the ``MANIFEST.json`` from an open archive."""
    try:
        raw = zf.read(ARCHIVE_MANIFEST_NAME)
    except KeyError as e:
        raise ValueError(
            f"archive missing {ARCHIVE_MANIFEST_NAME} — not a migrate archive"
        ) from e
    return ArchiveManifest.from_json(raw.decode("utf-8"))


def iter_entries(
    zf: zipfile.ZipFile, manifest: ArchiveManifest
) -> Iterable[ArchiveEntry]:
    """Yield :class:`ArchiveEntry` for every file / DB recorded in the manifest.

    Looks up each manifest entry's ``ZipInfo`` so the caller has the
    metadata (modtime, compressed size) without re-scanning the zip.
    """
    name_to_info: dict[str, zipfile.ZipInfo] = {i.filename: i for i in zf.infolist()}
    for e in manifest.files:
        info = name_to_info.get(e.path)
        if info is None:
            continue
        yield ArchiveEntry(
            arcname=e.path, is_db=False, expected_sha256=e.sha256, info=info,
        )
    for d in manifest.dbs:
        info = name_to_info.get(d.path)
        if info is None:
            continue
        yield ArchiveEntry(
            arcname=d.path, is_db=True, expected_sha256=d.sha256, info=info,
        )


def extract_to(
    zf: zipfile.ZipFile, arcname: str, dest: Path,
) -> str:
    """Stream-extract ``arcname`` from ``zf`` to ``dest`` and return sha256.

    Creates parent dirs as needed. Caller chooses ``dest`` per the merge
    policy — this function never decides where things go.
    """
    dest.parent.mkdir(parents=True, exist_ok=True)
    h = hashlib.sha256()
    with zf.open(arcname, "r") as src, dest.open("wb") as f:
        while True:
            chunk = src.read(_CHUNK)
            if not chunk:
                break
            h.update(chunk)
            f.write(chunk)
    return h.hexdigest()


def open_for_streaming(zf: zipfile.ZipFile, arcname: str) -> IO[bytes]:
    """Open an archive member as a binary stream. Caller closes."""
    return zf.open(arcname, "r")
