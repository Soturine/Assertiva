"""GitLab CI: the effective configuration across local includes, templates and `extends`.

Found by auditing a real project whose test jobs all lived in locally included files: the adapter saw one opaque
`include` and the hooks, and no test job at all. The layout below is synthetic."""

from assertiva.adapters.gitlab_ci import GitLabCiAdapter
from assertiva.verification import GateMode, VerificationKind, discover_surface, surface_findings
from conftest import write

MAIN = """
include:
  - /ci/base.yml
  - local: ci/jobs/*.yml
  - remote: https://example.invalid/shared.yml
  - local: ci/missing.yml
default:
  image: python:3.12
stages: [lint, test, deploy]
"""
BASE = """
include: ci/templates.yml
variables:
  APP_ENV: test
"""
TEMPLATES = """
.python-job:
  before_script:
    - pip install -r requirements.txt
    - python -m compileall -q src
  tags: [docker]
.db-job:
  extends: .python-job
  services: [postgres:16]
"""
UNIT = """
unit-tests:
  extends: .python-job
  stage: test
  script:
    - pytest -q tests/unit
  parallel:
    matrix:
      - PYTHON: ["3.11", "3.12"]
"""
INTEGRATION = """
integration-tests:
  extends: .db-job
  needs: [unit-tests]
  script:
    - !reference [.python-job, before_script]
    - pytest -q -m integration
  rules:
    - if: $CI_PIPELINE_SOURCE == "merge_request_event"
lint:
  stage: lint
  script: [ruff check .]
  allow_failure:
    exit_codes: [2]
retired:
  script: [pytest -q tests/legacy]
  when: never
"""


def project(tmp_path):
    write(tmp_path / ".gitlab-ci.yml", MAIN)
    write(tmp_path / "ci" / "base.yml", BASE)
    write(tmp_path / "ci" / "templates.yml", TEMPLATES)
    write(tmp_path / "ci" / "jobs" / "unit.yml", UNIT)
    write(tmp_path / "ci" / "jobs" / "integration.yml", INTEGRATION)
    return tmp_path


def by_job(checks):
    out = {}
    for check in checks:
        out.setdefault(check.metadata.get("job"), []).append(check)
    return out


def test_jobs_in_nested_local_includes_are_discovered_with_their_templates(tmp_path):
    jobs = by_job(GitLabCiAdapter().discover(project(tmp_path)))
    unit = {c.command: c for c in jobs["unit-tests"]}
    assert unit["pytest -q tests/unit"].kind is VerificationKind.TEST
    assert unit["pytest -q tests/unit"].metadata["defined_in"] == "ci/jobs/unit.yml"
    assert unit["pytest -q tests/unit"].metadata["matrix_values"]["python"] == ["3.11", "3.12"]
    assert "python -m compileall -q src" in unit  # before_script inherited through extends from an included template
    assert ".python-job" not in jobs and ".db-job" not in jobs  # hidden templates are not jobs


def test_multi_level_extends_services_references_rules_and_needs(tmp_path):
    jobs = by_job(GitLabCiAdapter().discover(project(tmp_path)))
    integration = {c.command: c for c in jobs["integration-tests"]}
    test = integration["pytest -q -m integration"]
    assert test.metadata["services"] == ["postgres:16"] and test.metadata["needs"] == ["unit-tests"]
    assert test.metadata["lifecycle"]["selected"] == "CONDITIONAL"
    assert "python -m compileall -q src" in integration  # !reference expanded
    assert test.metadata["image"] == "python:3.12"  # default image


def test_allow_failure_exit_codes_and_jobs_that_never_run(tmp_path):
    jobs = by_job(GitLabCiAdapter().discover(project(tmp_path)))
    [lint] = jobs["lint"]
    assert lint.gate is GateMode.ALLOWED_FAILURE and lint.metadata["allow_failure"] == {"exit_codes": [2]}
    assert "retired" not in jobs


def test_what_cannot_be_resolved_stays_explicit(tmp_path):
    checks = GitLabCiAdapter().discover(project(tmp_path))
    limits = " ".join(" ".join(c.limitations) for c in checks if c.metadata.get("job") is None)
    assert "remote include is not followed" in limits
    assert "included local file not found in the repository: ci/missing.yml" in limits


def test_include_and_extends_cycles_are_reported_not_looped(tmp_path):
    write(tmp_path / ".gitlab-ci.yml", "include: ci/a.yml\n")
    write(tmp_path / "ci" / "a.yml", "include: ci/b.yml\n.a: {extends: .b, script: [pytest]}\njob: {extends: .a}\n")
    write(tmp_path / "ci" / "b.yml", "include: ci/a.yml\n.b: {extends: .a}\n")
    checks = GitLabCiAdapter().discover(tmp_path)
    assert any("include cycle" in " ".join(c.limitations) for c in checks)
    [job] = [c for c in checks if c.metadata.get("job") == "job"]
    assert any("extends cycle" in lim for lim in job.limitations)


def test_an_include_cannot_reach_outside_the_repository(tmp_path):
    write(tmp_path / "outside.yml", "stolen: {script: [pytest]}\n")
    root = tmp_path / "repo"
    write(root / ".gitlab-ci.yml", "include: /../outside.yml\n")
    checks = GitLabCiAdapter().discover(root)
    assert not any(c.metadata.get("job") == "stolen" for c in checks)


def test_a_ci_step_running_a_project_script_matches_the_local_check(tmp_path):
    write(tmp_path / "package.json", '{"scripts": {"test": "jest --ci", "lint": "eslint ."}}')
    write(tmp_path / ".gitlab-ci.yml", "test:\n  script: [npm test]\nlint:\n  script: [npm run lint]\n")
    surface = discover_surface(tmp_path)
    ci = {c.command: c for c in surface.checks if c.adapter_id == "gitlab-ci"}
    assert ci["npm test"].metadata["effective_tool"] == "jest" and ci["npm run lint"].metadata["effective_tool"] == "eslint"
    assert ci["npm run lint"].kind is VerificationKind.UNKNOWN  # matching only: what may run is unchanged
    assert not any(f.code == "LOCAL_CHECK_NOT_OBSERVED_IN_CI" for f in surface_findings(surface))
