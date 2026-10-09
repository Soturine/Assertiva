"""Delivery intelligence: CI configuration from several providers through one Verification Surface,
matrix visibility, artifact lineage and review candidates. Declared evidence only; nothing remote runs."""

import hashlib


from assertiva.adapters.azure_pipelines import AzurePipelinesAdapter
from assertiva.adapters.gitlab_ci import GitLabCiAdapter
from assertiva.adapters.jenkins import JenkinsAdapter
from assertiva.candidate import StageStatus
from assertiva.models import ArtifactEvidence
from assertiva.verification import GateMode, VerificationKind, artifact_lineage, discover_surface

from conftest import write

AZURE = """
pool:
  vmImage: ubuntu-latest
stages:
  - stage: test
    jobs:
      - job: unit
        strategy:
          matrix:
            py311: {python.version: '3.11'}
            py312: {python.version: '3.12'}
        steps:
          - task: UsePythonVersion@0
          - script: python -m pytest -q
            displayName: tests
          - script: ruff check .
            continueOnError: true
  - stage: release
    condition: eq(variables['Build.SourceBranch'], 'refs/heads/main')
    jobs:
      - deployment: ship
        environment: production
        strategy:
          runOnce:
            deploy:
              steps:
                - script: twine upload dist/*
"""

GITLAB = """
image: python:3.12
include:
  - project: shared/ci
stages: [test, deploy]
.template: {script: [echo hidden]}
test:
  stage: test
  before_script: [pip install -e .]
  script:
    - pytest -q
  parallel:
    matrix:
      - PYTHON_VERSION: ["3.11", "3.12"]
lint:
  script: [ruff check .]
  allow_failure: true
  rules:
    - if: $CI_PIPELINE_SOURCE == "merge_request_event"
deploy:
  stage: deploy
  script: [kubectl apply -f k8s/]
  environment: {name: production}
  when: manual
"""

JENKINS = """
@Library('shared') _
pipeline {
  agent { docker { image 'python:3.12' } }
  stages {
    stage('Test') {
      steps {
        sh 'pytest -q'
        sh "pytest tests/${SUITE}"
      }
    }
    stage('Lint') {
      when { branch 'main' }
      steps { catchError { sh 'ruff check .' } }
    }
    stage('Deploy') {
      steps { sh 'helm upgrade app ./chart' }
    }
  }
}
"""


def by_command(checks):
    return {c.command: c for c in checks if c.command}


def test_azure_pipelines(tmp_path):
    write(tmp_path / "azure-pipelines.yml", AZURE)
    checks = AzurePipelinesAdapter().discover(tmp_path)
    commands = by_command(checks)
    tests = commands["python -m pytest -q"]
    assert tests.kind is VerificationKind.TEST and tests.metadata["lifecycle"] == {
        "declared": True, "selected": "UNCONDITIONAL", "executed": "UNKNOWN", "deploys": False}
    assert tests.metadata["matrix_values"] == {"python": ["3.11", "3.12"], "os": ["ubuntu-latest"]}
    assert commands["ruff check ."].gate is GateMode.ALLOWED_FAILURE
    ship = commands["twine upload dist/*"]
    assert ship.kind is VerificationKind.DEPLOY and ship.metadata["environment"] == "production"
    assert ship.metadata["lifecycle"]["selected"] == "CONDITIONAL" and ship.metadata["lifecycle"]["deploys"]
    assert any(c.tool == "UsePythonVersion@0" and c.kind is VerificationKind.UNKNOWN for c in checks)


def test_gitlab_ci(tmp_path):
    write(tmp_path / ".gitlab-ci.yml", GITLAB)
    checks = GitLabCiAdapter().discover(tmp_path)
    commands = by_command(checks)
    assert "echo hidden" not in commands and "pip install -e ." not in commands  # hidden jobs and setup are not checks
    tests = commands["pytest -q"]
    assert tests.kind is VerificationKind.TEST and tests.metadata["matrix_values"] == {"python": ["3.11", "3.12"]}
    lint = commands["ruff check ."]
    assert lint.gate is GateMode.ALLOWED_FAILURE and lint.metadata["lifecycle"]["selected"] == "CONDITIONAL"
    deploy = commands["kubectl apply -f k8s/"]
    assert deploy.kind is VerificationKind.DEPLOY and deploy.metadata["environment"] == "production"
    assert any("include" in (c.tool or "") and "not followed" in c.limitations[0] for c in checks)


def test_jenkins_declarative_pipeline(tmp_path):
    write(tmp_path / "Jenkinsfile", JENKINS)
    checks = JenkinsAdapter().discover(tmp_path)
    commands = by_command(checks)
    assert commands["pytest -q"].kind is VerificationKind.TEST and commands["pytest -q"].metadata["matrix_values"] == {"python": ["3.12"]}
    lint = commands["ruff check ."]
    assert lint.gate is GateMode.ALLOWED_FAILURE and lint.metadata["lifecycle"]["selected"] == "CONDITIONAL"
    assert commands["helm upgrade app ./chart"].kind is VerificationKind.DEPLOY
    dynamic = [c for c in checks if c.metadata.get("command") == "pytest tests/${SUITE}"]
    assert dynamic and dynamic[0].kind is VerificationKind.UNKNOWN  # interpolated command: not guessed
    assert any(c.tool == "shared library" for c in checks)


def test_unreadable_configuration_is_unknown_not_guessed(tmp_path):
    write(tmp_path / ".gitlab-ci.yml", "test: [unclosed\n")
    [check] = GitLabCiAdapter().discover(tmp_path)
    assert check.kind is VerificationKind.UNKNOWN and "could not be parsed" in check.limitations[0]


def test_every_provider_joins_one_surface(tmp_path):
    write(tmp_path / "azure-pipelines.yml", AZURE)
    write(tmp_path / ".gitlab-ci.yml", GITLAB)
    write(tmp_path / "Jenkinsfile", JENKINS)
    adapters = {c.adapter_id for c in discover_surface(tmp_path).checks}
    assert {"azure-pipelines", "gitlab-ci", "jenkins"} <= adapters


# --- matrix visibility ----------------------------------------------------------------------------

GHA = """
on: push
jobs:
  test:
    runs-on: ubuntu-latest
    strategy:
      matrix:
        python-version: [{versions}]
    steps:
      - uses: actions/setup-python@v6
        with:
          python-version: ${{{{ matrix.python-version }}}}
      - run: pytest -q
"""


def audit_findings(root):
    from assertiva.audit import run_audit

    report = run_audit(root)
    return {f["code"]: f for f in report["findings"]}, report


def python_project(root, versions, requires=">=3.11"):
    write(root / "pyproject.toml", f'[project]\nname = "shop"\nversion = "1"\nrequires-python = "{requires}"\n')
    write(root / "tests" / "test_ok.py", "def test_ok():\n    assert True\n")
    write(root / ".github" / "workflows" / "ci.yml", GHA.format(versions=versions))
    return root


def test_declared_minimum_runtime_not_selected_by_ci_is_a_gap(tmp_path):
    findings, report = audit_findings(python_project(tmp_path, "'3.12', '3.13'"))
    assert findings["MATRIX_GAP"]["evidence"]["missing"] == ["3.11"]
    assert report["delivery"]["matrix"]["ci"]["python"] == ["3.12", "3.13"]
    assert findings["CI_SINGLE_OS"]["severity"] == "info"


def test_runtime_in_the_matrix_is_not_a_gap(tmp_path):
    findings, _ = audit_findings(python_project(tmp_path, "'3.11', '3.12'"))
    assert "MATRIX_GAP" not in findings and "MATRIX_UNVERIFIED" not in findings


def test_ci_that_never_states_the_runtime_is_unverified_not_assumed(tmp_path):
    root = python_project(tmp_path, "'3.12'")
    write(root / ".github" / "workflows" / "ci.yml", "on: push\njobs:\n  test:\n    runs-on: ubuntu-latest\n    steps:\n      - run: pytest -q\n")
    findings, _ = audit_findings(root)
    assert findings["MATRIX_UNVERIFIED"]["evidence"]["dimension"] == "python"


def test_declared_browser_project_not_run_in_ci(tmp_path):
    write(tmp_path / "package.json", '{"devDependencies": {"@playwright/test": "1.63.0"}}')
    write(tmp_path / "playwright.config.js",
          "module.exports = { projects: [ { name: 'chromium' }, { name: 'firefox' }, { name: 'webkit' } ] };\n")
    write(tmp_path / ".github" / "workflows" / "e2e.yml",
          "on: push\njobs:\n  e2e:\n    runs-on: ubuntu-latest\n    steps:\n      - run: npx playwright test --project=chromium\n")
    findings, _ = audit_findings(tmp_path)
    assert findings["MATRIX_GAP"]["evidence"] == {"dimension": "browser project", "missing": ["firefox", "webkit"],
                                                  "ci": ["chromium"], "source": "playwright.config.js projects"}


# --- artifact lineage ------------------------------------------------------------------------------

def surface_with(tmp_path, steps):
    write(tmp_path / ".github" / "workflows" / "release.yml",
          "on: push\njobs:\n  release:\n    runs-on: ubuntu-latest\n    steps:\n" + "".join(f"      - run: {s}\n" for s in steps))
    return discover_surface(tmp_path)


def artifact(sha):
    return ArtifactEvidence(adapter_id="python-package", kind="wheel", status=StageStatus.PASS, artifact="shop-1-py3-none-any.whl", sha256=sha)


def test_publishing_an_untested_build_and_unknown_lineage(tmp_path):
    _, findings = artifact_lineage(surface_with(tmp_path, ["python -m build", "twine upload dist/*"]), [], {}, "abc")
    codes = {f.code for f in findings}
    assert codes == {"PUBLISHED_ARTIFACT_NOT_QUALIFIED", "ARTIFACT_LINEAGE_UNKNOWN"}


def test_tested_in_the_publishing_job_still_has_unknown_lineage(tmp_path):
    lineage, findings = artifact_lineage(surface_with(tmp_path, ["python -m build", "pytest -q", "twine upload dist/*"]),
                                         [artifact("a" * 64)], {}, "abc")
    assert {f.code for f in findings} == {"ARTIFACT_LINEAGE_UNKNOWN"}
    [entry] = lineage
    assert entry["tested"] == "PASS" and entry["source_revision"] == "abc" and len(entry["published"]) == 1


def test_tested_artifact_differs_from_the_one_that_would_ship(tmp_path):
    shipped = [("dist/shop-1-py3-none-any.whl", hashlib.sha256(b"other bytes").hexdigest())]
    _, findings = artifact_lineage(surface_with(tmp_path, ["pytest -q"]), [artifact("a" * 64)], {"shop-1-py3-none-any.whl": shipped}, "abc")
    assert [f.code for f in findings] == ["TESTED_ARTIFACT_DIFFERS_FROM_DELIVERED"]


def test_no_delivery_declared_means_no_lineage_claim(tmp_path):
    lineage, findings = artifact_lineage(surface_with(tmp_path, ["pytest -q"]), [artifact("a" * 64)], {}, "abc")
    assert findings == [] and lineage[0]["published"] == "NOT_DECLARED"


# --- review candidates -------------------------------------------------------------------------------

REVIEW = {
    "tests/helpers.py": "def assert_valid_order(order):\n    assert order['id'] > 0\n",
    "tests/test_orders.py": (
        "import pytest\nfrom unittest.mock import patch\nfrom helpers import assert_valid_order\n\n\n"
        "def test_a():\n    assert_valid_order({'id': 1})\n\n\n"
        "def test_b():\n    assert_valid_order({'id': 2})\n\n\n"
        "@patch('shop.db.connect')\ndef test_c(connect):\n    assert connect\n\n\n"
        "def test_d(monkeypatch):\n    monkeypatch.setattr('shop.db.connect', lambda: None)\n    assert True\n\n\n"
        "@pytest.mark.integration\ndef test_checkout_integration(monkeypatch):\n    monkeypatch.setattr('shop.payments.charge', lambda *a: True)\n    assert True\n"
    ),
    "tests/test_views.py": "def test_home(snapshot):\n    assert snapshot\n\n\ndef test_about(snapshot):\n    assert snapshot\n",
    "tests/test_unique.py": "from helpers import assert_valid_order\n\n\ndef test_only():\n    assert 1\n",
    # a project function that happens to be called snapshot is not a snapshot assertion
    "tests/test_copies.py": "from shop.workspace import snapshot\n\n\ndef test_a():\n    assert snapshot('a')\n\n\ndef test_b():\n    assert snapshot('b')\n",
}


def test_review_candidates_are_concentrations_not_duplicates_or_findings(tmp_path):
    from assertiva.pytest_audit import review_candidates

    for rel, text in REVIEW.items():
        write(tmp_path / rel, text)
    found = {(c["kind"], c["subject"]): c for c in review_candidates(tmp_path)}
    assert found[("SHARED_ORACLE_HELPER", "assert_valid_order")]["tests"] == 2
    assert found[("CENTRAL_TEST_DOUBLE", "shop.db.connect")]["tests"] == 2
    assert ("INTEGRATION_TEST_REPLACES_DEPENDENCY", "shop.payments.charge") in found
    assert found[("SNAPSHOT_CONCENTRATION", "tests/test_views.py")]["tests"] == 2
    assert ("SNAPSHOT_CONCENTRATION", "tests/test_copies.py") not in found
    assert all("not duplicate" in c["note"] for c in found.values())
    findings, report = audit_findings(tmp_path)
    assert report["review_candidates"] and not {c["kind"] for c in report["review_candidates"]} & set(findings)
