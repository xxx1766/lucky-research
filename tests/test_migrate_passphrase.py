"""Tests for `_resolve_passphrase` in `research_assistant.migrate.cli`.

The helper is private but it's the single chokepoint for passphrase sourcing
(prompt vs env var vs no-encrypt), and getting it wrong silently means a CI
script ships a plaintext archive. Worth a dedicated suite.
"""
from __future__ import annotations

import pytest

from research_assistant.migrate.cli import _resolve_passphrase


def test_no_encrypt_no_env_returns_none():
    assert _resolve_passphrase(encrypt=False, env_var=None, confirm=False) is None


def test_env_var_returns_bytes(monkeypatch):
    monkeypatch.setenv("LR_MIGRATE_PASS", "letmein")
    out = _resolve_passphrase(encrypt=False, env_var="LR_MIGRATE_PASS", confirm=True)
    assert out == b"letmein"


def test_env_var_set_overrides_encrypt_flag(monkeypatch):
    # encrypt=True together with env_var means "non-interactive" — env wins.
    monkeypatch.setenv("LR_MIGRATE_PASS", "hunter2")
    out = _resolve_passphrase(encrypt=True, env_var="LR_MIGRATE_PASS", confirm=True)
    assert out == b"hunter2"


def test_empty_env_var_is_an_error(monkeypatch):
    monkeypatch.setenv("LR_MIGRATE_PASS", "")
    with pytest.raises(RuntimeError, match="empty"):
        _resolve_passphrase(encrypt=False, env_var="LR_MIGRATE_PASS", confirm=False)


def test_unset_env_var_is_an_error(monkeypatch):
    monkeypatch.delenv("LR_MIGRATE_PASS", raising=False)
    with pytest.raises(RuntimeError, match="empty"):
        _resolve_passphrase(encrypt=False, env_var="LR_MIGRATE_PASS", confirm=False)


def test_encrypt_prompts_with_confirm_succeeds(monkeypatch):
    # Two reads, both "secret" → returns the bytes.
    queue = iter(["secret", "secret"])
    monkeypatch.setattr("getpass.getpass", lambda prompt="": next(queue))
    out = _resolve_passphrase(encrypt=True, env_var=None, confirm=True)
    assert out == b"secret"


def test_encrypt_prompts_without_confirm_succeeds(monkeypatch):
    # confirm=False (import path) — one read.
    queue = iter(["secret"])
    monkeypatch.setattr("getpass.getpass", lambda prompt="": next(queue))
    out = _resolve_passphrase(encrypt=True, env_var=None, confirm=False)
    assert out == b"secret"


def test_empty_prompted_passphrase_is_an_error(monkeypatch):
    monkeypatch.setattr("getpass.getpass", lambda prompt="": "")
    with pytest.raises(RuntimeError, match="empty"):
        _resolve_passphrase(encrypt=True, env_var=None, confirm=False)


def test_mismatched_confirm_loops_until_matched(monkeypatch, capsys):
    # First round: "a" vs "b" → mismatch, prints warning, loops.
    # Second round: "x" vs "x" → match.
    queue = iter(["a", "b", "x", "x"])
    monkeypatch.setattr("getpass.getpass", lambda prompt="": next(queue))
    out = _resolve_passphrase(encrypt=True, env_var=None, confirm=True)
    assert out == b"x"
    err = capsys.readouterr().err
    assert "did not match" in err
