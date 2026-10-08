"""Optional project configuration: small, owned by the project, never required, never guessed."""

import sys

from assertiva.adapters import runner_adapters
from assertiva.config import load_config
from conftest import write

_CASE = "import unittest\n\n\nclass T(unittest.TestCase):\n    def test_x(self):\n        self.assertEqual(1, 1)\n"


def test_no_file_is_the_default_and_detection_decides(tmp_path):
    write(tmp_path / "tests" / "test_x.py", _CASE)
    config = load_config(tmp_path)
    assert config.source is None and not config.runners and not config.problems
    assert [a.adapter_id for a in runner_adapters(tmp_path, sys.executable)] == ["pytest-native"]


def test_configured_runners_replace_detection_and_the_budget_applies(tmp_path):
    write(tmp_path / "tests" / "test_x.py", _CASE)
    write(tmp_path / ".assertiva.toml", '[tests]\nrunners = ["unittest"]\ntimeout_s = 1800\n')
    [adapter] = runner_adapters(tmp_path, sys.executable)
    assert adapter.adapter_id == "unittest" and adapter.timeout_s == 1800


def test_pyproject_tool_table_is_read_when_there_is_no_file(tmp_path):
    write(tmp_path / "pyproject.toml", '[project]\nname = "x"\n\n[tool.assertiva.tests]\nrunners = ["unittest"]\n')
    config = load_config(tmp_path)
    assert config.source == "pyproject.toml [tool.assertiva]" and config.runners == ("unittest",)


def test_consent_is_never_read_from_the_project_only_from_the_users_home(tmp_path, assertiva_home):
    project = tmp_path / "p"
    write(project / "pyproject.toml", '[tool.assertiva.execution]\nenv = ["DATABASE_URL"]\nauthorize = ["make seed"]\n')
    config = load_config(project)
    assert config.env == () and config.authorize == ()
    assert "execution.env is not read from the project; consent belongs in <ASSERTIVA_HOME>/consent.toml" in config.problems
    write(assertiva_home / "consent.toml", f'[[project]]\nroot = {str(project.resolve())!r}\nenv = ["DATABASE_URL"]\nauthorize = ["make seed"]\n'
                                             f'\n[[project]]\nroot = {str((tmp_path / "other").resolve())!r}\nenv = ["X"]\n')
    config = load_config(project)
    assert config.env == ("DATABASE_URL",) and config.authorize == ("make seed",)


def test_unknown_or_malformed_entries_are_reported_never_guessed(tmp_path):
    write(tmp_path / ".assertiva.toml", '[tests]\nrunners = ["nose", "pytest"]\ntimeout_s = "long"\ncolor = 1\n\n'
                                        '[execution]\nauthorize = "everything"\n\n[deploy]\nenabled = true\n')
    config = load_config(tmp_path)
    assert config.runners == ("pytest",) and config.timeout_s is None and config.authorize == ()
    assert set(config.problems) == {
        "unknown section [deploy] ignored", "unknown key tests.color ignored", "unknown runner 'nose' in tests.runners ignored",
        "tests.timeout_s must be a positive number; ignored",
        "execution.authorize is not read from the project; consent belongs in <ASSERTIVA_HOME>/consent.toml",
    }


def test_an_unreadable_file_is_a_reported_problem(tmp_path):
    write(tmp_path / ".assertiva.toml", "[tests\n")
    config = load_config(tmp_path)
    assert config.problems and "could not be read" in config.problems[0] and not config.runners


def test_configuration_problems_reach_the_audit_report(tmp_path):
    from assertiva.audit import run_audit

    write(tmp_path / "tests" / "test_x.py", _CASE)
    write(tmp_path / ".assertiva.toml", "[tests]\nspeed = 3\n")
    report = run_audit(tmp_path)
    assert "configuration (.assertiva.toml): unknown key tests.speed ignored" in report["claim_boundary"]["limitations"]
