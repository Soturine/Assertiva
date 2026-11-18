"""An artifact build that could not import its build backend is attributed to the environment.

Found in the VozNativa v0.10 dogfood (2026-11-18): with build isolation disabled in the environment
(``PIP_NO_BUILD_ISOLATION``, which pip reads as *disable*), ``pip wheel`` ran in the project interpreter, which had no
``setuptools``. The audit reported ARTIFACT_QUALIFICATION_FAILED (high) with "fix packaging" for a project whose own
package gate builds the same wheel: a false red with a misleading recommendation.
"""

from types import SimpleNamespace

from assertiva.audit import _artifact_findings, environment_build_cause
from assertiva.models import StageStatus

BACKEND = 'exit 2 in 2.186s:   File "<frozen importlib._bootstrap>" | ModuleNotFoundError: No module named \'setuptools\''


def _check(detail: str):
    return SimpleNamespace(name="build wheel", status=StageStatus.FAIL, detail=detail)


def _current(*checks):
    artifact = SimpleNamespace(artifact=None, status=StageStatus.FAIL, checks=list(checks), omitted_files=[])
    return SimpleNamespace(artifacts=[artifact])


def test_missing_build_backend_is_the_environment(tmp_path):
    cause = environment_build_cause([_check(BACKEND)], tmp_path)
    assert cause is not None
    assert cause["origin"] == "ENVIRONMENT"
    assert cause["missing_build_backends"] == ["setuptools"]


def test_a_missing_project_module_is_not_decided(tmp_path):
    detail = "ModuleNotFoundError: No module named 'mypkg'"
    assert environment_build_cause([_check(detail)], tmp_path) is None


def test_a_backend_that_is_the_project_itself_is_not_decided(tmp_path):
    (tmp_path / "setuptools").mkdir()  # the project under audit is setuptools: its own import failed
    assert environment_build_cause([_check(BACKEND)], tmp_path) is None


def test_any_other_failure_leaves_it_undecided(tmp_path):
    other = "error: package directory 'src/mypkg' does not exist"
    assert environment_build_cause([_check(BACKEND), _check(other)], tmp_path) is None


def test_the_finding_carries_the_cause_and_a_matching_recommendation(tmp_path):
    finding = _artifact_findings(_current(_check(BACKEND)), tmp_path)[0]
    assert finding.code == "ARTIFACT_QUALIFICATION_FAILED"
    assert finding.evidence["dominant_cause"]["missing_build_backends"] == ["setuptools"]
    assert "build backend" in finding.recommendation and "PIP_NO_BUILD_ISOLATION" in finding.recommendation


def test_a_real_packaging_failure_keeps_the_packaging_recommendation(tmp_path):
    finding = _artifact_findings(_current(_check("error: package directory 'src/mypkg' does not exist")), tmp_path)[0]
    assert "dominant_cause" not in finding.evidence
    assert finding.recommendation is None  # the code's default (fix packaging) applies
