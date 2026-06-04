"""Tests for ``python -m research_assistant.migrate artifacts {list,register,scan}``.

The audit found cli_artifacts had zero test coverage; this file pins the three
sub-commands' happy paths plus the scan no-such-experiment error.
"""
from __future__ import annotations

import argparse

import pytest

from research_assistant import common
from research_assistant.migrate.cli_artifacts import (
    cmd_artifacts_list,
    cmd_artifacts_register,
    cmd_artifacts_scan,
)
from research_assistant.migrate.manifest import (
    external_artifacts_path,
    read_external_artifacts,
)


@pytest.fixture
def fake_experiments(tmp_path, monkeypatch):
    """Point EXPERIMENTS_DIR (and every captured reference) at a tmp dir."""
    fake = tmp_path / "experiments"
    fake.mkdir()
    monkeypatch.setattr(common.io, "EXPERIMENTS_DIR", fake)
    # manifest.py captures EXPERIMENTS_DIR at import time, used by
    # external_artifacts_path; rebind there too.
    from research_assistant.migrate import manifest as mf
    monkeypatch.setattr(mf, "EXPERIMENTS_DIR", fake)
    return fake


def _ns(**kw) -> argparse.Namespace:
    return argparse.Namespace(**kw)


def test_artifacts_list_empty_experiment_returns_zero(fake_experiments, capsys):
    (fake_experiments / "lora-eval").mkdir()
    rc = cmd_artifacts_list(_ns(slug="lora-eval"))
    out = capsys.readouterr().out
    assert rc == 0
    assert "(no external artifacts registered for lora-eval)" in out


def test_artifacts_register_writes_record_and_synthesizes_fetch_cmd(
    fake_experiments, capsys
):
    slug = "lora-eval"
    (fake_experiments / slug).mkdir()
    rc = cmd_artifacts_register(_ns(
        slug=slug, name="llama2-7b", path="repo/m1/base", glob="*",
        source="huggingface", repo="meta-llama/Llama-2-7b",
        revision=None, size="13GB", fetch_cmd=None,
    ))
    assert rc == 0
    ea = read_external_artifacts(external_artifacts_path(slug))
    assert len(ea.artifacts) == 1
    record = ea.artifacts[0]
    assert record.name == "llama2-7b"
    assert record.type == "huggingface"
    # _synthesize_fetch_cmd should have produced a non-empty command since
    # --fetch-cmd was None.
    assert record.fetch_cmd and "meta-llama/Llama-2-7b" in record.fetch_cmd


def test_artifacts_list_populated_shows_each_record(fake_experiments, capsys):
    slug = "lora-eval"
    (fake_experiments / slug).mkdir()
    # Register first to populate the file.
    cmd_artifacts_register(_ns(
        slug=slug, name="llama2-7b", path="repo/m1/base", glob="*",
        source="huggingface", repo="meta-llama/Llama-2-7b",
        revision="main", size="13GB", fetch_cmd=None,
    ))
    capsys.readouterr()  # drop register's stdout

    rc = cmd_artifacts_list(_ns(slug=slug))
    out = capsys.readouterr().out
    assert rc == 0
    assert "llama2-7b" in out
    assert "repo/m1/base" in out
    assert "huggingface" in out
    assert "meta-llama/Llama-2-7b" in out


def test_artifacts_scan_missing_slug_returns_2(fake_experiments, capsys):
    rc = cmd_artifacts_scan(_ns(slug="does-not-exist", threshold=1024))
    err = capsys.readouterr().err
    assert rc == 2
    assert "no such experiment" in err


def test_artifacts_scan_no_large_files_returns_zero(fake_experiments, capsys):
    slug = "lora-eval"
    exp = fake_experiments / slug
    exp.mkdir()
    # File well under threshold.
    (exp / "tiny.bin").write_bytes(b"x")
    rc = cmd_artifacts_scan(_ns(slug=slug, threshold=10_000))
    out = capsys.readouterr().out
    assert rc == 0
    assert "No unregistered files" in out


def test_artifacts_scan_finds_unregistered_large_file_and_can_skip(
    fake_experiments, capsys, monkeypatch
):
    """Drive _prompt to choice '3' so the test doesn't get stuck on input()."""
    slug = "lora-eval"
    exp = fake_experiments / slug
    (exp / "deep").mkdir(parents=True)
    big = exp / "deep" / "weights.bin"
    big.write_bytes(b"\x00" * 2048)  # 2 KiB

    # Stub _prompt to "3" (skip) so the scan loop completes without
    # writing a record or waiting for stdin.
    import research_assistant.migrate.cli as cli_mod
    monkeypatch.setattr(cli_mod, "_prompt", lambda *_a, **_k: "3")

    rc = cmd_artifacts_scan(_ns(slug=slug, threshold=1024))
    out = capsys.readouterr().out
    assert rc == 0
    assert "Found 1 unregistered file" in out
    # Nothing got registered (user chose skip).
    ea = read_external_artifacts(external_artifacts_path(slug))
    assert ea.artifacts == []
