"""Fail-before / pass-after probes for the Derivanta dogfood findings (synthetic fixtures only).

Rebuilds the reproducers of the Derivanta Engine intakes (PR #3, PR #4) from their written descriptions and records
what `assertiva audit` reports for each. Run from the repository root (or with the checkout on PYTHONPATH):

    python benchmarks/derivanta_probes.py OUT_DIR   # one line per probe; OUT_DIR/results.json

AXF-05 runs the fixture's own unittest suites (`--execute`, synthetic code only).
"""
import json
import os
import subprocess
import sys
from pathlib import Path

BASE = Path(sys.argv[1]).resolve()
FIX = BASE / "fixtures"


def project(name, files):
    root = FIX / name
    if root.exists():
        import shutil
        shutil.rmtree(root)
    for rel, text in files.items():
        p = root / rel
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(text, encoding="utf-8")
    return root


def audit(root, *extra, cwd=None):
    done = subprocess.run([sys.executable, "-m", "assertiva.cli", "audit", str(root), "--output", "json", *extra],
                          capture_output=True, text=True, cwd=cwd, check=False, env={**os.environ, "ASSERTIVA_HOME": str(BASE / "home")})
    try:
        report = json.loads(done.stdout)
    except ValueError:
        report = None
    return done.returncode, report, done.stderr.strip().splitlines()[-1:] if done.stderr.strip() else []


def codes(report):
    return sorted({f["code"] for f in report["findings"]}) if report else None


def finding(report, code):
    return next((f for f in report["findings"] if f["code"] == code), None) if report else None


def candidates(report, kind):
    eff = (report or {}).get("test_effectiveness") or {}
    return [c for c in eff.get("candidates", []) if c.get("kind") == kind]


results = {}

# --- AXF-02: multi-line run step with two unittest discover commands (M1 C1 trio, rebuilt)
UT = "import unittest\nfrom lib import add\nclass T(unittest.TestCase):\n    def test_add(self):\n        self.assertEqual(add(1, 2), 3)\n"
LIB = "def add(a, b):\n    return a + b\n"
WF = "name: ci\non: push\njobs:\n  t:\n    runs-on: ubuntu-latest\n    steps:\n      - run: |\n{body}"
common = {"a/lib.py": LIB, "a/tests/test_a.py": UT, "b/lib.py": LIB, "b/tests/test_b.py": UT}
bodies = {
    "c1-multiline-both": "          python -m unittest discover -s a/tests -t a\n          python -m unittest discover -s b/tests -t b\n",
    "c1-multiline-only-a": "          python -m unittest discover -s a/tests -t a\n          echo done\n",
    "c1-multiline-b-second": "          echo start\n          python -m unittest discover -s b/tests -t b\n          python -m unittest discover -s a/tests -t a\n",
}
for name, body in bodies.items():
    rc, report, _ = audit(project(name, {**common, ".github/workflows/ci.yml": WF.format(body=body)}))
    gap = finding(report, "CI_TEST_EXECUTION_GAP")
    redundancy = candidates(report, "REDUNDANCY")
    results[f"AXF-02/{name}"] = {"exit": rc, "gap": gap and gap["evidence"].get("unobserved_test_files"),
                                 "redundancy_candidates": [c["tests"] for c in redundancy]}

# --- AXF-07 is visible on c1-multiline-both (different lib modules, identical bodies): recorded above

# --- AXF-03: determinism direct vs assigned
det = project("c2-determinism", {
    "lib.py": "def f(x):\n    return x * 2\n",
    "tests/test_det.py": "from lib import f\n\ndef test_direct():\n    assert f(3) == f(3)\n\n"
                         "def test_assigned():\n    a = f(3)\n    assert a == f(3)\n\ndef test_value():\n    assert f(3) == 6\n",
    "pyproject.toml": '[tool.pytest.ini_options]\npythonpath = ["."]\n'})
rc, report, _ = audit(det)
results["AXF-03"] = {"exit": rc, "false_green": [(c["detail"].get("pattern"), c["tests"]) for c in candidates(report, "FALSE_GREEN")],
                     "weak": [(c["detail"].get("oracles"), c["tests"]) for c in candidates(report, "WEAK_ORACLE")]}

# --- AXF-M2-01: assert ... or True
taut = project("m2-or-true", {
    "lib.py": "def add(a, b):\n    return a + b\n",
    "tests/test_add.py": "from lib import add\n\ndef test_always_passes():\n    assert add(1, 2) == 4 or True\n\n"
                         "def test_control():\n    assert add(1, 2) == 3\n\ndef test_existing_positive():\n    assert True\n",
    "pyproject.toml": '[tool.pytest.ini_options]\npythonpath = ["."]\n'})
rc, report, _ = audit(taut)
results["AXF-M2-01"] = {"exit": rc, "false_green": [(c["detail"].get("pattern"), c["tests"]) for c in candidates(report, "FALSE_GREEN")]}

# --- AXF-06: typed exception boundary
typed = project("axf06-typed", {
    "lib.py": "class DecodeError(ValueError):\n    pass\n\ndef decode(data):\n    if not data:\n        raise DecodeError('empty')\n    return data[0]\n",
    "tests/test_decode.py": "from lib import decode, DecodeError\n\n"
                            "def test_never_escapes_typed_errors():\n    for data in (b'', b'x'):\n        try:\n            decode(data)\n"
                            "        except (DecodeError, TypeError):\n            pass\n\n"
                            "def test_swallows_everything():\n    try:\n        decode(b'')\n    except Exception:\n        pass\n",
    "pyproject.toml": '[tool.pytest.ini_options]\npythonpath = ["."]\n'})
rc, report, _ = audit(typed)
results["AXF-06"] = {"exit": rc, "codes": codes(report),
                     "false_green": [(c["detail"].get("pattern"), c["tests"]) for c in candidates(report, "FALSE_GREEN")],
                     "no_assertion": (finding(report, "NO_ASSERTION_SIGNAL") or finding(report, "TESTS_WITHOUT_ASSERTIONS") or {}).get("evidence")}

# --- AXF-M3-01: CI runs pytest through a repository script
gate_wf = "name: ci\non: push\njobs:\n  t:\n    runs-on: ubuntu-latest\n    steps:\n      - uses: actions/checkout@v4\n      - run: pip install pytest\n      - run: {cmd}\n"
pyfiles = {"lib.py": LIB, "tests/test_lib.py": "from lib import add\n\ndef test_add():\n    assert add(1, 2) == 3\n",
           "pyproject.toml": '[tool.pytest.ini_options]\npythonpath = ["."]\n'}
for name, cmd, script in [
    ("m3-indirect", "python tools/gate.py", "import subprocess, sys\nsubprocess.run([sys.executable, '-m', 'pytest', '-q'], check=True)\n"),
    ("m3-direct", "python -m pytest -q", None),
    ("m3-indirect-no-pytest", "python tools/gate.py", "import subprocess, sys\nsubprocess.run([sys.executable, '-m', 'ruff', 'check'], check=True)\n"),
]:
    files = {**pyfiles, ".github/workflows/ci.yml": gate_wf.format(cmd=cmd)}
    if script:
        files["tools/gate.py"] = script
    rc, report, _ = audit(project(name, files))
    results[f"AXF-M3-01/{name}"] = {"exit": rc, "ci_pytest_not_observed": finding(report, "CI_PYTEST_NOT_OBSERVED") is not None}

# --- AXF-M3-02: error contract wording
err = project("m3-error-contract", {
    "lib.py": "class AppError(Exception):\n    def __init__(self, code, exit_code):\n        self.code, self.exit_code = code, exit_code\n"
              "    def payload(self):\n        return {'code': self.code}\n\ndef run(x):\n    raise AppError('E_BAD', 2)\n",
    "tests/test_err.py": "import pytest\nfrom lib import run, AppError\n\n"
                         "def test_code_pinned():\n    with pytest.raises(AppError) as raised:\n        run(1)\n    assert raised.value.code == 'E_BAD'\n\n"
                         "def test_exit_code_only():\n    with pytest.raises(AppError) as raised:\n        run(2)\n    assert raised.value.exit_code == 2\n\n"
                         "def test_type_only():\n    with pytest.raises(AppError):\n        run(3)\n",
    "pyproject.toml": '[tool.pytest.ini_options]\npythonpath = ["."]\n'})
rc, report, _ = audit(err)
f = finding(report, "ERROR_CONTRACT_FIELD_NOT_OBSERVED")
results["AXF-M3-02"] = {"exit": rc, "summary": f and f["summary"], "evidence": f and f["evidence"]}

# --- AXF-01: relative --python with --dependencies (and --execute)
dep = project("axf01-deps", {"pyproject.toml": '[project]\nname = "d"\nversion = "1"\ndependencies = ["pyyaml"]\n',
                             "d/__init__.py": "", "tests/test_d.py": "def test_x():\n    assert 1 + 1 == 2\n"})
subprocess.run([sys.executable, "-m", "venv", "--without-pip", "--system-site-packages", str(dep / ".venv")], check=True)
venv_py = dep / ".venv" / ("Scripts/python.exe" if os.name == "nt" else "bin/python")
rel = os.path.relpath(venv_py, dep).replace("\\", "/")
rc, report, err_tail = audit(".", "--python", rel, "--dependencies", cwd=dep)
results["AXF-01/relative"] = {"exit": rc, "report": report is not None, "stderr_tail": err_tail}
rc, report, err_tail = audit(".", "--python", str(venv_py), "--dependencies", cwd=dep)
results["AXF-01/absolute"] = {"exit": rc, "report": report is not None}
rc, report, err_tail = audit(".", "--python", "missing/python.exe", "--dependencies", cwd=dep)
results["AXF-01/missing"] = {"exit": rc, "report": report is not None, "stderr_tail": err_tail}

# --- AXF-05: several declared unittest start directories, non-package, executed
ut5 = {".github/workflows/ci.yml": "name: ci\non: push\njobs:\n  t:\n    runs-on: ubuntu-latest\n    steps:\n"
       "      - run: |\n          python -m unittest discover -s suite_a/tests -p 'test_*.py' -v\n          python suite_a/check.py\n"
       "      - run: |\n          python -m unittest discover -s suite_b/tests -p 'test_*.py' -v\n"
       "      - run: |\n          python -m unittest discover -s suite_b/tests -p 'test_*.py' -v\n          python -m unittest discover -s suite_c/tests -p 'test_*.py' -v\n"}
for s, n in (("suite_a", 3), ("suite_b", 2), ("suite_c", 1)):
    body = "import unittest\n\nclass T(unittest.TestCase):\n" + "".join(f"    def test_{i}(self):\n        self.assertEqual({i} + 1, {i + 1})\n" for i in range(n))
    ut5[f"{s}/tests/test_{s}.py"] = body
ut5["suite_c/tests/test_suite_c.py"] = ut5["suite_c/tests/test_suite_c.py"].replace("self.assertEqual(0 + 1, 1)", "self.assertEqual(0 + 1, 2)")
rc, report, _ = audit(project("axf05-unittest-roots", ut5), "--execute")
runs = (report or {}).get("states", {}).get("current", {}).get("runs", [])
results["AXF-05"] = {"exit": rc, "status": report and report.get("status"),
                     "runs": [{"adapter": r.get("adapter"), "status": r.get("status"), "invocations": r.get("invocations"), "exit_code": r.get("exit_code"), "limitations": r.get("limitations")} for r in runs]}

out = BASE / "results.json"
out.write_text(json.dumps(results, indent=1), encoding="utf-8")
for key, value in results.items():
    print(key, json.dumps(value)[:600])
