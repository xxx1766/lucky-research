"""Tests for migrate.reindex — walks disk truth sources, emits memory_store
payloads as a generator. Sources are scattered across mentor/, experiments/,
ideas/ so the fixture has to point each module's DIR constant at a fresh
``tmp_path``.
"""
from __future__ import annotations

from pathlib import Path

import pytest

from research_assistant import common
from research_assistant import experiments as exp_pkg
from research_assistant.ideas import registry as ideas_registry
from research_assistant.mentor import boss_profile, past_work
from research_assistant.migrate.reindex import (
    cmd_reindex,
    count_by_namespace,
    iter_reindex_payloads,
)


@pytest.fixture
def isolated_repo(tmp_path, monkeypatch):
    """Redirect every truth-source DIR constant into tmp_path/."""
    inputs = tmp_path / "inputs"
    outputs = tmp_path / "outputs"
    inputs.mkdir()
    outputs.mkdir()

    fakes = {
        "PAST_WORK_DIR": inputs / "past-work",
        "EXPERIMENTS_DIR": outputs / "experiments",
        "BOSS_PROFILE_DIR": inputs / "boss-profile",
        "BOSS_MEETINGS_DIR": inputs / "boss-profile" / "meetings",
        "BOSS_REPORTS_DIR": inputs / "boss-profile" / "reports",
        "BOSS_REHEARSALS_DIR": inputs / "boss-profile" / "rehearsals",
        "IDEA_CHECKS_DIR": outputs / "idea-checks",
        "RESEARCH_NOTES_DIR": outputs / "research-notes",
    }
    for path in fakes.values():
        path.mkdir(parents=True, exist_ok=True)

    # Patch common.io (canonical) AND every module that captured the constant
    # at import time.
    for name, p in fakes.items():
        monkeypatch.setattr(common.io, name, p)
    monkeypatch.setattr(past_work, "PAST_WORK_DIR", fakes["PAST_WORK_DIR"])
    monkeypatch.setattr(exp_pkg, "EXPERIMENTS_DIR", fakes["EXPERIMENTS_DIR"])
    monkeypatch.setattr(boss_profile, "BOSS_MEETINGS_DIR", fakes["BOSS_MEETINGS_DIR"])
    monkeypatch.setattr(boss_profile, "BOSS_REPORTS_DIR", fakes["BOSS_REPORTS_DIR"])
    monkeypatch.setattr(
        boss_profile, "BOSS_REHEARSALS_DIR", fakes["BOSS_REHEARSALS_DIR"]
    )
    monkeypatch.setattr(ideas_registry, "IDEA_CHECKS_DIR", fakes["IDEA_CHECKS_DIR"])
    return fakes


# ---------- empty repo ----------


def test_iter_empty_returns_no_payloads(isolated_repo):
    assert list(iter_reindex_payloads()) == []
    assert count_by_namespace() == {}


# ---------- past-work ----------


def _write_past_work(root: Path, slug: str, *, title: str, year: int, status: str) -> None:
    (root / f"{slug}.md").write_text(
        "---\n"
        f"slug: {slug}\n"
        f'title: "{title}"\n'
        f"year: {year}\n"
        "venue: internal\n"
        f"status: {status}\n"
        "tags: [lora]\n"
        "links: []\n"
        "---\n\n# X\n",
        encoding="utf-8",
    )


def test_past_work_payload_shape(isolated_repo):
    _write_past_work(isolated_repo["PAST_WORK_DIR"], "lora",
                     title="LoRA notes", year=2026, status="published")
    payloads = [p for p in iter_reindex_payloads() if p["namespace"] == "project/past-work"]
    assert len(payloads) == 1
    p = payloads[0]
    assert p["key"] == "lora"
    assert "LoRA notes" in p["value"]
    assert "Year 2026" in p["value"]
    assert "Tags: lora" in p["value"]
    assert p["metadata"]["kind"] == "past_work"
    assert p["metadata"]["slug"] == "lora"


def test_past_work_malformed_entry_is_skipped(isolated_repo):
    pw = isolated_repo["PAST_WORK_DIR"]
    _write_past_work(pw, "good", title="OK", year=2026, status="published")
    (pw / "broken.md").write_text("---\nNOT VALID YAML ::: }}}\n---\n", encoding="utf-8")
    keys = [p["key"] for p in iter_reindex_payloads()
            if p["namespace"] == "project/past-work"]
    assert keys == ["good"]


# ---------- experiments ----------


def _write_experiment_manifest(root: Path, slug: str, *, papers: list[str] = ()) -> None:
    d = root / slug
    d.mkdir(parents=True, exist_ok=True)
    papers_yaml = "\n".join(f"  - {p}" for p in papers) if papers else " []"
    (d / "manifest.md").write_text(
        "---\n"
        f"slug: {slug}\n"
        f"title: {slug.replace('-', ' ').title()}\n"
        "created_at: 2026-05-01\n"
        "repo:\n  url: u\n  branch: main\n"
        f"papers:{(chr(10) + papers_yaml) if papers else ' []'}\n"
        "status: active\n"
        "---\nbody\n",
        encoding="utf-8",
    )


def _write_experiment_version(root: Path, slug: str, version: str) -> None:
    vd = root / slug / "versions"
    vd.mkdir(parents=True, exist_ok=True)
    (vd / f"{version}.md").write_text(
        f"---\nversion: {version}\ndescription: x\nstatus: completed\n"
        "metrics: {acc: 0.83}\n---\nbody\n",
        encoding="utf-8",
    )


def test_experiment_manifest_and_versions_yielded(isolated_repo):
    er = isolated_repo["EXPERIMENTS_DIR"]
    _write_experiment_manifest(er, "lora-eval", papers=["OSDI/cool"])
    _write_experiment_version(er, "lora-eval", "v1.0")
    _write_experiment_version(er, "lora-eval", "v1.1")
    payloads = list(iter_reindex_payloads())
    namespaces = sorted({p["namespace"] for p in payloads})
    assert "project/experiments" in namespaces
    # per-version namespace is per-slug
    assert any(ns.startswith("project/experiments/lora-eval/versions") for ns in namespaces)
    # 1 manifest + 2 versions
    assert sum(1 for p in payloads if p["namespace"] == "project/experiments") == 1
    version_keys = sorted(
        p["key"] for p in payloads
        if p["namespace"] == "project/experiments/lora-eval/versions"
    )
    assert version_keys == ["v1.0", "v1.1"]


# ---------- ideas ----------


def _write_idea(root: Path, slug: str, *, statement: str) -> None:
    d = root / slug
    d.mkdir(parents=True, exist_ok=True)
    # ideas.registry uses `idea.md`, not manifest.md (see list_ideas).
    (d / "idea.md").write_text(
        "---\n"
        f"slug: {slug}\n"
        f"statement: {statement}\n"
        "created: 2026-05-01\n"
        "updated: 2026-05-01\n"
        "area_tags: [moe, efficient-attention]\n"
        "status: captured\n"
        "---\nbody\n",
        encoding="utf-8",
    )


def test_idea_payload(isolated_repo):
    _write_idea(isolated_repo["IDEA_CHECKS_DIR"], "sparse-moe",
                statement="MoE with sparser routing.")
    payloads = [p for p in iter_reindex_payloads() if p["namespace"] == "ideas"]
    assert len(payloads) == 1
    assert payloads[0]["key"] == "sparse-moe"
    assert "MoE with sparser routing" in payloads[0]["value"]
    assert "moe" in payloads[0]["value"]   # area_tags rendered into search text
    assert payloads[0]["metadata"]["slug"] == "sparse-moe"


# ---------- boss ----------


def test_boss_profile_and_meeting_payloads(isolated_repo):
    bd = isolated_repo["BOSS_PROFILE_DIR"]
    (bd / "profile.md").write_text(
        "---\n"
        "name: Prof. X\n"
        "role: PI\n"
        "research_interests: [systems, llm]\n"
        "hot_buttons: [scalability]\n"
        "---\nbody\n",
        encoding="utf-8",
    )
    md = isolated_repo["BOSS_MEETINGS_DIR"]
    (md / "2026-05-12.md").write_text(
        "---\n"
        "date: 2026-05-12\n"
        "topic: Q2 progress\n"
        "mode: '1:1'\n"
        "feedback: keep at it\n"
        "action_items: [write more code]\n"
        "---\nbody\n",
        encoding="utf-8",
    )
    profile = next(p for p in iter_reindex_payloads() if p["namespace"] == "project/boss")
    assert profile["key"] == "profile"
    assert "Prof. X" in profile["value"]
    assert "scalability" in profile["value"]
    meeting = next(
        p for p in iter_reindex_payloads() if p["namespace"] == "project/boss/meetings"
    )
    assert meeting["key"] == "2026-05-12"
    assert "Q2 progress" in meeting["value"]
    assert "keep at it" in meeting["value"]


# ---------- namespace filter ----------


def test_namespace_filter_scopes_correctly(isolated_repo):
    _write_past_work(isolated_repo["PAST_WORK_DIR"], "x",
                     title="X", year=2026, status="published")
    _write_idea(isolated_repo["IDEA_CHECKS_DIR"], "y", statement="Y.")
    _write_experiment_manifest(isolated_repo["EXPERIMENTS_DIR"], "z")

    pw_only = list(iter_reindex_payloads("project/past-work"))
    assert [p["key"] for p in pw_only] == ["x"]
    exp_only = list(iter_reindex_payloads("project/experiments"))
    assert [p["key"] for p in exp_only] == ["z"]
    ideas_only = list(iter_reindex_payloads("ideas"))
    assert [p["key"] for p in ideas_only] == ["y"]


def test_namespace_filter_matches_subnamespaces(isolated_repo):
    """`project/experiments` should include both the per-experiment payload
    and the per-version payloads (sub-namespace)."""
    er = isolated_repo["EXPERIMENTS_DIR"]
    _write_experiment_manifest(er, "lora")
    _write_experiment_version(er, "lora", "v1.0")
    out = list(iter_reindex_payloads("project/experiments"))
    assert len(out) == 2
    namespaces = {p["namespace"] for p in out}
    assert namespaces == {"project/experiments", "project/experiments/lora/versions"}


# ---------- count_by_namespace ----------


def test_count_by_namespace_aggregates_correctly(isolated_repo):
    pw = isolated_repo["PAST_WORK_DIR"]
    _write_past_work(pw, "a", title="A", year=2026, status="published")
    _write_past_work(pw, "b", title="B", year=2026, status="published")
    _write_idea(isolated_repo["IDEA_CHECKS_DIR"], "c", statement="C.")
    counts = count_by_namespace()
    assert counts["project/past-work"] == 2
    assert counts["ideas"] == 1


# ---------- cmd_reindex CLI handler ----------


import argparse  # noqa: E402  (intentional: keep CLI tests adjacent)
import json  # noqa: E402


def _reindex_ns(*, summary: bool, namespace: str | None = None) -> argparse.Namespace:
    return argparse.Namespace(summary=summary, namespace=namespace)


def test_cmd_reindex_summary_on_empty_repo_reports_zero(isolated_repo, capsys):
    rc = cmd_reindex(_reindex_ns(summary=True))
    out = capsys.readouterr().out
    assert rc == 0
    assert "(no reindexable payloads found)" in out


def test_cmd_reindex_summary_groups_counts_by_namespace(isolated_repo, capsys):
    _write_past_work(
        isolated_repo["PAST_WORK_DIR"], "a", title="A", year=2026, status="published",
    )
    _write_past_work(
        isolated_repo["PAST_WORK_DIR"], "b", title="B", year=2026, status="published",
    )
    _write_idea(isolated_repo["IDEA_CHECKS_DIR"], "c", statement="C.")

    rc = cmd_reindex(_reindex_ns(summary=True))
    out = capsys.readouterr().out
    assert rc == 0
    assert "project/past-work" in out
    assert "ideas" in out
    # Total row + body — at minimum the past-work count "2" appears on its row.
    assert "2" in out and "1" in out
    assert "total" in out


def test_cmd_reindex_default_mode_emits_one_json_per_payload(isolated_repo, capsys):
    _write_past_work(
        isolated_repo["PAST_WORK_DIR"], "a", title="A", year=2026, status="published",
    )
    _write_idea(isolated_repo["IDEA_CHECKS_DIR"], "b", statement="B.")

    rc = cmd_reindex(_reindex_ns(summary=False))
    out = capsys.readouterr().out
    assert rc == 0
    lines = [ln for ln in out.splitlines() if ln.strip()]
    assert len(lines) == 2
    payloads = [json.loads(ln) for ln in lines]
    namespaces = {p["namespace"] for p in payloads}
    assert namespaces == {"project/past-work", "ideas"}


def test_cmd_reindex_namespace_filter_scopes_jsonl(isolated_repo, capsys):
    _write_past_work(
        isolated_repo["PAST_WORK_DIR"], "a", title="A", year=2026, status="published",
    )
    _write_idea(isolated_repo["IDEA_CHECKS_DIR"], "b", statement="B.")

    rc = cmd_reindex(_reindex_ns(summary=False, namespace="ideas"))
    out = capsys.readouterr().out
    assert rc == 0
    lines = [ln for ln in out.splitlines() if ln.strip()]
    assert len(lines) == 1
    payload = json.loads(lines[0])
    assert payload["namespace"] == "ideas"
    assert payload["key"] == "b"
