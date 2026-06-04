"""Tests for `research_assistant.papers.verification` — /paper verify ledger."""
from __future__ import annotations

import pytest

from research_assistant.papers.placeholders import debt_summary
from research_assistant.papers.verification import (
    MAX_VERIFY_ROUNDS,
    ClaimEvidence,
    DebtEntry,
    VerificationReport,
    collect_claims,
    compute_verdict,
    finalize_verdict,
    naked_claims,
    read_latest_reports,
    report_from_markdown,
    report_to_markdown,
    verify_debt_counts,
    write_verification_report,
)


def _report(section="method", date="2026-06-04", round=1, score=7, debts=None, claims=None):
    return VerificationReport(
        section=section,
        date=date,
        round=round,
        score=score,
        debts=debts or {},
        claims=claims or [],
    )


# ---------- claim model ----------


def test_claim_is_naked():
    assert ClaimEvidence(claim="x").is_naked is True
    assert ClaimEvidence(claim="x", evidence="cite:vaswani2017").is_naked is False
    assert ClaimEvidence(claim="x", verified=True).is_naked is False


# ---------- verdict ----------


def test_verdict_passed_when_no_hard_debt():
    debts = {"figure": "open"}  # soft only
    assert compute_verdict(debts, 1) == ("passed", False)


def test_verdict_failed_when_hard_open_below_cap():
    debts = {"evidence": "open"}
    assert compute_verdict(debts, 1) == ("failed", False)


def test_verdict_blocked_at_round_cap():
    debts = {"citation": "open"}
    verdict, unresolvable = compute_verdict(debts, MAX_VERIFY_ROUNDS)
    assert verdict == "blocked"
    assert unresolvable is True


def test_verdict_accepts_debt_entries():
    debts = {"prose": DebtEntry(status="open"), "figure": DebtEntry(status="closed")}
    assert compute_verdict(debts, 1) == ("failed", False)


def test_verdict_all_closed_passes():
    debts = {c: "closed" for c in ("citation", "evidence", "prose", "consistency")}
    assert compute_verdict(debts, 2) == ("passed", False)


def test_finalize_verdict_stamps_report():
    r = _report(debts={"evidence": DebtEntry(status="open")}, round=1)
    final = finalize_verdict(r)
    assert final.verdict == "failed"
    assert final.unresolvable is False
    # original untouched (model_copy)
    assert r.verdict == "failed"  # default; finalize returns a copy


def test_score_bounds_enforced():
    with pytest.raises(ValueError):
        _report(score=0)
    with pytest.raises(ValueError):
        _report(score=11)


# ---------- serialization round-trip ----------


def test_report_markdown_round_trip():
    r = finalize_verdict(
        _report(
            debts={
                "citation": DebtEntry(status="closed"),
                "consistency": DebtEntry(status="open", note="intro promises ≠ results"),
            },
            claims=[
                ClaimEvidence(claim="2x faster", evidence="exp:wl-1@v1.2", verified=True),
                ClaimEvidence(claim="best on ImageNet"),  # naked
            ],
        )
    )
    text = report_to_markdown(r)
    assert text.startswith("---\n")
    back = report_from_markdown(text)
    assert back.section == r.section
    assert back.verdict == r.verdict
    assert back.debts["consistency"].status == "open"
    assert back.debts["consistency"].note == "intro promises ≠ results"
    assert len(back.claims) == 2
    assert back.naked_claims()[0].claim == "best on ImageNet"
    # body carries the human-readable ledger + claim map
    assert "Debt ledger" in text
    assert "NAKED" in text


def test_report_from_markdown_requires_frontmatter():
    with pytest.raises(ValueError):
        report_from_markdown("no frontmatter here")


# ---------- persistence ----------


def test_write_report_finalizes_and_paths(tmp_path):
    r = _report(section="results", debts={"evidence": DebtEntry(status="open")})
    out = write_verification_report(tmp_path, r)
    assert out.parent.name == "reviews"
    assert out.name == "verify-results-2026-06-04.md"
    saved = report_from_markdown(out.read_text(encoding="utf-8"))
    assert saved.verdict == "failed"  # finalized on write


def test_write_report_collision_safe(tmp_path):
    r = _report(section="method")
    a = write_verification_report(tmp_path, r)
    b = write_verification_report(tmp_path, r)
    assert a.name == "verify-method-2026-06-04.md"
    assert b.name == "verify-method-2026-06-04-2.md"


def test_read_latest_reports_picks_highest_round(tmp_path):
    write_verification_report(
        tmp_path, _report(section="method", date="2026-06-01", round=1, score=5)
    )
    write_verification_report(
        tmp_path,
        _report(
            section="method", date="2026-06-04", round=2, score=8,
            debts={"prose": DebtEntry(status="closed")},
        ),
    )
    latest = read_latest_reports(tmp_path)
    assert set(latest) == {"method"}
    assert latest["method"].round == 2
    assert latest["method"].score == 8


def test_verify_debt_counts(tmp_path):
    write_verification_report(
        tmp_path,
        _report(
            section="method",
            debts={"prose": DebtEntry(status="open"), "consistency": DebtEntry(status="open")},
        ),
    )
    write_verification_report(
        tmp_path,
        _report(section="results", debts={"consistency": DebtEntry(status="open")}),
    )
    prose, consistency = verify_debt_counts(tmp_path)
    assert prose == 1          # only method
    assert consistency == 2    # method + results


def test_collect_and_naked_claims(tmp_path):
    write_verification_report(
        tmp_path,
        _report(
            section="intro",
            claims=[
                ClaimEvidence(claim="grounded", evidence="cite:x", verified=True),
                ClaimEvidence(claim="unbacked"),
            ],
        ),
    )
    assert len(collect_claims(tmp_path)) == 2
    nk = naked_claims(tmp_path)
    assert [c.claim for c in nk] == ["unbacked"]


def test_empty_dir_yields_nothing(tmp_path):
    assert read_latest_reports(tmp_path) == {}
    assert verify_debt_counts(tmp_path) == (0, 0)
    assert collect_claims(tmp_path) == []


# ---------- cross-module: debt_summary picks up verify debts ----------


def test_debt_summary_includes_prose_and_consistency(tmp_path):
    # No placeholders / cites, but a verify report with open prose + consistency.
    write_verification_report(
        tmp_path,
        _report(
            section="method",
            debts={
                "prose": DebtEntry(status="open"),
                "consistency": DebtEntry(status="open"),
            },
        ),
    )
    summary = debt_summary(tmp_path)
    assert summary.prose == 1
    assert summary.consistency == 1
    assert summary.total == 2
    line = summary.as_line()
    assert "1 prose" in line
    assert "1 consistency" in line
