"""Schema + I/O tests for ``research_assistant.migrate.manifest``."""
from __future__ import annotations

from datetime import datetime, timezone

import pytest

from research_assistant.migrate import manifest as mf
from research_assistant.migrate.manifest import (
    ArchiveManifest,
    ArtifactRecord,
    DBEntry,
    ExcludedArtifact,
    ExternalArtifacts,
    FileEntry,
    ImportEntry,
    ImportReport,
    SourceInfo,
    external_artifacts_path,
    read_external_artifacts,
    write_external_artifacts,
)


# ---------- ArtifactRecord validators ----------

def test_artifact_record_accepts_minimal():
    r = ArtifactRecord(name="foo", path="repo/m1/base")
    assert r.glob == "*"
    assert r.type == "other"


def test_artifact_record_rejects_absolute_path():
    with pytest.raises(ValueError):
        ArtifactRecord(name="foo", path="/etc/passwd")


def test_artifact_record_rejects_parent_traversal():
    with pytest.raises(ValueError):
        ArtifactRecord(name="foo", path="repo/../etc")


def test_artifact_record_rejects_empty_path():
    with pytest.raises(ValueError):
        ArtifactRecord(name="foo", path="")


def test_artifact_record_strips_trailing_slash():
    r = ArtifactRecord(name="foo", path="repo/m1/base/")
    assert r.path == "repo/m1/base"


def test_artifact_record_rejects_empty_name():
    with pytest.raises(ValueError):
        ArtifactRecord(name="   ", path="repo/x")


# ---------- external-artifacts.md round-trip ----------

def test_external_artifacts_path_guards_traversal(tmp_path, monkeypatch):
    monkeypatch.setattr(mf, "EXPERIMENTS_DIR", tmp_path)
    with pytest.raises(ValueError):
        external_artifacts_path("../etc")
    with pytest.raises(ValueError):
        external_artifacts_path("")


def test_external_artifacts_path_resolves_under_experiments(tmp_path, monkeypatch):
    monkeypatch.setattr(mf, "EXPERIMENTS_DIR", tmp_path)
    p = external_artifacts_path("my-slug")
    assert p == tmp_path / "my-slug" / "external-artifacts.md"


def test_read_returns_empty_for_missing_file(tmp_path, monkeypatch):
    monkeypatch.setattr(mf, "EXPERIMENTS_DIR", tmp_path)
    out = read_external_artifacts(tmp_path / "nope.md")
    assert out.artifacts == []
    assert out.body == ""


def test_round_trip_preserves_records_and_body(tmp_path, monkeypatch):
    monkeypatch.setattr(mf, "EXPERIMENTS_DIR", tmp_path)
    path = external_artifacts_path("slug")
    original = ExternalArtifacts(
        artifacts=[
            ArtifactRecord(
                name="llama-base",
                path="repo/m1/base",
                glob="model-*.safetensors",
                type="huggingface",
                repo="meta-llama/Llama-2-7b-hf",
                revision="main",
                size_estimate="13GB",
                fetch_cmd="huggingface-cli download meta-llama/Llama-2-7b-hf",
            ),
        ],
        body="\nNotes about the artifact.\n",
    )
    write_external_artifacts(path, original)
    parsed = read_external_artifacts(path)
    assert len(parsed.artifacts) == 1
    a = parsed.artifacts[0]
    assert a.name == "llama-base"
    assert a.path == "repo/m1/base"
    assert a.glob == "model-*.safetensors"
    assert a.type == "huggingface"
    assert a.repo == "meta-llama/Llama-2-7b-hf"
    assert a.size_estimate == "13GB"
    assert "Notes about" in parsed.body


def test_read_raises_on_missing_frontmatter(tmp_path, monkeypatch):
    monkeypatch.setattr(mf, "EXPERIMENTS_DIR", tmp_path)
    path = tmp_path / "external-artifacts.md"
    path.write_text("no frontmatter here\njust prose\n", encoding="utf-8")
    with pytest.raises(ValueError):
        read_external_artifacts(path)


# ---------- ArchiveManifest JSON round-trip ----------

def test_archive_manifest_json_roundtrip():
    src = SourceInfo(
        hostname="srcbox",
        username="alice",
        exported_at=datetime(2026, 5, 23, 14, 22, 1, tzinfo=timezone.utc),
        plugin_git_sha="deadbeef",
        plugin_git_dirty=False,
        python_version="3.11.7",
    )
    m = ArchiveManifest(
        source=src,
        scope=["inputs", "outputs"],
        files=[FileEntry(path="inputs/papers/x.pdf", size=42, sha256="a" * 64, compression="stored")],
        dbs=[DBEntry(path="ruvector.db", size=100, sha256="b" * 64, row_counts_by_namespace={"papers": 3})],
        excluded_artifacts=[
            ExcludedArtifact(
                experiment="exp1", name="base", dest_path="outputs/experiments/exp1/repo/m1/base",
                glob="model-*.safetensors", type="huggingface", repo="meta/X", revision="v1",
            ),
        ],
    )
    text = m.to_json()
    back = ArchiveManifest.from_json(text)
    assert back.source.hostname == "srcbox"
    assert back.files[0].compression == "stored"
    assert back.dbs[0].row_counts_by_namespace == {"papers": 3}
    assert back.excluded_artifacts[0].dest_path.endswith("/base")


# ---------- ImportReport rendering ----------

def test_import_report_markdown_lists_collisions_and_artifacts():
    src = SourceInfo(
        hostname="srcbox", username="alice",
        exported_at=datetime(2026, 5, 23, tzinfo=timezone.utc),
        python_version="3.11.7",
    )
    report = ImportReport(
        archive="migrate-foo.zip",
        imported_at=datetime(2026, 5, 24, tzinfo=timezone.utc),
        source=src,
        entries=[
            ImportEntry(path="inputs/papers/x.pdf", verdict="restored"),
            ImportEntry(
                path="inputs/papers/y.pdf", verdict="collision",
                sidecar_path="inputs/papers/y.from-migrate-20260524-101010.pdf",
            ),
            ImportEntry(
                path="ruvector.db", verdict="db-sidecar",
                sidecar_path="ruvector.from-migrate.db",
            ),
        ],
        excluded_artifacts=[
            ExcludedArtifact(
                experiment="exp1", name="base",
                dest_path="outputs/experiments/exp1/repo/m1/base",
                glob="model-*.safetensors", type="huggingface",
                repo="meta/X", revision="v1", size_estimate="13GB",
                fetch_cmd="huggingface-cli download meta/X",
            ),
        ],
    )
    md = report.to_markdown()
    assert "## Summary" in md
    assert "**restored**: 1" in md
    assert "**collision**: 1" in md
    assert "**db-sidecar**: 1" in md
    assert "Collisions" in md
    assert "y.from-migrate-20260524-101010.pdf" in md
    assert "ruvector.from-migrate.db" in md
    assert "External artifacts to re-fetch" in md
    assert "huggingface-cli download meta/X" in md
