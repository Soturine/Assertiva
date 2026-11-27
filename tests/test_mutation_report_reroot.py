"""A mutation report produced in another root (a container, a CI checkout) is tied by content, not refused by path.

Found in the v1.1 adaptive-tool dogfood: Stryker.NET ran in a container on a copy at /tmp/work and wrote absolute paths
of that root; the audit called the report MUTATION_REPORT_SOURCE_MISMATCH ("produced for different source") for the
exact revision it audited. Re-rooting only finds the candidate file by its trailing path; identical content still
decides, so a report of other code stays a mismatch."""

import json
import sys

from assertiva import cli
from conftest import commit_all, write

PRICE = "namespace Pricing;\npublic static class Price { public static int Total(int q) => q >= 10 ? q * 95 : q * 100; }\n"
TESTS = "public class PriceTests { [Fact] public void Small() => Assert.Equal(900, Price.Total(9)); }\n"


def _report(price_source: str) -> dict:
    return {"schemaVersion": "2", "thresholds": {"high": 80, "low": 60}, "projectRoot": "/tmp/work",
            "files": {"/tmp/work/src/Pricing/Price.cs": {"language": "cs", "source": price_source, "mutants": [
                {"id": "1", "mutatorName": "Equality mutation", "replacement": "q > 10", "status": "Survived",
                 "location": {"start": {"line": 2, "column": 60}, "end": {"line": 2, "column": 67}}}]}},
            "testFiles": {"/tmp/work/tests/PriceTests.cs": {"source": TESTS, "tests": [{"id": "t1", "name": "PriceTests.Small"}]}}}


def _audit(tmp_path, capsys, report: dict) -> dict:
    root = tmp_path / "pricing"
    write(root / "src" / "Pricing" / "Price.cs", PRICE)
    write(root / "tests" / "PriceTests.cs", TESTS)
    commit_all(root)
    path = tmp_path / "mutation-report.json"
    path.write_text(json.dumps(report), encoding="utf-8")
    assert cli.main(["audit", str(root), "--python", sys.executable, "--mutation-report", str(path), "--output", "json"]) == 0
    return json.loads(capsys.readouterr().out)


def test_a_report_from_another_root_is_tied_by_identical_content(tmp_path, capsys):
    out = _audit(tmp_path, capsys, _report(PRICE))
    run = out["states"]["current"]["mutation"][0]
    assert run["matches_state"] is True and "MUTATION_REPORT_SOURCE_MISMATCH" not in [f["code"] for f in out["findings"]]
    assert any("matched to the project by path suffix" in limit for limit in run["limitations"])


def test_a_report_of_other_code_stays_a_mismatch_after_rerooting(tmp_path, capsys):
    out = _audit(tmp_path, capsys, _report(PRICE.replace(">= 10", "> 10")))
    assert out["states"]["current"]["mutation"][0]["matches_state"] is False
    assert "MUTATION_REPORT_SOURCE_MISMATCH" in [f["code"] for f in out["findings"]]
