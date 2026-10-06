"""The contract the Skill relies on when it runs engine-backed: a cheap availability probe and a static,
read-only audit that returns the path of the HTML Assurance Report it wrote.

How the Skill reasons in semantic-only mode, about CI revision provenance, static counts and dependency
recommendations is judged by the semantic evals (evals/cases), not graded here by string."""

import json
import sys
from pathlib import Path

import pytest

from assertiva import __version__, cli
from assertiva.workspace import tree_fingerprint

ROOT = Path(__file__).resolve().parents[1]


def test_version_probe_tells_the_skill_the_engine_is_available(capsys):
    with pytest.raises(SystemExit) as exit_:
        cli.main(["--version"])
    assert exit_.value.code == 0
    assert capsys.readouterr().out.strip() == f"assertiva {__version__}"


def test_engine_backed_first_call_is_static_and_returns_the_html_report_path(calc_project, capsys):
    before = tree_fingerprint(calc_project)
    code = cli.main(["audit", str(calc_project), "--python", sys.executable, "--output", "json"])
    report = json.loads(capsys.readouterr().out)
    assert code == 0
    html = Path(report["report_path"])
    assert html.name == "audit.html" and html.is_file()
    assert not html.is_relative_to(calc_project)
    assert report["states"]["current"]["runs"] == []  # nothing executed without --execute
    assert tree_fingerprint(calc_project) == before


def test_skill_declares_both_modes_and_keeps_eval_verdicts_out_of_normal_use():
    skill = (ROOT / "SKILL.md").read_text(encoding="utf-8")
    assert "Assertiva mode: engine-backed" in skill
    assert "Assertiva mode: semantic-only" in skill
    assert "Assurance Report:" in skill and "report_path" in skill
    for category in ("DETERMINISTIC FACT", "DECLARED FACT", "HEURISTIC SIGNAL", "SEMANTIC INFERENCE", "UNKNOWN"):
        assert category in skill, category
    assert "never present PASS/FAIL/REVIEW as the Skill's verdict" in skill
