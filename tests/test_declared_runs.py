"""AXF-01: --python is resolved once against the invocation directory, so a relative interpreter works wherever the
children run, and a missing one is refused with exit 2, not a traceback.
AXF-05: several declared `unittest discover -s` invocations are reproduced one by one; zero tests is never a pass.
Synthetic reproducers of the Derivanta Engine M1 report (Framework 218761d: five CI start directories, 79 tests,
0.10.0 ran `discover` at the root and executed 0)."""

import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

from assertiva import cli
from assertiva.adapters.unittest_native import UnittestAdapter
from assertiva.process import resolve_interpreter

from conftest import write


# --- AXF-01 ------------------------------------------------------------------------------------------------------

def test_a_relative_interpreter_is_resolved_against_the_invocation_directory(tmp_path):
    folder = tmp_path / "with space" / "Scripts"
    folder.mkdir(parents=True)
    fake = folder / "python.exe"
    fake.write_bytes(b"")
    fake.chmod(0o755)
    resolved = resolve_interpreter("with space/Scripts/python.exe", base=tmp_path)
    assert Path(resolved).is_absolute() and Path(resolved) == fake


def test_a_bare_name_is_looked_up_on_path(monkeypatch):
    monkeypatch.setenv("PATH", str(Path(sys.executable).parent))
    assert Path(resolve_interpreter(Path(sys.executable).stem)).resolve() == Path(sys.executable).resolve()


@pytest.mark.parametrize("value", ["missing/python.exe", ".", "no-such-python-3x"])
def test_a_missing_interpreter_is_refused_without_running_anything(tmp_path, value):
    with pytest.raises(ValueError):
        resolve_interpreter(value, base=tmp_path)


def test_the_cli_refuses_a_missing_interpreter_with_exit_2_and_a_message(tmp_path, capsys, monkeypatch):
    write(tmp_path / "tests" / "test_x.py", "def test_x():\n    assert 1 + 1 == 2\n")
    monkeypatch.chdir(tmp_path)
    with pytest.raises(SystemExit) as exited:
        cli.main(["audit", ".", "--python", "missing/python.exe", "--dependencies"])
    err = capsys.readouterr().err
    assert exited.value.code == 2 and "no interpreter at" in err and "Traceback" not in err


@pytest.mark.integration
def test_a_relative_venv_interpreter_works_with_dependencies(tmp_path):
    root = tmp_path / "proj"
    write(root / "pyproject.toml", '[project]\nname = "d"\nversion = "1"\ndependencies = ["pyyaml"]\n')
    write(root / "d" / "__init__.py", "")
    write(root / "tests" / "test_d.py", "def test_x():\n    assert 1 + 1 == 2\n")
    subprocess.run([sys.executable, "-m", "venv", "--without-pip", "--system-site-packages", str(root / ".venv")], check=True)
    relative = ".venv/Scripts/python.exe" if os.name == "nt" else ".venv/bin/python"
    done = subprocess.run([sys.executable, "-m", "assertiva.cli", "audit", ".", "--python", relative, "--dependencies",
                           "--output", "json"], cwd=root, capture_output=True, text=True,
                          env={**os.environ, "ASSERTIVA_HOME": str(tmp_path / "home"),
                               "PYTHONPATH": str(Path(__file__).parents[1])})
    assert done.returncode == 0, done.stderr[-500:]  # 0.10.0: FileNotFoundError traceback, exit 1
    assert json.loads(done.stdout)["dependencies"]["dependencies"][0]["name"] == "pyyaml"


# --- AXF-05 ------------------------------------------------------------------------------------------------------

def suites(root, steps, counts, failing=()):
    for name, n in counts.items():
        body = "import unittest\n\n\nclass T(unittest.TestCase):\n" + "".join(
            f"    def test_{i}(self):\n        self.assertEqual({i} + 1, {i + (2 if (name, i) in failing else 1)})\n" for i in range(n))
        write(root / name / "tests" / f"test_{name}.py", body if n else "import unittest\n")
    write(root / ".github" / "workflows" / "ci.yml", "name: ci\non: push\njobs:\n  t:\n    runs-on: ubuntu-latest\n    steps:\n"
          + "".join("      - run: |\n" + "".join(f"          {line}\n" for line in step) for step in steps))
    return root


def discover(name):
    return f"python -m unittest discover -s {name}/tests -p 'test_*.py' -v"


@pytest.mark.integration
def test_every_declared_start_directory_runs_and_a_failure_stays_a_failure(tmp_path):
    root = suites(tmp_path, [[discover("suite_a"), "python suite_a/check.py"], [discover("suite_b")],
                             [discover("suite_b"), discover("suite_c")]],  # suite_b declared twice: run once
                  {"suite_a": 3, "suite_b": 2, "suite_c": 1}, failing={("suite_c", 0)})
    run = UnittestAdapter(python=sys.executable).run(root)
    assert run.status.value == "FAIL" and len(run.invocations) == 6  # 0.10.0: root discover, 0 tests, UNKNOWN
    parts = run.metadata["declared_invocations"]
    assert [(p["directory"], p["status"], p["invocations"]) for p in parts] == [(".", "PASS", 3), (".", "PASS", 2), (".", "FAIL", 1)]
    assert {i.invocation_id.split("::")[0] for i in run.invocations} == {f"suite_{s}/tests/test_suite_{s}.py" for s in "abc"}


@pytest.mark.integration
def test_all_declared_suites_passing_is_a_pass_and_one_empty_suite_is_not(tmp_path):
    ok = UnittestAdapter(python=sys.executable).run(suites(tmp_path / "ok", [[discover("x"), discover("y")]], {"x": 2, "y": 1}))
    assert ok.status.value == "PASS" and len(ok.invocations) == 3
    empty = UnittestAdapter(python=sys.executable).run(suites(tmp_path / "empty", [[discover("x"), discover("y")]], {"x": 2, "y": 0}))
    assert empty.status.value == "UNKNOWN" and len(empty.invocations) == 2  # the y suite executed nothing
    assert any("executed no test" in lim for lim in empty.limitations)


@pytest.mark.integration
def test_a_declared_invocation_in_another_directory_is_not_run_and_keeps_the_run_from_passing(tmp_path):
    root = suites(tmp_path, [[discover("x"), "cd y && python -m unittest discover -s tests"]], {"x": 1, "y": 1})
    run = UnittestAdapter(python=sys.executable).run(root)
    assert [p["status"] for p in run.metadata["declared_invocations"]] == ["PASS", "NOT_RUN"]
    assert run.status.value == "UNKNOWN" and any("not reproduced" in lim for lim in run.limitations)


def test_one_declared_invocation_keeps_the_single_run_behavior(tmp_path):
    root = suites(tmp_path, [[discover("x")]], {"x": 1})
    args, source = UnittestAdapter(python=sys.executable)._declared_args(root)
    assert args[:3] == ["discover", "-s", "x/tests"] and source == discover("x")
