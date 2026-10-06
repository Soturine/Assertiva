"""The core is tool-neutral: evidence from any adapter flows through measure, qualification and
the report without the core knowing which runner, packager or CI produced it."""

import json
import re
from pathlib import Path

import pytest

from assertiva import adapters
from assertiva.candidate import DeltaState, QualificationCheck, StageStatus
from assertiva import models
from assertiva.models import ArtifactCheck, ArtifactEvidence, CoverageSummary, Outcome, RunEvidence
from assertiva.verification import SupportLevel

from conftest import write

RESULTS = "fake-results.json"


class FakeRunner:
    """Reads declared results from the project: ids deliberately unlike any real runner's."""

    adapter_id = "fake-runner"

    def __init__(self, python=None):
        pass

    def supports(self, root):
        return SupportLevel.SUPPORTED if (Path(root) / RESULTS).is_file() else SupportLevel.UNSUPPORTED

    def run(self, root, args=None, coverage=False):
        data = json.loads((Path(root) / RESULTS).read_text(encoding="utf-8"))
        invocations = [
            models.TestInvocation(invocation_id=i["id"], declaration_id=i["id"], materialization_id=i["id"],
                           outcome=Outcome(i["outcome"]), source_paths=tuple(i["sources"]))
            for i in data["invocations"]
        ]
        outcomes = {inv.outcome for inv in invocations}
        status = (StageStatus.UNKNOWN if not invocations
                  else StageStatus.FAIL if outcomes & {Outcome.FAILED, Outcome.ERROR} else StageStatus.PASS)
        run = RunEvidence(adapter_id=self.adapter_id, mode="execute", status=status, invocations=invocations,
                          collection_errors=list(data.get("errors", {})), command=["fake-runner"], wall_clock_s=0.1)
        run.metadata["error_sources"] = data.get("errors", {})
        if coverage and "coverage" in data:
            run.coverage = CoverageSummary(data["coverage"]["line"], data["coverage"]["branch"], "fake coverage")
        return run

    def static_signals(self, root):
        return {}

    def static_negative_paths(self, root):
        return {}

    def reproduction_args(self, check):
        return None

    def equivalent_to_default(self, args):
        return not args


class FakeArtifact:
    adapter_id = "fake-bundler"

    def __init__(self, python=None):
        pass

    def supports(self, root):
        return SupportLevel.SUPPORTED if (Path(root) / "bundle.manifest").is_file() else SupportLevel.UNSUPPORTED

    def qualify(self, root):
        ok = "broken" not in (Path(root) / "bundle.manifest").read_text(encoding="utf-8")
        status = StageStatus.PASS if ok else StageStatus.FAIL
        return ArtifactEvidence(adapter_id=self.adapter_id, kind="bundle", status=status, artifact="app.bundle",
                                checks=[ArtifactCheck("bundle", status, detail="fake bundle check")],
                                fidelity={"BUNDLE_LOADS": status.value})


@pytest.fixture
def fake_stack(monkeypatch, tmp_path):
    monkeypatch.setattr(adapters, "RUNNER_FACTORIES", [FakeRunner])
    monkeypatch.setattr(adapters, "ARTIFACT_FACTORIES", [FakeArtifact])
    root = tmp_path / "other-stack"
    write(root / "src" / "app.other", "fn add(a, b) = a + b\n")
    write(root / "spec" / "add.spec", "add works\n")
    write(root / "bundle.manifest", "ok\n")
    results(root, [{"id": "add > works", "outcome": "PASSED", "sources": ["spec/add.spec"]}], line=60.0, branch=40.0)
    return root


def results(root, invocations, line=None, branch=None, errors=None):
    data = {"invocations": invocations, "errors": errors or {}}
    if line is not None:
        data["coverage"] = {"line": line, "branch": branch}
    write(root / RESULTS, json.dumps(data))


def test_generic_runner_evidence_enters_state_evidence(fake_stack):
    from assertiva.evidence import measure, state_metrics

    state = measure(fake_stack, "current", "isolated-project-copy")
    assert [run.adapter_id for run in state.runs] == ["fake-runner"]
    metrics = state_metrics(state)
    assert metrics["test_invocations"].value == 1 and metrics["line_coverage"].value == 60.0
    assert [a.kind for a in state.artifacts] == ["bundle"]


def test_generic_coverage_and_artifact_evidence_reach_qualification(fake_stack):
    from assertiva.improve import discard_session, qualify_candidate, start_improve

    session = start_improve(fake_stack)
    try:
        write(session.workspace / "spec" / "edge.spec", "add handles zero\n")
        results(session.workspace, [
            {"id": "add > works", "outcome": "PASSED", "sources": ["spec/add.spec"]},
            {"id": "add > zero", "outcome": "PASSED", "sources": ["spec/edge.spec"]},
        ], line=75.0, branch=70.0)
        q = qualify_candidate(session).qualification
    finally:
        discard_session(session)
    deltas = {d.name: d.state for d in q.metric_deltas}
    assert deltas["branch_coverage"] is DeltaState.IMPROVED and deltas["line_coverage"] is DeltaState.IMPROVED
    stages = {c.check: c for c in q.checks}
    assert stages[QualificationCheck.CANDIDATE_TESTS].status is StageStatus.PASS
    assert stages[QualificationCheck.ORIGINAL_REGRESSION].status is StageStatus.PASS
    assert stages[QualificationCheck.BUILD_AND_ARTIFACT].status is StageStatus.PASS
    assert "bundle app.bundle" in stages[QualificationCheck.BUILD_AND_ARTIFACT].summary


def test_collection_errors_are_attributed_by_the_adapter_not_by_id_syntax(fake_stack):
    from assertiva.improve import discard_session, qualify_candidate, start_improve

    session = start_improve(fake_stack)
    try:
        write(session.workspace / "spec" / "broken.spec", "???\n")
        results(session.workspace, [{"id": "add > works", "outcome": "PASSED", "sources": ["spec/add.spec"]}],
                errors={"the broken suite": "spec/broken.spec"})
        q = qualify_candidate(session).qualification
    finally:
        discard_session(session)
    candidate_tests = next(s for s in q.checks if s.check is QualificationCheck.CANDIDATE_TESTS)
    assert candidate_tests.status is StageStatus.FAIL and "the broken suite" in candidate_tests.summary


def test_unknown_runner_evidence_stays_unknown(fake_stack):
    from assertiva.audit import run_audit

    results(fake_stack, [])
    report = run_audit(fake_stack, execute=True)
    assert report["states"]["current"]["runs"][0]["status"] == "UNKNOWN"
    assert "test_invocations" in report["states"]["current"]["metrics"]
    observed = " ".join(report["claim_boundary"]["observed"])
    assert "fake-runner run in an isolated copy: UNKNOWN (0 invocations)" in observed


def test_report_renders_without_python_or_pytest_fields(fake_stack):
    from assertiva.audit import run_audit
    from assertiva.report import render_html

    report = run_audit(fake_stack, execute=True)
    html = render_html(report)
    assert "fake-runner" in html and "fake-bundler" in html and "bundle loads PASS" in html
    assert not re.search(r"pytest|wheel|python", html, re.I)


CORE = ("candidate.py", "evidence.py", "verification.py", "report.py", "workspace.py", "models.py", "process.py", "improve.py", "impact.py", "selection.py", "components.py")
TOOL_NAMES = r"pytest|py\.test|setuptools|\bwheel\b|\bpip\b|github|stryker|pitest|mutmut|cosmic|jest|vitest|junit|playwright|maven|gradle|dotnet|npm"


@pytest.mark.parametrize("module", CORE)
def test_core_modules_do_not_name_tools(module):
    import assertiva

    text = (Path(assertiva.__file__).parent / module).read_text(encoding="utf-8")
    code = "\n".join(line for line in text.splitlines() if not line.lstrip().startswith("#"))
    assert not re.findall(TOOL_NAMES, code, re.I), module


@pytest.mark.parametrize("module", CORE)
def test_core_modules_do_not_parse_runner_id_syntax(module):
    import assertiva

    text = (Path(assertiva.__file__).parent / module).read_text(encoding="utf-8")
    assert 'split("::")' not in text and "split('::')" not in text, module


# --- universal runner contracts (adapter-specific behavior stays in each adapter's tests) ---------

FIXTURE_DIR = Path(__file__).parent / "fixtures"
OWN_PROJECT = {"pytest-native": None, "jest": "js-jest", "playwright": "js-playwright", "maven": "java-maven"}


def _runner(adapter_id):
    from assertiva.adapters.jest import JestAdapter
    from assertiva.adapters.maven import MavenAdapter
    from assertiva.adapters.playwright import PlaywrightAdapter
    from assertiva.adapters.pytest_native import PytestNativeAdapter

    return {"pytest-native": PytestNativeAdapter, "jest": JestAdapter, "playwright": PlaywrightAdapter, "maven": MavenAdapter}[adapter_id]


@pytest.mark.parametrize("adapter_id", list(OWN_PROJECT))
def test_each_runner_claims_exactly_its_own_project(adapter_id, tmp_path):
    python_project = tmp_path / "py"
    write(python_project / "tests" / "test_ok.py", "def test_ok():\n    assert True\n")
    projects = {name: (FIXTURE_DIR / folder if folder else python_project) for name, folder in OWN_PROJECT.items()}
    adapter = _runner(adapter_id)()
    claimed = {name for name, root in projects.items() if adapter.supports(root) is SupportLevel.SUPPORTED}
    assert claimed == {adapter_id}


UNAVAILABLE = {
    "pytest-native": ({"tests/test_ok.py": "def test_ok():\n    assert 1 == 1\n"}, {}, {"python": "no-such-python"}),
    "jest": ({"package.json": '{"devDependencies": {"jest": "30.5.2"}}'}, {}, {}),
    "playwright": ({"package.json": '{"devDependencies": {"@playwright/test": "1.63.0"}}'}, {}, {}),
    "maven": ({"pom.xml": "<project/>", "mvnw": "#!/bin/sh\necho must never run\n"}, {"ASSERTIVA_MAVEN": "missing/mvn"}, {}),
}


@pytest.mark.parametrize("adapter_id", list(UNAVAILABLE))
def test_unavailable_runner_is_blocked_never_pass_and_installs_nothing(adapter_id, tmp_path, monkeypatch):
    from assertiva.workspace import tree_fingerprint

    files, env, kwargs = UNAVAILABLE[adapter_id]
    for rel, text in files.items():
        write(tmp_path / rel, text)
    for name, value in env.items():
        monkeypatch.setenv(name, str(tmp_path / value))
    if "python" in kwargs:
        kwargs = {"python": str(tmp_path / kwargs["python"])}
    before = tree_fingerprint(tmp_path)
    run = _runner(adapter_id)(**kwargs).run(tmp_path)
    assert run.status is StageStatus.BLOCKED and run.invocations == [] and run.limitations
    assert tree_fingerprint(tmp_path) == before  # nothing installed, no wrapper or build output
