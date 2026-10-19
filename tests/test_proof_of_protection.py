"""End to end, through the CLI: an audit finds a gap, a strengthened test is written in the candidate workspace, and
qualification proves what it now protects — the same deliberate break and the same mutants of a native tool, executed
on the baseline and on the candidate. The project is never changed. Needs an interpreter with pytest and Cosmic Ray
(ASSERTIVA_MUTATION_PYTHON); with ASSERTIVA_REQUIRE_MUTATION=1 a missing one fails instead of skipping.
"""

from __future__ import annotations

import json
import os
import shutil
import subprocess
from pathlib import Path

import pytest

from assertiva import cli
from assertiva.workspace import tree_fingerprint

pytestmark = pytest.mark.integration

DEMO = Path(__file__).parent / "fixtures" / "protection-demo"


def _python() -> str:
    python = os.environ.get("ASSERTIVA_MUTATION_PYTHON")
    ok = bool(python) and subprocess.run([python, "-c", "import cosmic_ray, pytest"], capture_output=True).returncode == 0
    if not ok:
        reason = "needs ASSERTIVA_MUTATION_PYTHON: an interpreter with pytest and cosmic-ray installed"
        if os.environ.get("ASSERTIVA_REQUIRE_MUTATION"):
            pytest.fail(reason)
        pytest.skip(reason)
    return python


def _run(capsys, *args) -> dict:
    capsys.readouterr()
    cli.main([*args, "--output", "json"])
    return json.loads(capsys.readouterr().out)


def test_a_found_gap_a_strengthened_test_and_the_protection_it_adds(tmp_path, capsys):
    python = _python()
    root = tmp_path / "project"
    shutil.copytree(DEMO, root, ignore=shutil.ignore_patterns("strengthened", "negative-controls.json", "README.md"))
    before = tree_fingerprint(root)

    # 1. audit: the weak oracle is found, and the native tool shows what the suite misses on this state
    audit = _run(capsys, "audit", str(root), "--execute", "--python", python, "--mutate", "pricing.py")
    weak = [f for f in audit["findings"] if f["code"].startswith("WEAK_ORACLE")]
    assert any("test_member_gets_a_discount" in json.dumps(f["evidence"]) for f in weak)
    [run] = audit["states"]["current"]["mutation"]
    assert run["error"] is None and run["matches_state"] is True and run["counts"].get("SURVIVED", 0) > 0

    # 2. improve: the strengthened test is written in the candidate workspace, never in the project
    workspace = Path(_run(capsys, "improve", str(root), "--python", python)["candidate_workspace"])
    shutil.copy(DEMO / "strengthened" / "test_pricing.py", workspace / "tests" / "test_pricing.py")

    # 3. qualification: the same break and the same mutants on both states
    report = _run(capsys, "improve", str(root), "--python", python, "--mutate", "pricing.py",
                  "--negative-controls", str(DEMO / "negative-controls.json"))
    protection = report["candidate_qualification"]["protection"]
    gained = {(e["kind"], e["id"]): e for e in protection["gained"]}
    assert ("negative_control", "threshold-exclusive") in gained
    assert "test_the_threshold_is_inclusive" in gained[("negative_control", "threshold-exclusive")]["detected_by"]
    assert sum(kind == "mutant" for kind, _ in gained) >= 10 and protection["lost"] == []
    assert not [e for e in protection["still_undetected"] if e["kind"] == "mutant"]
    checks = {c["check"]: c for s in report["candidate_qualification"]["stages"] for c in s["checks"]}
    assert checks["MUTATION_OR_NEGATIVE_CONTROLS"]["status"] == "PASS"
    assert "protection gained" in checks["MUTATION_OR_NEGATIVE_CONTROLS"]["summary"]
    from assertiva.report_html import render_html

    page = Path(report["report_path"]).read_text(encoding="utf-8")
    assert 'id="protection"' in page and "missed → detected" in page and "test_the_threshold_is_inclusive" in page
    assert "Proteção que o candidato adiciona" in render_html(report, lang="pt-BR")

    cli.main(["improve", str(root), "--discard"])
    assert tree_fingerprint(root) == before  # nothing was applied: approval is the human's


def test_a_candidate_that_removes_protection_fails_with_what_it_lost(tmp_path, capsys):
    python = _python()
    root = tmp_path / "project"
    shutil.copytree(DEMO, root, ignore=shutil.ignore_patterns("strengthened", "negative-controls.json", "README.md"))
    workspace = Path(_run(capsys, "improve", str(root), "--python", python)["candidate_workspace"])
    # the candidate keeps only the existence check: the non-member test that detected some mutants is gone
    (workspace / "tests" / "test_pricing.py").write_text(
        "from pricing import discount_cents\n\n\ndef test_member_gets_a_discount():\n    assert discount_cents(15000, True) is not None\n",
        encoding="utf-8")
    report = _run(capsys, "improve", str(root), "--python", python, "--mutate", "pricing.py")
    protection = report["candidate_qualification"]["protection"]
    assert protection["lost"] and protection["gained"] == []
    checks = {c["check"]: c for s in report["candidate_qualification"]["stages"] for c in s["checks"]}
    assert checks["MUTATION_OR_NEGATIVE_CONTROLS"]["status"] == "FAIL"
    assert "PROTECTION_LOST" in checks["MUTATION_OR_NEGATIVE_CONTROLS"]["summary"]
    cli.main(["improve", str(root), "--discard"])
