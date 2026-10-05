import json

from assertiva import cli


def test_audit_unknown_project_reports_unknown_not_zero_tests(tmp_path, monkeypatch, capsys):
    monkeypatch.setattr(
        "sys.argv",
        ["assertiva", "audit", str(tmp_path), "--output", "json"],
    )
    assert cli.main() == 0
    payload = json.loads(capsys.readouterr().out)
    assert payload["status"] == "UNKNOWN"
    assert payload["findings"][0]["code"] == "NO_EXECUTABLE_TEST_ADAPTER_RECOGNIZED"
