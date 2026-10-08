"""`assertiva audit --run-check CHECK_ID`: the auditor reproduces a declared check (what CI runs) without touching the project.

Found by dogfooding: an agent that needed CI-equivalent evidence for a unittest suite (no native adapter) ran the
runner inside the project tree, because the audit offered no safe instrument for it. The engine now runs a named,
discovered check in a disposable copy under the read-only guard, with the same rules as improve's delivery checks."""

import json
import sys
from pathlib import Path

from assertiva import cli
from assertiva.report import render_html
from assertiva.workspace import tree_fingerprint
from conftest import write

_UNITTEST = ("import unittest\n\nfrom calc import add\n\n\nclass AddTests(unittest.TestCase):\n"
             "    def test_value(self):\n        self.assertEqual(add(2, 2), {expected})\n")
_CHECK = "gha:.github/workflows/ci.yml:test:1"


def _project(root: Path, expected: int = 4, extra_step: str = "") -> Path:
    write(root / "calc.py", "def add(a, b):\n    return a + b\n")
    write(root / "tests" / "__init__.py", "")
    write(root / "tests" / "test_calc.py", _UNITTEST.format(expected=expected))
    write(root / ".github" / "workflows" / "ci.yml",
          "on: push\njobs:\n  test:\n    runs-on: ubuntu-latest\n    steps:\n"
          "      - run: python -m unittest discover -s tests\n" + extra_step)
    return root


def _audit(root: Path, capsys, *args: str) -> tuple[int, dict | None, str]:
    code = cli.main(["audit", str(root), "--python", sys.executable, "--output", "json", *args])
    out, err = capsys.readouterr()
    return code, (json.loads(out) if code == 0 else None), err


def test_a_named_declared_check_runs_in_a_disposable_copy_and_is_reported(tmp_path, capsys):
    root = _project(tmp_path / "p")
    code, report, _ = _audit(root, capsys)
    assert [c["check_id"] for c in report["verification_surface"]] == [_CHECK]
    assert report["declared_checks"] == []  # discovered is not executed
    before = tree_fingerprint(root)
    code, report, _ = _audit(root, capsys, "--run-check", _CHECK)
    assert code == 0 and tree_fingerprint(root) == before
    assert not list(root.rglob("__pycache__"))  # nothing was run inside the project
    [check] = report["declared_checks"]
    assert check["check_id"] == _CHECK and check["status"] == "PASS" and check["kind"] == "TEST"
    assert any(o.startswith(f"declared check {_CHECK} reproduced in an isolated copy: PASS") for o in report["claim_boundary"]["observed"])
    assert "no tests were executed; test outcomes are UNKNOWN" not in report["claim_boundary"]["not_evidenced"]
    assert {"stage": f"check:{_CHECK}", "decision": "EXECUTED"}.items() <= report["execution_budget"]["decisions"][-1].items()
    # unittest has a native adapter: the CI command runs through it and yields per-test outcomes
    assert check["scope"].startswith("per-test outcomes") and check["execution"]["via"] == "unittest"
    [run] = report["states"]["current"]["runs"]
    assert run["adapter"] == "unittest" and run["outcomes"] == {"PASSED": 1}
    page = render_html(report)
    assert 'id="scope-tests"' in page and "Reproduced in a disposable copy" in page


def test_a_failing_declared_check_is_a_finding(tmp_path, capsys):
    root = _project(tmp_path / "p", expected=5)
    _, report, _ = _audit(root, capsys, "--run-check", _CHECK)
    assert report["declared_checks"][0]["status"] == "FAIL"
    finding = next(f for f in report["findings"] if f["code"] == "DECLARED_CHECK_FAILED")
    assert finding["severity"] == "high" and finding["evidence"]["check_id"] == _CHECK


def test_unknown_and_unreproducible_checks_are_refused_or_explained(tmp_path, capsys):
    root = _project(tmp_path / "p", extra_step="      - run: twine upload dist/*\n")
    code, _, err = _audit(root, capsys, "--run-check", "gha:nope")
    assert code == 2 and "no discovered check" in err
    deploy = "gha:.github/workflows/ci.yml:test:2"
    _, report, _ = _audit(root, capsys, "--run-check", deploy)
    [check] = report["declared_checks"]
    assert check["status"] == "NOT_RUN" and "never executed" in check["detail"]
    assert not any(f["code"] == "DECLARED_CHECK_FAILED" for f in report["findings"])
