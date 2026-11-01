"""AXF-02 / DG-0101-02 / DG-0101-03 / DG-0101-08 / AXF-M3-01: every runner command of a CI step is a declared scope —
on several lines, after a literal `cd`, next to another runner — and a step that runs a repository script which runs
the tests is not "no tests in CI". Synthetic reproducers of the Derivanta Engine M1 C1 fixtures and M3 report."""

import pytest

from assertiva.pytest_audit import audit_pytest_project

from conftest import write

UT = "import unittest\nfrom lib import add\n\n\nclass T(unittest.TestCase):\n    def test_add(self):\n        self.assertEqual(add(1, 2), 3)\n"
PY = "from lib import add\n\n\ndef test_add():\n    assert add(1, 2) == 3\n"
LIB = "def add(a, b):\n    return a + b\n"


def project(root, run_lines, tests=None):
    files = tests or {"a/lib.py": LIB, "a/tests/test_a.py": UT, "b/lib.py": LIB, "b/tests/test_b.py": UT}
    for rel, text in files.items():
        write(root / rel, text)
    body = "".join(f"          {line}\n" for line in run_lines)
    write(root / ".github" / "workflows" / "ci.yml",
          "name: ci\non: push\njobs:\n  t:\n    runs-on: ubuntu-latest\n    steps:\n      - run: |\n" + body)
    return root


def codes(root):
    return {f.code: f for f in audit_pytest_project(root).findings}


def gap(root):
    found = codes(root).get("CI_TEST_EXECUTION_GAP")
    return found.evidence["unobserved_test_files"] if found else []


A = "python -m unittest discover -s a/tests -t a"
B = "python -m unittest discover -s b/tests -t b"


@pytest.mark.parametrize("lines", [[A, B], ["echo start", B, A]], ids=["both", "b-second"])
def test_every_unittest_line_of_a_multiline_step_is_a_ci_scope(tmp_path, lines):
    assert gap(project(tmp_path, lines)) == []  # 0.10.0: the second line's suite was a high CI_TEST_EXECUTION_GAP


def test_a_suite_no_line_runs_is_still_a_gap(tmp_path):
    assert gap(project(tmp_path, [A, "echo done"])) == ["b/tests/test_b.py"]  # negative control (c1-multiline-only-a)


def test_two_runners_in_one_step_each_declare_their_scope(tmp_path):
    tests = {"a/lib.py": LIB, "a/tests/test_a.py": PY.replace("from lib", "from lib"), "b/lib.py": LIB, "b/tests/test_b.py": UT}
    assert gap(project(tmp_path, ["python -m pytest a/tests && " + B], tests)) == []  # DG-0101-02


def test_a_literal_cd_moves_the_scope_and_an_unknown_one_claims_nothing(tmp_path):
    root = project(tmp_path / "lit", ["cd a && python -m unittest discover -s tests"])
    assert gap(root) == ["b/tests/test_b.py"]  # DG-0101-03: 0.10.0 read `tests` from the root and flagged both
    assert gap(project(tmp_path / "var", ["cd $SUITE && python -m unittest discover -s tests"])) == []  # unresolved: no claim


def test_a_comment_in_a_step_is_not_a_scope(tmp_path):
    root = project(tmp_path, ["python -m pytest a/tests  # b/tests runs nightly"])
    assert gap(root) == ["b/tests/test_b.py"]  # DG-0101-08: the comment's words were read as selected paths


# --- AXF-M3-01: tests run through a repository script --------------------------------------------------------------

GATE_RUNS = "import subprocess, sys\n\nsubprocess.run([sys.executable, '-m', 'pytest', '-q'], check=True)\n"


def script_project(root, script, command="python tools/gate.py"):
    write(root / "lib.py", LIB)
    write(root / "tests" / "test_lib.py", PY)
    write(root / "pyproject.toml", '[tool.pytest.ini_options]\npythonpath = ["."]\n')
    if script is not None:
        write(root / "tools" / "gate.py", script)
    write(root / ".github" / "workflows" / "ci.yml", "on: push\njobs:\n  t:\n    runs-on: ubuntu-latest\n    steps:\n"
          f"      - uses: actions/checkout@v4\n      - run: pip install pytest\n      - run: {command}\n")
    return root


def test_a_ci_script_that_runs_pytest_is_not_reported_as_no_pytest_in_ci(tmp_path):
    found = codes(script_project(tmp_path, GATE_RUNS))
    assert "CI_PYTEST_NOT_OBSERVED" not in found  # 0.10.0: medium finding recommending work already done
    through = found["CI_TESTS_RUN_THROUGH_SCRIPT"]
    assert through.severity == "info" and through.evidence["scripts"][0]["script"] == "tools/gate.py"


@pytest.mark.parametrize("script", [
    "import subprocess, sys\n\nsubprocess.run([sys.executable, '-m', 'ruff', 'check'], check=True)\n",
    "print('remember to run pytest')\n",  # mentions the runner, does not run it
], ids=["other-tool", "only-mentions"])
def test_a_ci_script_that_does_not_run_pytest_keeps_the_finding(tmp_path, script):
    assert "CI_PYTEST_NOT_OBSERVED" in codes(script_project(tmp_path, script))


def test_direct_pytest_in_ci_is_unchanged(tmp_path):
    found = codes(script_project(tmp_path, None, command="python -m pytest -q"))
    assert "CI_PYTEST_NOT_OBSERVED" not in found and "CI_TESTS_RUN_THROUGH_SCRIPT" not in found


def test_a_shell_script_that_runs_pytest_counts_and_a_commented_line_does_not(tmp_path):
    write(tmp_path / "a" / "ci" / "test.sh", "#!/bin/sh\nset -e\npython -m pytest -q\n")
    write(tmp_path / "b" / "ci" / "test.sh", "#!/bin/sh\n# pytest -q\necho skipped\n")
    assert "CI_TESTS_RUN_THROUGH_SCRIPT" in codes(script_project(tmp_path / "a", None, command="bash ci/test.sh"))
    assert "CI_PYTEST_NOT_OBSERVED" in codes(script_project(tmp_path / "b", None, command="bash ci/test.sh"))


# --- DG-0101-10 / DG-0101-11: pipes, redirections and discarded test status ---------------------------------------

from assertiva.adapters.commands import classify_command  # noqa: E402
from assertiva.verification import discover_surface, surface_findings  # noqa: E402


@pytest.mark.parametrize("command,args", [
    ("python -m pytest tests/unit | tee pytest.log", ("tests/unit",)),
    ("python -m pytest tests/unit 2>&1 | tail -5", ("tests/unit",)),
    ("pytest tests > out.txt", ("tests",)),
    ('pytest -k "a|b" tests', ("-k", "a|b", "tests")),  # a quoted | is an argument
])
def test_pipes_and_redirections_are_not_runner_arguments(command, args):
    assert classify_command(command).runner_args == args  # 0.10.0: tee, pytest.log, 2>&1, tail were scopes


def masked(root, run, shell=None, runs_on="ubuntu-latest"):
    step = f"      - run: {run}\n" + (f"        shell: {shell}\n" if shell else "")
    write(root / ".github" / "workflows" / "ci.yml", f"on: push\njobs:\n  t:\n    runs-on: {runs_on}\n    steps:\n" + step)
    write(root / "tests" / "test_x.py", "def test_x():\n    assert 1 + 1 == 2\n")
    return next((f for f in surface_findings(discover_surface(root)) if f.code == "CI_TEST_STATUS_MASKED"), None)


def test_a_piped_test_command_in_the_default_shell_discards_its_status(tmp_path):
    found = masked(tmp_path, "python -m pytest | tee pytest.log")
    assert found is not None and found.evidence["steps"][0]["how"] == "a pipe in a shell without pipefail"


@pytest.mark.parametrize("run", ["python -m pytest || true", "python -m pytest || echo tests failed", "python -m pytest || exit 0"])
def test_or_true_after_tests_discards_the_status_in_any_shell(tmp_path, run):
    found = masked(tmp_path, run, shell="bash")
    assert found is not None and "|| true" in found.evidence["steps"][0]["how"]


@pytest.mark.parametrize("run,shell,runs_on", [
    ("python -m pytest | tee pytest.log", "bash", "ubuntu-latest"),  # explicit bash: -eo pipefail
    ("set -o pipefail; python -m pytest | tee pytest.log", None, "ubuntu-latest"),
    ("python -m pytest | tee pytest.log", None, "windows-latest"),  # pwsh: not decided here
    ("python -m pytest | tee pytest.log", None, "${{ matrix.os }}"),  # unknown runner: no claim
    ("pip list | grep pytest", None, "ubuntu-latest"),  # not a test command
    ("python -m pytest || exit 1", None, "ubuntu-latest"),  # the failure is kept
], ids=["explicit-bash", "set-pipefail", "windows", "matrix-os", "not-a-test", "or-exit-1"])
def test_status_masking_is_not_claimed_where_the_shell_keeps_it_or_cannot_be_decided(tmp_path, run, shell, runs_on):
    assert masked(tmp_path, run, shell, runs_on) is None
