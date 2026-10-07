"""`assertiva audit` finishing is not the audited project's tests passing: the verdict lives in the report."""

import json
import re
import sys
from pathlib import Path

import pytest

from assertiva import cli

from conftest import write


@pytest.mark.integration
def test_audit_command_success_is_not_the_audited_suite_passing(tmp_path, capsys):
    project = tmp_path / "failing"
    write(project / "lib.py", "def two():\n    return 2\n")
    write(project / "conftest.py", "")
    write(project / "tests" / "test_lib.py",
          "from lib import two\n\ndef test_two():\n    assert two() == 2\n\ndef test_broken():\n    assert two() == 3\n")
    code = cli.main(["audit", str(project), "--execute", "--python", sys.executable, "--output", "json", "--report-dir", str(tmp_path / "reports")])
    report = json.loads(capsys.readouterr().out)

    assert code == 0  # the command ran to completion and reported; 2 means refusal or misuse, 3 a read-only violation
    state = report["states"]["current"]
    assert state["runs"][0]["status"] == "FAIL"
    assert (state["metrics"]["passed"]["value"], state["metrics"]["failed"]["value"]) == (1, 1)
    assert report["status"] == "FINDINGS" and "NATIVE_TESTS_FAILING" in {f["code"] for f in report["findings"]}
    assert "native pytest-native run in an isolated copy: FAIL (2 invocations)" in report["claim_boundary"]["observed"]

    page = Path(report["report_path"]).read_text(encoding="utf-8")
    assert re.search(r'class="c-headline">.*?>Needs review<', page, re.S)  # the page concludes "needs review", not success
    assert sorted(p.name for p in (tmp_path / "reports").iterdir()) == ["audit.html", "audit.json"]
