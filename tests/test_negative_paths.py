"""Negative-path depth: 'some error happened' is not 'the failure contract is protected'."""

import sys

import pytest

from assertiva.candidate import DeltaState, QualificationStage, StageStatus
from assertiva.improve import discard_session, qualify_candidate, start_improve
from assertiva.pytest_audit import audit_pytest_project, discover_pytest_definitions

from conftest import write

HEADER = "import asyncio\nimport pytest\n\nclass ValidationError(Exception):\n    def __init__(self, code='', field=''):\n        self.code, self.field = code, field\n\n"


def dims(tmp_path, body):
    write(tmp_path / "tests" / "test_neg.py", HEADER + body)
    return {t.name: t.negative_dims for t in discover_pytest_definitions(tmp_path)}


def test_specific_exception_type_is_observed(tmp_path):
    assert dims(tmp_path, "def test_x():\n    with pytest.raises(ValueError):\n        int('x')\n")["test_x"] == ("ERROR_TYPE",)


def test_broad_exception_is_not_an_error_type_contract(tmp_path):
    assert dims(tmp_path, "def test_x():\n    with pytest.raises(Exception):\n        int('x')\n")["test_x"] == ()


def test_message_match_is_observed(tmp_path):
    found = dims(tmp_path, "def test_x():\n    with pytest.raises(ValueError, match='invalid literal'):\n        int('x')\n")
    assert found["test_x"] == ("ERROR_TYPE", "MESSAGE")


def test_status_only_is_only_protocol_status(tmp_path):
    body = "class R:\n    status_code = 422\n\ndef test_x():\n    r = R()\n    assert r.status_code == 422\n"
    assert dims(tmp_path, body)["test_x"] == ("PROTOCOL_STATUS",)


def test_structured_machine_code_and_field_are_observed(tmp_path):
    body = (
        "def register(email):\n    raise ValidationError('INVALID_EMAIL', 'email')\n\n"
        "def test_x():\n    with pytest.raises(ValidationError) as excinfo:\n        register('nope')\n"
        "    assert excinfo.value.code == 'INVALID_EMAIL'\n    assert excinfo.value.field == 'email'\n"
    )
    assert dims(tmp_path, body)["test_x"] == ("ERROR_TYPE", "MACHINE_CODE", "FIELD_OR_PATH")


def test_status_plus_structured_body_is_not_status_only(tmp_path):
    body = (
        "class R:\n    status_code = 422\n    def json(self):\n        return {'errors': [{'code': 'REQUIRED', 'field': 'email'}]}\n\n"
        "def test_x():\n    r = R()\n    assert r.status_code == 422\n"
        "    assert r.json()['errors'][0]['code'] == 'REQUIRED'\n    assert r.json()['errors'][0]['field'] == 'email'\n"
    )
    write(tmp_path / "tests" / "test_neg.py", HEADER + body)
    [test] = discover_pytest_definitions(tmp_path)
    assert test.negative_dims == ("MACHINE_CODE", "FIELD_OR_PATH", "STRUCTURED_CONTEXT", "PROTOCOL_STATUS")
    assert not audit_pytest_project(tmp_path).has_finding("ERROR_STATUS_ONLY_SIGNAL")


def test_multiple_validation_errors_are_structured_context(tmp_path):
    body = (
        "class Many(Exception):\n    def errors(self):\n        return [1, 2]\n\n"
        "def test_x():\n    with pytest.raises(Many) as excinfo:\n        raise Many()\n    assert len(excinfo.value.errors()) == 2\n"
    )
    assert dims(tmp_path, body)["test_x"] == ("ERROR_TYPE", "STRUCTURED_CONTEXT")


def test_assertion_after_rejection_is_a_state_signal_not_rollback_proof(tmp_path):
    body = (
        "store = []\n\ndef add(item):\n    if not item:\n        raise ValueError('empty')\n    store.append(item)\n\n"
        "def test_x():\n    before = len(store)\n    with pytest.raises(ValueError):\n        add('')\n    assert len(store) == before\n"
    )
    found = dims(tmp_path, body)["test_x"]
    assert found == ("ERROR_TYPE", "STATE_AFTER_REJECTION")
    assert "ROLLBACK" not in found


def test_awaited_async_failure_is_observed(tmp_path):
    body = "async def fail():\n    raise ValueError()\n\nasync def test_x():\n    with pytest.raises(ValueError):\n        await fail()\n"
    assert dims(tmp_path, body)["test_x"] == ("ERROR_TYPE", "ASYNC_OBSERVED")


def test_async_failure_created_but_never_observed_is_flagged(tmp_path):
    body = "async def fail():\n    raise ValueError()\n\nasync def test_x():\n    task = asyncio.create_task(fail())\n    assert task is not None\n"
    write(tmp_path / "tests" / "test_neg.py", HEADER + body)
    finding = next(f for f in audit_pytest_project(tmp_path).findings if f.code == "ASYNC_FAILURE_NOT_OBSERVED")
    assert finding.evidence["tests"] == ["tests/test_neg.py::test_x"]


def test_awaited_task_is_not_flagged(tmp_path):
    body = "async def ok():\n    return 1\n\nasync def test_x():\n    task = asyncio.create_task(ok())\n    assert await task == 1\n"
    write(tmp_path / "tests" / "test_neg.py", HEADER + body)
    assert not audit_pytest_project(tmp_path).has_finding("ASYNC_FAILURE_NOT_OBSERVED")


def test_contract_field_finding_requires_evidence_that_the_contract_has_fields(tmp_path):
    type_only = "def test_type_only():\n    with pytest.raises(ValidationError):\n        raise ValidationError('X', 'y')\n"
    write(tmp_path / "tests" / "test_neg.py", HEADER + type_only)
    assert not audit_pytest_project(tmp_path).has_finding("ERROR_CONTRACT_FIELD_NOT_OBSERVED")  # not universal

    with_code = (
        "def test_with_code():\n    with pytest.raises(ValidationError) as e:\n        raise ValidationError('X', 'y')\n"
        "    assert e.value.code == 'X'\n\n"
    )
    write(tmp_path / "tests" / "test_neg.py", HEADER + with_code + type_only)
    finding = next(f for f in audit_pytest_project(tmp_path).findings if f.code == "ERROR_CONTRACT_FIELD_NOT_OBSERVED")
    assert finding.evidence["tests"] == ["tests/test_neg.py::test_type_only"]
    assert finding.evidence["error_types"] == ["ValidationError"]


def test_state_after_rejection_finding_only_when_the_suite_shows_the_practice(tmp_path):
    no_state = "def test_a():\n    with pytest.raises(ValueError):\n        int('x')\n"
    write(tmp_path / "tests" / "test_neg.py", HEADER + no_state)
    assert not audit_pytest_project(tmp_path).has_finding("STATE_AFTER_REJECTION_NOT_EVIDENCED")
    with_state = "items = []\n\ndef test_b():\n    with pytest.raises(ValueError):\n        int('x')\n    assert items == []\n\n"
    write(tmp_path / "tests" / "test_neg.py", HEADER + with_state + no_state)
    finding = next(f for f in audit_pytest_project(tmp_path).findings if f.code == "STATE_AFTER_REJECTION_NOT_EVIDENCED")
    assert finding.evidence["tests"] == ["tests/test_neg.py::test_a"]


# --- qualification -----------------------------------------------------------------

NEG_PROJECT = (
    "class SignupError(Exception):\n    def __init__(self, code):\n        self.code = code\n\n"
    "users = []\n\ndef signup(email):\n    if '@' not in email:\n        raise SignupError('INVALID_EMAIL')\n    users.append(email)\n"
)
WEAK_TEST = "import pytest\nfrom app import signup, SignupError\n\ndef test_rejects_bad_email():\n    with pytest.raises(SignupError):\n        signup('nope')\n"
STRONG_TEST = (
    "import pytest\nfrom app import signup, SignupError, users\n\ndef test_rejects_bad_email():\n    before = list(users)\n"
    "    with pytest.raises(SignupError) as excinfo:\n        signup('nope')\n    assert excinfo.value.code == 'INVALID_EMAIL'\n    assert users == before\n"
)


@pytest.fixture
def neg_session(tmp_path):
    root = tmp_path / "neg"
    write(root / "app.py", NEG_PROJECT)
    write(root / "conftest.py", "")
    write(root / "tests" / "test_signup.py", WEAK_TEST)
    session = start_improve(root, python=sys.executable)
    yield session
    discard_session(session)


def stage(q):
    return next(s for s in q.stages if s.stage is QualificationStage.NEGATIVE_PATHS)


def test_strengthened_negative_path_passes_stage(neg_session):
    (neg_session.workspace / "tests" / "test_signup.py").write_text(STRONG_TEST, encoding="utf-8")
    q = qualify_candidate(neg_session).qualification
    result = stage(q)
    assert result.status is StageStatus.PASS, result
    assert "MACHINE_CODE" in result.summary and "STATE_AFTER_REJECTION" in result.summary
    assert any("E3" in item for item in result.limitations)  # static provenance stays visible
    assert next(d for d in q.metric_deltas if d.name == "negative_paths_without_contract_detail").state is DeltaState.IMPROVED


def test_broadened_expectation_fails_stage(neg_session):
    (neg_session.workspace / "tests" / "test_signup.py").write_text(WEAK_TEST.replace("pytest.raises(SignupError)", "pytest.raises(Exception)"), encoding="utf-8")
    assert stage(qualify_candidate(neg_session).qualification).status is StageStatus.FAIL


def test_untouched_negative_paths_stay_unknown(neg_session):
    write(neg_session.workspace / "tests" / "test_other.py", "def test_other():\n    assert 1 + 1 == 2\n")
    assert stage(qualify_candidate(neg_session).qualification).status is StageStatus.UNKNOWN


def test_report_shows_negative_path_dimensions_per_state(neg_session):
    from assertiva.report import improve_report, render_html

    (neg_session.workspace / "tests" / "test_signup.py").write_text(STRONG_TEST, encoding="utf-8")
    result = qualify_candidate(neg_session)
    report = improve_report(neg_session, result)
    key = "tests/test_signup.py::test_rejects_bad_email"
    assert report["states"]["baseline"]["negative_paths"][key] == ["ERROR_TYPE"]
    assert report["states"]["candidate"]["negative_paths"][key] == ["ERROR_TYPE", "MACHINE_CODE", "STATE_AFTER_REJECTION"]
    assert 'id="negative-paths"' in render_html(report)
