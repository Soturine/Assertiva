"""Protection evidence cannot be asserted into PROVEN_IN_SCOPE (v1.1 final addendum, CP-FINAL-A).

Reproduced on 4b3a2db before the fix: a NEGATIVE_CONTROL with invented prose, `"detected": "false"` (a string) and a
MUTANT described in prose each made a behavior PROVEN_IN_SCOPE with fault sensitivity DEMONSTRATED, and an
ENGINE_MUTATION claim was accepted when the named test had killed *any* mutant. Now: `detected` is a strict boolean;
an engine mutation claim names the specific mutant and its killers; a negative control is VERIFIED only through an
improve report (under an evidence root, unchanged since cited) that records this control as protection gained by
these tests, for a tree equal to that run's baseline plus its candidate changes. Anything else stays the agent's
report: kept, but the mechanical status is capped at OBSERVED_PASS."""

import copy
import hashlib
import json
import shutil
import sys
from pathlib import Path

import pytest

from assertiva import cli
from assertiva.assessment import AssessmentError, apply_assessment
from assertiva.workspace import capture_baseline, entry_digest
from conftest import commit_all, git, write

DEMO = Path(__file__).resolve().parents[1] / "examples" / "document-assurance" / "warehouse"
STRONG = "tests/test_transfer_approval.py::test_large_transfer_without_approval_is_rejected"
NEW_TEST = ("from transfer import Store, handle_transfer\n\n\n"
            "def test_large_transfer_without_approval_is_rejected():\n"
            "    store, events = Store({('A', 'bolt'): 500}), []\n"
            "    r = handle_transfer({'actor': {'permissions': ['stock:transfer']}, 'item': 'bolt', 'qty': 101, 'from': 'A', 'to': 'B'}, store, events)\n"
            "    assert (r.status, r.body, store.level('A', 'bolt'), events) == (409, {'code': 'APPROVAL_REQUIRED'}, 500, [])\n")


@pytest.fixture
def bound(tmp_path, assertiva_home, capsys):
    """(project, report, improve report path, its sha256): a tree that is an improve baseline plus its candidate test."""
    root = tmp_path / "warehouse"
    shutil.copytree(DEMO, root)
    commit_all(root)
    baseline = capture_baseline(root)
    write(root / "tests" / "test_transfer_approval.py", NEW_TEST)
    git(root, "add", "-A")
    git(root, "-c", "commit.gpgsign=false", "commit", "-q", "-m", "candidate")
    improve = {"workflow": "improve", "project": {"baseline_digest": baseline.digest},
               "change_set": {"changes": [{"change_id": "tests/test_transfer_approval.py", "path": "tests/test_transfer_approval.py",
                                           "original_fingerprint": None,
                                           "candidate_fingerprint": entry_digest(root, "tests/test_transfer_approval.py")}]},
               "candidate_qualification": {"protection": {"gained": [
                   {"kind": "negative_control", "id": "drop-approval", "detected_by": STRONG, "attribution": "TEST"}]}}}
    path = assertiva_home / "reports" / "improve.json"
    write(path, json.dumps(improve))
    assert cli.main(["audit", str(root), "--execute", "--python", sys.executable, "--output", "json"]) == 0
    report = json.loads(capsys.readouterr().out)
    return root, report, path, hashlib.sha256(path.read_bytes()).hexdigest()


def _assess(report, protection, tests=None):
    behavior = {"id": "BHV-approval", "title": "Above 100 needs approval", "authority": "OBSERVED_BEHAVIOR",
                "slice": {"expected": "409 APPROVAL_REQUIRED"},
                "tests": tests or [{"test": STRONG, "relation": "validates", "oracle": "STRONG"}],
                "protection": protection, "status": "PROVEN_IN_SCOPE", "rationale": "Read the test and the rule."}
    return {"run_id": report["run_id"], "summary": "s", "behaviors": [behavior]}


def _control(path=None, sha=None, **over):
    base = {"kind": "NEGATIVE_CONTROL", "ref": "drop-approval", "detected": True, "detected_by": [STRONG],
            "evidence": ["improve run on the baseline"]}
    if path:
        base["improve_report"] = {"path": str(path), "sha256": sha}
    base.update(over)
    return base


def _behavior(root, report, protection, tests=None):
    return apply_assessment(report, _assess(report, protection, tests), root)["context"]["behaviors"][0]


def test_a_control_bound_to_its_improve_report_proves_protection(bound):
    root, report, path, sha = bound
    b = _behavior(root, report, [_control(path, sha)])
    assert b["status"] == "PROVEN_IN_SCOPE" and b["dimensions"]["fault_sensitivity"] == "DEMONSTRATED"
    assert b["protection"][0]["basis"] == "IMPROVE_REPORT_VERIFIED" and "status_limited_by" not in b


def test_invented_prose_or_an_own_mutant_is_kept_but_never_proves(bound):
    root, report, _, _ = bound
    for proof in (_control(evidence=["trust me"]), {**_control(), "kind": "MUTANT", "ref": "some mutant"}):
        b = _behavior(root, report, [proof])
        assert (b["claimed_status"], b["status"]) == ("PROVEN_IN_SCOPE", "OBSERVED_PASS")
        assert b["dimensions"]["fault_sensitivity"] == "AGENT_REPORTED" and b["status_limited_by"]
        assert b["protection"][0]["basis"] == "AGENT_REPORTED"


def test_detected_is_a_strict_boolean(bound):
    root, report, path, sha = bound
    for value in ("false", "true", 1, None):
        with pytest.raises(AssessmentError, match="JSON boolean"):
            _behavior(root, report, [_control(path, sha, detected=value)])


def test_a_wrong_control_wrong_test_or_other_tree_does_not_verify(bound):
    root, report, path, sha = bound
    assert _behavior(root, report, [_control(path, sha, ref="no-such-control")])["status"] == "OBSERVED_PASS"
    other = "tests/test_transfer.py::test_transfer_succeeds"
    tests = [{"test": STRONG, "relation": "validates", "oracle": "STRONG"}, {"test": other, "relation": "validates", "oracle": "STRONG"}]
    b = _behavior(root, report, [_control(path, sha, detected_by=[other])], tests)
    assert b["status"] == "OBSERVED_PASS" and "other detecting tests" in b["protection"][0]["verification"]
    write(root / "transfer.py", (root / "transfer.py").read_text(encoding="utf-8") + "\n# edited after the improve run\n")
    git(root, "-c", "commit.gpgsign=false", "commit", "-qam", "drift")
    drifted = copy.deepcopy(report)
    drifted["project"]["digest"] = capture_baseline(root).digest
    b = _behavior(root, drifted, [_control(path, sha)])
    assert b["status"] == "OBSERVED_PASS" and "not the improve run's baseline" in b["protection"][0]["verification"]


def test_a_tampered_or_unauthorized_improve_report_is_refused(bound, tmp_path):
    root, report, path, sha = bound
    with pytest.raises(AssessmentError, match="no longer has the declared SHA-256"):
        _behavior(root, report, [_control(path, "0" * 64)])
    outside = tmp_path / "elsewhere" / "improve.json"
    write(outside, path.read_text(encoding="utf-8"))
    with pytest.raises(AssessmentError, match="outside the evidence roots"):
        _behavior(root, report, [_control(outside, sha)])


def _with_mutation(report, provenance="ENGINE_EXECUTED", matches=True):
    out = copy.deepcopy(report)
    out["states"]["current"]["mutation"] = [{"provenance": provenance, "matches_state": matches, "detections": [
        {"mutant_id": "m1", "mutant": "transfer.py:41 qty > 100 -> qty >= 100", "status": "KILLED", "killed_by": [STRONG]},
        {"mutant_id": "m2", "mutant": "transfer.py:45 level < qty -> level <= qty", "status": "KILLED",
         "killed_by": ["tests/test_transfer.py::test_transfer_succeeds"]}]}]
    return out


def test_an_engine_mutation_claim_names_the_mutant_and_its_killer(bound):
    root, report, _, _ = bound
    mutated = _with_mutation(report)
    ok = _behavior(root, mutated, [{"kind": "ENGINE_MUTATION", "ref": "m1", "detected": True, "detected_by": [STRONG]}])
    assert ok["status"] == "PROVEN_IN_SCOPE" and ok["protection"][0]["basis"] == "ENGINE_VERIFIED"
    with pytest.raises(AssessmentError, match="was not detected by"):  # the test killed m1, not m2
        _behavior(root, mutated, [{"kind": "ENGINE_MUTATION", "ref": "m2", "detected": True, "detected_by": [STRONG]}])
    with pytest.raises(AssessmentError, match="is not a mutant"):
        _behavior(root, mutated, [{"kind": "ENGINE_MUTATION", "ref": "m9", "detected": True, "detected_by": [STRONG]}])
    for imported in (_with_mutation(report, provenance="EXTERNAL_TOOL_REPORT"), _with_mutation(report, matches=False)):
        with pytest.raises(AssessmentError, match="is not a mutant"):  # imported or another state's report
            _behavior(root, imported, [{"kind": "ENGINE_MUTATION", "ref": "m1", "detected": True, "detected_by": [STRONG]}])
