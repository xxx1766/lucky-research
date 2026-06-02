"""``archive`` module tests — compression choice, atomic write, sha256, DB
metadata extraction."""
from __future__ import annotations

import sqlite3
import zipfile
from pathlib import Path
from unittest.mock import patch

import pytest

from research_assistant.migrate import archive as arch
from research_assistant.migrate.archive import (
    ARCHIVE_MANIFEST_NAME,
    _choose_compression,
    db_namespace_row_counts,
    is_db_file,
    is_db_sidecar,
    is_encrypted_archive,
    open_archive,
    read_manifest,
    sha256_of_file,
    wal_checkpoint,
    write_archive,
)
from research_assistant.migrate.scan import FileItem


# ---------- compression policy ----------

@pytest.mark.parametrize("name,expected", [
    ("foo.safetensors", "stored"),
    ("foo.pdf", "stored"),
    ("foo.PNG", "stored"),
    ("foo.bin", "stored"),
    ("foo.parquet", "stored"),
    ("foo.md", "deflated"),
    ("foo.tex", "deflated"),
    ("foo.json", "deflated"),
    ("foo.py", "deflated"),
    ("foo.csv", "deflated"),
    ("foo.db", "deflated"),  # DB files are entropic-but-small enough to gain
    ("no_ext_at_all", "deflated"),
])
def test_choose_compression(name, expected):
    assert _choose_compression(name) == expected


# ---------- sha256 ----------

def test_sha256_of_file(tmp_path):
    p = tmp_path / "x.bin"
    p.write_bytes(b"hello world")
    # Pre-computed: sha256("hello world")
    assert sha256_of_file(p) == "b94d27b9934d3e08a52e52d7da7dabfac484efe37a5380ee9088f7ace2efcde9"


# ---------- DB helpers ----------

def test_is_db_file_and_sidecar():
    assert is_db_file("ruvector.db")
    assert is_db_file(".swarm/memory.db")
    assert not is_db_file("notes.db")  # not a tracked DB name
    assert is_db_sidecar("ruvector.db-wal")
    assert is_db_sidecar(".swarm/memory.db-shm")
    assert not is_db_sidecar("ruvector.db")
    assert not is_db_sidecar("foo.db-bak")


def _make_db(path: Path) -> None:
    """Create a tiny SQLite DB with a ``papers`` table holding a ``namespace`` col."""
    conn = sqlite3.connect(str(path))
    conn.execute("CREATE TABLE entries (id INTEGER, namespace TEXT)")
    conn.executemany(
        "INSERT INTO entries VALUES (?, ?)",
        [(1, "papers"), (2, "papers"), (3, "ideas")],
    )
    conn.commit()
    conn.close()


def test_db_namespace_row_counts(tmp_path):
    db = tmp_path / "ruvector.db"
    _make_db(db)
    counts = db_namespace_row_counts(db)
    assert counts == {"papers": 2, "ideas": 1}


def test_db_namespace_row_counts_missing_table(tmp_path):
    db = tmp_path / "ruvector.db"
    conn = sqlite3.connect(str(db))
    conn.execute("CREATE TABLE other (id INTEGER, label TEXT)")
    conn.commit()
    conn.close()
    assert db_namespace_row_counts(db) == {}


def test_db_namespace_row_counts_missing_file_returns_empty(tmp_path):
    assert db_namespace_row_counts(tmp_path / "nope.db") == {}


def test_wal_checkpoint_succeeds_on_real_db(tmp_path):
    db = tmp_path / "ruvector.db"
    _make_db(db)
    assert wal_checkpoint(db) is True


def test_wal_checkpoint_missing_file_returns_false(tmp_path):
    assert wal_checkpoint(tmp_path / "nope.db") is False


# ---------- write_archive end-to-end ----------

def test_write_archive_roundtrip_with_mixed_compression(tmp_path, monkeypatch):
    repo = tmp_path / "repo"
    (repo / "inputs" / "papers").mkdir(parents=True)
    (repo / "outputs").mkdir()
    monkeypatch.setattr(arch, "REPO_ROOT", repo)

    pdf = repo / "inputs" / "papers" / "x.pdf"
    md = repo / "outputs" / "notes.md"
    pdf.write_bytes(b"%PDF-1.4 fake pdf bytes")
    md.write_text("# notes\nhello\n")

    items = [
        FileItem(pdf, "inputs/papers/x.pdf", pdf.stat().st_size),
        FileItem(md, "outputs/notes.md", md.stat().st_size),
    ]
    archive_path = tmp_path / "out.zip"
    outcome = write_archive(
        archive_path, items, scope=["inputs", "outputs"],
        excluded_artifacts=[], repo_root=repo,
    )

    assert outcome.archive_path == archive_path
    assert archive_path.is_file()
    assert not archive_path.with_suffix(".zip.tmp").exists()

    with zipfile.ZipFile(archive_path) as zf:
        names = zf.namelist()
        assert "inputs/papers/x.pdf" in names
        assert "outputs/notes.md" in names
        assert ARCHIVE_MANIFEST_NAME in names
        pdf_info = zf.getinfo("inputs/papers/x.pdf")
        md_info = zf.getinfo("outputs/notes.md")
        assert pdf_info.compress_type == zipfile.ZIP_STORED
        assert md_info.compress_type == zipfile.ZIP_DEFLATED
        manifest_text = zf.read(ARCHIVE_MANIFEST_NAME).decode("utf-8")

    # Re-parse manifest from the zip and check entries.
    parsed = outcome.manifest
    paths = {e.path for e in parsed.files}
    assert paths == {"inputs/papers/x.pdf", "outputs/notes.md"}
    assert next(e for e in parsed.files if e.path == "inputs/papers/x.pdf").compression == "stored"
    assert next(e for e in parsed.files if e.path == "outputs/notes.md").compression == "deflated"
    assert "inputs/papers/x.pdf" in manifest_text


def test_write_archive_db_metadata_recorded(tmp_path, monkeypatch):
    repo = tmp_path / "repo"
    repo.mkdir()
    monkeypatch.setattr(arch, "REPO_ROOT", repo)

    db = repo / "ruvector.db"
    _make_db(db)
    items = [FileItem(db, "ruvector.db", db.stat().st_size)]
    archive_path = tmp_path / "out.zip"
    outcome = write_archive(
        archive_path, items, scope=["dbs"],
        excluded_artifacts=[], repo_root=repo,
    )
    assert len(outcome.manifest.dbs) == 1
    db_entry = outcome.manifest.dbs[0]
    assert db_entry.path == "ruvector.db"
    assert db_entry.row_counts_by_namespace == {"papers": 2, "ideas": 1}
    assert not outcome.manifest.files


def test_write_archive_drops_db_sidecars(tmp_path, monkeypatch):
    repo = tmp_path / "repo"
    repo.mkdir()
    monkeypatch.setattr(arch, "REPO_ROOT", repo)

    db = repo / "ruvector.db"
    _make_db(db)
    wal = repo / "ruvector.db-wal"
    shm = repo / "ruvector.db-shm"
    wal.write_bytes(b"\x00" * 32)
    shm.write_bytes(b"\x00" * 32)
    items = [
        FileItem(db, "ruvector.db", db.stat().st_size),
        FileItem(wal, "ruvector.db-wal", 32),
        FileItem(shm, "ruvector.db-shm", 32),
    ]
    archive_path = tmp_path / "out.zip"
    write_archive(
        archive_path, items, scope=["dbs"],
        excluded_artifacts=[], repo_root=repo,
    )
    with zipfile.ZipFile(archive_path) as zf:
        names = set(zf.namelist())
    assert "ruvector.db" in names
    assert "ruvector.db-wal" not in names
    assert "ruvector.db-shm" not in names


def test_write_archive_atomic_rename_on_failure(tmp_path, monkeypatch):
    """If the write loop blows up mid-way, no half-written .zip is left behind."""
    repo = tmp_path / "repo"
    repo.mkdir()
    monkeypatch.setattr(arch, "REPO_ROOT", repo)

    f = repo / "a.txt"
    f.write_text("hello")
    items = [FileItem(f, "a.txt", f.stat().st_size)]
    archive_path = tmp_path / "out.zip"

    with patch.object(arch, "_stream_into_zip", side_effect=RuntimeError("boom")):
        with pytest.raises(RuntimeError):
            write_archive(
                archive_path, items, scope=["test"],
                excluded_artifacts=[], repo_root=repo,
            )

    assert not archive_path.exists()
    assert not archive_path.with_suffix(".zip.tmp").exists()


# ---------- encryption ----------

def _seed_repo(tmp_path: Path, monkeypatch) -> tuple[Path, list]:
    repo = tmp_path / "repo"
    (repo / "inputs" / "papers").mkdir(parents=True)
    (repo / "outputs").mkdir()
    monkeypatch.setattr(arch, "REPO_ROOT", repo)
    pdf = repo / "inputs" / "papers" / "x.pdf"
    md = repo / "outputs" / "notes.md"
    pdf.write_bytes(b"%PDF-1.4 fake")
    md.write_text("# notes\nhello secrets\n")
    items = [
        FileItem(pdf, "inputs/papers/x.pdf", pdf.stat().st_size),
        FileItem(md, "outputs/notes.md", md.stat().st_size),
    ]
    return repo, items


def test_unencrypted_archive_detected_as_not_encrypted(tmp_path, monkeypatch):
    repo, items = _seed_repo(tmp_path, monkeypatch)
    archive_path = tmp_path / "plain.zip"
    write_archive(
        archive_path, items, scope=["inputs", "outputs"],
        excluded_artifacts=[], repo_root=repo,
    )
    assert is_encrypted_archive(archive_path) is False


def test_encrypted_archive_detected_via_flag_bits(tmp_path, monkeypatch):
    repo, items = _seed_repo(tmp_path, monkeypatch)
    archive_path = tmp_path / "enc.zip"
    write_archive(
        archive_path, items, scope=["inputs", "outputs"],
        excluded_artifacts=[], repo_root=repo, passphrase=b"hunter2",
    )
    assert is_encrypted_archive(archive_path) is True
    # The central directory still lists the filenames in plaintext (zip
    # format) — the entry CONTENTS are what's encrypted.
    with zipfile.ZipFile(archive_path) as zf:
        assert "inputs/papers/x.pdf" in zf.namelist()
        assert "outputs/notes.md" in zf.namelist()


def test_encrypted_round_trip_with_correct_passphrase(tmp_path, monkeypatch):
    repo, items = _seed_repo(tmp_path, monkeypatch)
    archive_path = tmp_path / "enc.zip"
    write_archive(
        archive_path, items, scope=["inputs", "outputs"],
        excluded_artifacts=[], repo_root=repo, passphrase=b"hunter2",
    )
    with open_archive(archive_path, passphrase=b"hunter2") as zf:
        assert zf.read("outputs/notes.md") == b"# notes\nhello secrets\n"
        manifest = read_manifest(zf)
    assert {e.path for e in manifest.files} == {"inputs/papers/x.pdf", "outputs/notes.md"}


def test_encrypted_archive_rejects_wrong_passphrase(tmp_path, monkeypatch):
    repo, items = _seed_repo(tmp_path, monkeypatch)
    archive_path = tmp_path / "enc.zip"
    write_archive(
        archive_path, items, scope=["inputs", "outputs"],
        excluded_artifacts=[], repo_root=repo, passphrase=b"hunter2",
    )
    with open_archive(archive_path, passphrase=b"wrong-pw") as zf:
        with pytest.raises(RuntimeError, match="[Bb]ad password"):
            zf.read("outputs/notes.md")


def test_encrypted_archive_unreadable_without_passphrase(tmp_path, monkeypatch):
    repo, items = _seed_repo(tmp_path, monkeypatch)
    archive_path = tmp_path / "enc.zip"
    write_archive(
        archive_path, items, scope=["inputs", "outputs"],
        excluded_artifacts=[], repo_root=repo, passphrase=b"hunter2",
    )
    # Stdlib zipfile (what open_archive returns without passphrase) reads the
    # central directory fine but raises when extracting an encrypted entry
    # without a password.
    with open_archive(archive_path) as zf:
        with pytest.raises(RuntimeError, match="encrypted"):
            zf.read("outputs/notes.md")


def test_is_encrypted_archive_handles_missing_or_bad_file(tmp_path):
    assert is_encrypted_archive(tmp_path / "nope.zip") is False
    bad = tmp_path / "not-a-zip.zip"
    bad.write_bytes(b"not actually zip")
    assert is_encrypted_archive(bad) is False


def test_encrypted_round_trip_preserves_per_entry_compression(tmp_path, monkeypatch):
    """AES doesn't change the per-entry compression policy: .pdf still stored,
    .md still deflated. Catches accidental defaulting to DEFLATE-for-everything
    in the encrypted writer path.

    AES-encrypted entries surface ``compress_type=99`` to stdlib zipfile (the
    AES sentinel); the *real* underlying compression is recorded in an extra
    field that pyzipper unwraps. We inspect via pyzipper here.
    """
    pyzipper = pytest.importorskip("pyzipper")
    repo, items = _seed_repo(tmp_path, monkeypatch)
    archive_path = tmp_path / "enc.zip"
    write_archive(
        archive_path, items, scope=["inputs", "outputs"],
        excluded_artifacts=[], repo_root=repo, passphrase=b"hunter2",
    )
    with pyzipper.AESZipFile(archive_path) as zf:
        assert zf.getinfo("inputs/papers/x.pdf").compress_type == zipfile.ZIP_STORED
        assert zf.getinfo("outputs/notes.md").compress_type == zipfile.ZIP_DEFLATED
