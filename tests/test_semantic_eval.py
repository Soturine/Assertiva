"""The semantic eval harness keeps the rubric away from the evaluated agent and never grades by string.

These tests check how contexts are assembled and how verdicts are validated; they do not grade answers."""

import json
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "evals"))

import semantic  # noqa: E402

PRIVATE = ("Expected", "Expected behavior", "Prohibited", "Prohibited behavior", "Evidence requirements",
           "Scoring dimensions", "Acceptable alternatives", "Pass", "Pass condition", "Identity")
CASES = sorted(p.stem for p in semantic.CASES.glob("*.md"))


@pytest.mark.parametrize("case", CASES)
def test_agent_context_never_contains_the_private_rubric(case):
    _, sections = semantic.case_sections(case)
    context = semantic.agent_context(case)
    for name in PRIVATE:
        body = sections.get(name)
        if body:
            assert body not in context, (case, name)
    assert "<skill>" in context and semantic.DEFAULT_TASK in context or "Prompt / task" in sections


@pytest.mark.parametrize("case", CASES)
def test_agent_context_does_not_announce_the_case_title(case):
    """A case title names the failure mode under test; the evaluated agent sees only the scenario and the task."""
    title, sections = semantic.case_sections(case)
    visible = "\n".join(sections.get(name, "") for name in semantic.AGENT_SECTIONS)
    if title not in visible:
        assert title not in semantic.agent_context(case)


def test_agent_context_carries_the_skill_and_every_reference_it_can_load():
    context = semantic.agent_context("SELF_AUDIT_ASSERTIVA")
    assert semantic.SKILL_FILES, "the Skill ships references for progressive disclosure"
    for path in semantic.SKILL_FILES:
        rel = path.relative_to(semantic.ROOT).as_posix()
        assert f'<skill-file path="{rel}">' in context and path.read_text(encoding="utf-8") in context


@pytest.mark.parametrize("case", sorted(p.name for p in semantic.FIXTURES.iterdir() if p.is_dir()))
def test_a_case_with_a_fixture_works_on_that_project_not_on_this_repository(case, tmp_path):
    assert case in CASES, "every fixture belongs to a case"
    semantic.main(["prepare", "--out", str(tmp_path), "--workspace", case])
    workspace = tmp_path / case / "workspace"
    assert (workspace / "pyproject.toml").is_file()
    assert not (workspace / "evals").exists() and not (workspace / "SKILL.md").exists()
    assert str(workspace) in (tmp_path / case / "agent.md").read_text(encoding="utf-8")


def test_judge_context_holds_the_full_rubric_and_the_response():
    _, sections = semantic.case_sections("SELF_AUDIT_ASSERTIVA")
    context = semantic.judge_context("SELF_AUDIT_ASSERTIVA", "my answer")
    assert sections["Pass condition"] in context and sections["Prohibited behavior"] in context and "my answer" in context


@pytest.mark.parametrize("text", [
    '{"verdict": "PASS", "justification": "grounded", "dimensions": {"safety": "fine"}}',
    'Verdict follows:\n{"verdict": "REVIEW", "justification": "borderline"}',
])
def test_verdicts_are_categories_with_justification(text):
    assert semantic.parse_verdict(text)["verdict"] in {"PASS", "REVIEW"}


@pytest.mark.parametrize("text", [
    '{"verdict": "PASS"}',  # no justification
    '{"verdict": "GOOD", "justification": "x"}',
    '{"verdict": "PASS", "justification": "x", "score": 8}',
    '{"verdict": "PASS", "justification": "x", "quality": 0.9}',
    "PASS",
])
def test_scores_and_malformed_verdicts_are_rejected(text):
    with pytest.raises((ValueError, json.JSONDecodeError)):
        semantic.parse_verdict(text)


def test_workspace_copy_keeps_the_skill_and_package_and_leaves_the_rubric_out(tmp_path):
    """The exclusion rule, on a synthetic repository and an explicit manifest: it needs no Git checkout."""
    repo = tmp_path / "repo"
    for rel in ("SKILL.md", "assertiva/__init__.py", "evals/cases/CASE.md", "evals/semantic.py", "docs/a.md"):
        (repo / rel).parent.mkdir(parents=True, exist_ok=True)
        (repo / rel).write_text(rel, encoding="utf-8")
    manifest = ["SKILL.md", "assertiva/__init__.py", "evals/cases/CASE.md", "evals/semantic.py", "docs/a.md", "not-a-file/"]
    workspace = semantic.workspace_copy(tmp_path / "ws", root=repo, files=manifest)
    assert (workspace / "SKILL.md").is_file() and (workspace / "assertiva" / "__init__.py").is_file()
    assert (workspace / "docs" / "a.md").is_file()
    assert not (workspace / "evals").exists()


def test_workspace_copy_without_git_or_a_manifest_names_the_missing_prerequisite(tmp_path):
    plain = tmp_path / "plain"
    plain.mkdir()
    with pytest.raises(RuntimeError, match="not a Git checkout"):
        semantic.workspace_copy(tmp_path / "ws", root=plain)


@pytest.mark.skipif(not (semantic.ROOT / ".git").exists(), reason="needs a Git checkout: the tracked-file list defines this repository's workspace")
def test_agent_workspace_of_this_checkout_has_no_rubric(tmp_path):
    workspace = semantic.workspace_copy(tmp_path / "ws")
    assert (workspace / "SKILL.md").is_file() and (workspace / "assertiva").is_dir()
    assert not (workspace / "evals").exists()
    assert "Do not read anything outside" in semantic.agent_context("SELF_AUDIT_ASSERTIVA", workspace)


def test_missing_verdict_is_recorded_as_not_judged_never_as_pass(tmp_path):
    out = tmp_path / "run"
    (out / "CASE_A").mkdir(parents=True)
    (out / "CASE_A" / "response.md").write_text("answer", encoding="utf-8")
    (out / "CASE_A" / "verdict.json").write_text('{"verdict": "PASS", "justification": "ok"}', encoding="utf-8")
    (out / "CASE_B").mkdir()
    (out / "CASE_B" / "response.md").write_text("answer", encoding="utf-8")
    (out / "CASE_C").mkdir()  # prepared but never run: not a verdict of any kind
    semantic.main(["record", "--out", str(out), "--results", str(tmp_path / "results"), "--agent", "a", "--judge", "j"])
    page = (tmp_path / "results" / "README.md").read_text(encoding="utf-8")
    assert "CASE_A: PASS" in page and "CASE_B: NOT_JUDGED_INFRA" in page and "CASE_C: NOT_RUN" in page
    assert "FAIL" not in page.split("## Not judged")[1]  # infrastructure is never a fail
