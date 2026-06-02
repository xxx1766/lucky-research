"""Tests for `_synthesize_fetch_cmd` in `research_assistant.migrate.cli`.

The function is private but it's the single source of truth for the
auto-rendered fetch command that ships in `external-artifacts.md`; covering
each branch keeps `/experiment artifacts register|scan` from silently
regressing into a useless placeholder.
"""
from __future__ import annotations

from research_assistant.migrate.cli import _synthesize_fetch_cmd


def test_huggingface_with_revision():
    out = _synthesize_fetch_cmd(
        "huggingface", "org/model", "abc123", "models/llama",
    )
    assert "huggingface-cli download org/model --revision abc123" in out
    assert "--local-dir <experiment>/models/llama" in out


def test_huggingface_without_revision_omits_arg():
    out = _synthesize_fetch_cmd("huggingface", "org/model", None, "models/llama")
    assert "--revision" not in out
    assert "huggingface-cli download org/model " in out


def test_http_renders_curl():
    out = _synthesize_fetch_cmd("http", "https://example.com/x.zip", None, "data/x")
    assert out == "curl -L -o <experiment>/data/x https://example.com/x.zip"


def test_git_lfs_renders_clone():
    out = _synthesize_fetch_cmd("git-lfs", "https://hf.co/org/repo", None, "ckpts/r")
    assert out == "git lfs clone https://hf.co/org/repo <experiment>/ckpts/r"


def test_s3_single_object():
    out = _synthesize_fetch_cmd(
        "s3", "s3://my-bucket/path/to/file.tar", None, "data/file.tar",
    )
    assert out == "aws s3 cp s3://my-bucket/path/to/file.tar <experiment>/data/file.tar"
    assert "--recursive" not in out


def test_s3_prefix_uses_recursive():
    out = _synthesize_fetch_cmd(
        "s3", "s3://my-bucket/dir/", None, "data/dir",
    )
    assert out == "aws s3 cp s3://my-bucket/dir/ <experiment>/data/dir --recursive"


def test_s3_revision_is_surfaced_as_comment():
    out = _synthesize_fetch_cmd(
        "s3", "s3://b/k", "checkpoint-2026-06-01", "data/k",
    )
    assert "# revision: checkpoint-2026-06-01" in out


def test_other_with_repo_emits_todo_with_repo_string():
    out = _synthesize_fetch_cmd("other", "ftp://internal/blob", None, "data/blob")
    assert out.startswith("# TODO: fetch ftp://internal/blob into <experiment>/data/blob")


def test_other_with_revision_appends_comment():
    out = _synthesize_fetch_cmd("other", "ftp://internal/blob", "v3", "data/blob")
    assert "# revision: v3" in out


def test_no_repo_falls_through_to_placeholder():
    # None of the branches fire when --repo is omitted; the dest-only
    # placeholder reminds the user where to plug the command in.
    out = _synthesize_fetch_cmd("huggingface", None, None, "data/x")
    assert "fill in manually" in out
    out = _synthesize_fetch_cmd("s3", None, None, "data/x")
    assert "fill in manually" in out
    out = _synthesize_fetch_cmd("other", None, None, "data/x")
    assert "fill in manually" in out


def test_unknown_source_falls_through_to_placeholder():
    out = _synthesize_fetch_cmd("unknown-source", "anything", None, "data/x")
    assert "fill in manually" in out
