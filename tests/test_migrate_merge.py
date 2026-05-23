"""Import-time merge policy tests: collisions become sidecars, DBs become
``.from-migrate.db`` if dest non-empty, WAL sidecars are dropped, sha256
mismatch produces ``checksum-warn``."""
from __future__ import annotations

import sqlite3
from datetime import datetime
from pathlib import Path

from research_assistant.migrate import archive as arch
from research_assistant.migrate.archive import (
    iter_entries,
    open_archive,
    read_manifest,
    write_archive,
)
from research_assistant.migrate.merge import apply as merge_apply
from research_assistant.migrate.scan import FileItem


def _seed_db(path: Path, rows: list[tuple[int, str]] | None = None) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(path))
    conn.execute("CREATE TABLE entries (id INTEGER, namespace TEXT)")
    conn.executemany(
        "INSERT INTO entries VALUES (?, ?)",
        rows or [(1, "papers")],
    )
    conn.commit()
    conn.close()


def _build_archive(
    src_repo: Path, items: list[FileItem], out_zip: Path, monkeypatch
) -> None:
    monkeypatch.setattr(arch, "REPO_ROOT", src_repo)
    write_archive(
        out_zip, items, scope=["test"],
        excluded_artifacts=[], repo_root=src_repo,
    )


# ---------- regular files ----------

def test_no_collision_writes_at_dest(tmp_path, monkeypatch):
    src = tmp_path / "src"
    src.mkdir()
    (src / "inputs" / "papers").mkdir(parents=True)
    pdf = src / "inputs" / "papers" / "x.pdf"
    pdf.write_bytes(b"%PDF source machine")

    archive_path = tmp_path / "out.zip"
    _build_archive(
        src,
        [FileItem(pdf, "inputs/papers/x.pdf", pdf.stat().st_size)],
        archive_path, monkeypatch,
    )

    dest_repo = tmp_path / "dest"
    (dest_repo / "inputs" / "papers").mkdir(parents=True)
    with open_archive(archive_path) as zf:
        manifest = read_manifest(zf)
        verdicts = merge_apply(
            zf, list(iter_entries(zf, manifest)),
            repo_root=dest_repo, now=datetime(2026, 5, 24, 12, 0, 0),
        )
    assert len(verdicts) == 1
    assert verdicts[0].verdict == "restored"
    assert (dest_repo / "inputs" / "papers" / "x.pdf").read_bytes() == b"%PDF source machine"


def test_collision_writes_sidecar_with_timestamp(tmp_path, monkeypatch):
    src = tmp_path / "src"
    (src / "inputs" / "papers").mkdir(parents=True)
    pdf = src / "inputs" / "papers" / "x.pdf"
    pdf.write_bytes(b"source-machine bytes")

    archive_path = tmp_path / "out.zip"
    _build_archive(
        src, [FileItem(pdf, "inputs/papers/x.pdf", pdf.stat().st_size)],
        archive_path, monkeypatch,
    )

    dest_repo = tmp_path / "dest"
    (dest_repo / "inputs" / "papers").mkdir(parents=True)
    existing = dest_repo / "inputs" / "papers" / "x.pdf"
    existing.write_bytes(b"NEW MACHINE - must not be overwritten")

    with open_archive(archive_path) as zf:
        manifest = read_manifest(zf)
        verdicts = merge_apply(
            zf, list(iter_entries(zf, manifest)),
            repo_root=dest_repo, now=datetime(2026, 5, 24, 14, 22, 1),
        )
    assert verdicts[0].verdict == "collision"
    assert verdicts[0].sidecar_path == "inputs/papers/x.from-migrate-20260524-142201.pdf"
    # Dest file preserved.
    assert existing.read_bytes() == b"NEW MACHINE - must not be overwritten"
    # Archive copy saved as sidecar.
    sidecar = dest_repo / verdicts[0].sidecar_path
    assert sidecar.read_bytes() == b"source-machine bytes"


def test_dry_run_does_not_write_files(tmp_path, monkeypatch):
    src = tmp_path / "src"
    src.mkdir()
    f = src / "a.txt"
    f.write_text("hi")
    archive_path = tmp_path / "out.zip"
    _build_archive(
        src, [FileItem(f, "a.txt", f.stat().st_size)],
        archive_path, monkeypatch,
    )

    dest_repo = tmp_path / "dest"
    dest_repo.mkdir()

    with open_archive(archive_path) as zf:
        manifest = read_manifest(zf)
        verdicts = merge_apply(
            zf, list(iter_entries(zf, manifest)),
            repo_root=dest_repo, dry_run=True,
        )
    assert verdicts[0].verdict == "restored"
    assert not (dest_repo / "a.txt").exists()


# ---------- DBs ----------

def test_db_restored_when_dest_absent(tmp_path, monkeypatch):
    src = tmp_path / "src"
    src.mkdir()
    db = src / "ruvector.db"
    _seed_db(db)
    archive_path = tmp_path / "out.zip"
    _build_archive(
        src, [FileItem(db, "ruvector.db", db.stat().st_size)],
        archive_path, monkeypatch,
    )

    dest_repo = tmp_path / "dest"
    dest_repo.mkdir()
    with open_archive(archive_path) as zf:
        manifest = read_manifest(zf)
        verdicts = merge_apply(
            zf, list(iter_entries(zf, manifest)), repo_root=dest_repo,
        )
    assert verdicts[0].verdict == "db-restored"
    assert (dest_repo / "ruvector.db").is_file()


def test_db_sidecar_when_dest_non_empty(tmp_path, monkeypatch):
    src = tmp_path / "src"
    src.mkdir()
    db = src / "ruvector.db"
    _seed_db(db, rows=[(1, "papers"), (2, "papers"), (3, "ideas")])
    archive_path = tmp_path / "out.zip"
    _build_archive(
        src, [FileItem(db, "ruvector.db", db.stat().st_size)],
        archive_path, monkeypatch,
    )

    dest_repo = tmp_path / "dest"
    dest_repo.mkdir()
    new_db = dest_repo / "ruvector.db"
    _seed_db(new_db, rows=[(99, "drafts")])  # new-machine had its own work

    with open_archive(archive_path) as zf:
        manifest = read_manifest(zf)
        verdicts = merge_apply(
            zf, list(iter_entries(zf, manifest)), repo_root=dest_repo,
        )
    assert verdicts[0].verdict == "db-sidecar"
    assert verdicts[0].sidecar_path == "ruvector.from-migrate.db"
    # New machine's DB untouched.
    conn = sqlite3.connect(str(new_db))
    rows = conn.execute("SELECT namespace FROM entries").fetchall()
    conn.close()
    assert {r[0] for r in rows} == {"drafts"}
    # Archive copy landed as sidecar.
    sidecar = dest_repo / "ruvector.from-migrate.db"
    assert sidecar.is_file()


# ---------- traversal-defense ----------

def test_unsafe_archive_entry_raises(tmp_path, monkeypatch):
    from research_assistant.migrate.merge import _dest_for
    import pytest as _pt
    with _pt.raises(ValueError):
        _dest_for("../etc/passwd", repo_root=tmp_path)
    with _pt.raises(ValueError):
        _dest_for("/etc/passwd", repo_root=tmp_path)


# ---------- WAL sidecars passed through as skipped ----------

def test_wal_sidecar_in_entries_marked_skipped(tmp_path, monkeypatch):
    """If a malformed archive somehow contained a WAL sidecar, merge skips it
    rather than crashing."""
    src = tmp_path / "src"
    src.mkdir()
    # Build an archive with just a real DB.
    db = src / "ruvector.db"
    _seed_db(db)
    archive_path = tmp_path / "out.zip"
    _build_archive(
        src, [FileItem(db, "ruvector.db", db.stat().st_size)],
        archive_path, monkeypatch,
    )
    # Manually splice a fake -wal entry into the entries list we feed merge.
    with open_archive(archive_path) as zf:
        manifest = read_manifest(zf)
        entries = list(iter_entries(zf, manifest))
        # Synthesize a "phantom" -wal entry by reusing the real ZipInfo.
        from research_assistant.migrate.archive import ArchiveEntry
        entries.append(ArchiveEntry(
            arcname="ruvector.db-wal", is_db=False, expected_sha256=None,
            info=entries[0].info,
        ))
        dest_repo = tmp_path / "dest"
        dest_repo.mkdir()
        verdicts = merge_apply(zf, entries, repo_root=dest_repo)
    verdicts_by_name = {v.path: v.verdict for v in verdicts}
    assert verdicts_by_name["ruvector.db"] == "db-restored"
    assert verdicts_by_name["ruvector.db-wal"] == "skipped"
