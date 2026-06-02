"""Smoke tests for the outer CLI handlers (``cmd_export`` / ``cmd_import``).

These exercise CLI-layer guards the audit found untested. Deeper export/
import behavior is already covered by :mod:`tests.test_migrate_archive` and
:mod:`tests.test_migrate_merge`; this file only pins the easy CLI-edge
paths (missing archive, malformed-external-artifacts error path).
"""
from __future__ import annotations

import argparse

from research_assistant.migrate.cli import cmd_export, cmd_import


def _import_ns(**overrides) -> argparse.Namespace:
    base = dict(
        archive="/tmp/__definitely_does_not_exist__.zip",
        repo_root=None,
        dry_run=True,
        passphrase_env=None,
    )
    base.update(overrides)
    return argparse.Namespace(**base)


def _export_ns(**overrides) -> argparse.Namespace:
    base = dict(
        repo_root=None,
        out=None,
        include=None,
        threshold=10**12,  # 1 TB → no real file trips the unregistered guard
        non_interactive=True,
        dry_run=True,
        encrypt=False,
        passphrase_env=None,
    )
    base.update(overrides)
    return argparse.Namespace(**base)


def test_cmd_import_missing_archive_returns_2(capsys):
    rc = cmd_import(_import_ns(archive="/tmp/__nope_lucky_research__.zip"))
    err = capsys.readouterr().err
    assert rc == 2
    assert "archive not found" in err


def test_cmd_export_surfaces_scan_value_error_as_friendly_message(
    tmp_path, capsys, monkeypatch
):
    """When scan_repo raises ValueError (typically a malformed
    external-artifacts.md), cmd_export must return 2 and print the friendly
    "Fix the offending external-artifacts.md" hint — not a raw traceback."""
    import research_assistant.migrate.cli as cli_mod

    def fake_scan_repo(*_a, **_kw):
        raise ValueError("malformed external-artifacts.md in experiments/lora-eval")

    monkeypatch.setattr(cli_mod, "scan_repo", fake_scan_repo)
    rc = cmd_export(_export_ns(out=str(tmp_path / "out")))
    err = capsys.readouterr().err
    assert rc == 2
    assert "malformed external-artifacts.md" in err
    assert "Fix the offending external-artifacts.md" in err
