"""The contract the Skill relies on when it uses the engine: a cheap availability probe, a read-only audit that returns
the path of the HTML Assurance Report it wrote, and the invariants SKILL.md states.

How the agent investigates, when it stops and how it reasons about CI provenance, static counts and dependency
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


def test_skill_states_the_invariants_it_relies_on_and_leaves_method_to_the_agent():
    """String checks only for contracts the engine and the report depend on; how the agent investigates is graded by
    the semantic evals, never by keywords here."""
    skill = (ROOT / "SKILL.md").read_text(encoding="utf-8")
    assert skill.splitlines()[:3] == ["---", "name: assertiva", skill.splitlines()[2]]  # Agent Skills frontmatter
    assert skill.splitlines()[2].startswith("description: ")
    assert len(skill.splitlines()) < 150, "SKILL.md stays an entrypoint; detail lives in references/"
    assert "Assurance Report:" in skill and "report_path" in skill and "--assessment" in skill
    for category in ("OBSERVED", "DECLARED", "INFERRED", "UNKNOWN"):
        assert f"**{category}**" in skill, category
    assert "never present PASS/FAIL/REVIEW as the Skill's verdict" in skill
    assert "Audit never modifies the project" in skill and "never pass `--approve`" in skill
    engine = (ROOT / "references" / "ENGINE.md").read_text(encoding="utf-8")
    for disposition in ("CONFIRMED", "PARTIAL", "CONTEXTUAL", "FALSE_POSITIVE", "UNRESOLVED"):
        assert f"`{disposition}`" in engine
