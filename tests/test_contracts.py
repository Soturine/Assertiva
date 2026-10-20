"""Consumer-driven contracts. The fixtures are real: pact-python 4.1.0 (Pact Rust FFI 0.5.10) wrote the contracts from
consumer tests and verified them against small local providers (tests/fixtures/contracts/generate*.py): one correct,
one answering a string where the consumer expects an integer, an empty contract, and the failing interaction marked
pending. Two of those runs report success without verifying everything; the evidence must say so."""

from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

from assertiva import cli
from assertiva.adapters.contracts import findings, load_contract_evidence

FIXTURES = Path(__file__).parent / "fixtures" / "contracts"


def _load(name):
    return load_contract_evidence(FIXTURES / name)


def test_a_verification_that_checked_every_interaction_is_verified():
    item = _load("verification-verified.json")
    assert item["status"] == "VERIFIED" and item["verified"] == item["interactions"] == 2 and findings(item) == []


def test_a_mismatch_fails_with_what_differs():
    item = _load("verification-broken.json")
    [finding] = findings(item)
    assert item["status"] == "FAILED" and finding.code == "CONTRACT_VERIFICATION_FAILED" and finding.severity == "high"
    assert "Expected '1500' (String) to be an integer" in " ".join(finding.evidence["mismatches"])


def test_green_runs_that_verified_nothing_or_only_pending_are_not_verified():
    empty, pending = _load("verification-empty.json"), _load("verification-pending.json")
    assert empty["tool_result"] is True and empty["status"] == "EMPTY"  # the tool says success
    assert pending["tool_result"] is True and pending["status"] == "PENDING_FAILURES" and pending["verified"] == 1
    assert [f.code for f in findings(empty) + findings(pending)] == ["CONTRACT_EMPTY", "CONTRACT_PENDING_FAILURES"]


def test_a_contract_file_alone_proves_nothing_about_the_provider():
    contract, empty = _load("pacts/orders-web-pricing-api.json"), _load("pacts/reports-job-pricing-api.json")
    assert contract["status"] == "NOT_VERIFIED" and contract["interactions"] == 2
    assert contract["provider_states"] == ["a member order of 150.00", "no order 999"] and contract["specification"] == "4.0"
    assert empty["status"] == "EMPTY"


def test_other_json_is_refused_with_a_reason(tmp_path):
    (tmp_path / "x.json").write_text('{"results": {}}', encoding="utf-8")
    assert "neither a Pact contract" in load_contract_evidence(tmp_path / "x.json")["error"]


@pytest.mark.integration
def test_audit_reports_contract_evidence(calc_project, tmp_path, capsys):
    capsys.readouterr()
    cli.main(["audit", str(calc_project), "--report-dir", str(tmp_path / "r"), "--python", sys.executable, "--output", "json",
              *[arg for name in ("verification-verified.json", "verification-empty.json", "verification-pending.json")
                for arg in ("--contract", str(FIXTURES / name))]])
    report = json.loads(capsys.readouterr().out)
    assert [c["status"] for c in report["contracts"]] == ["VERIFIED", "EMPTY", "PENDING_FAILURES"]
    assert {f["code"] for f in report["findings"]} >= {"CONTRACT_EMPTY", "CONTRACT_PENDING_FAILURES"}
    assert 'id="contracts"' in (tmp_path / "r" / "audit.html").read_text(encoding="utf-8")
