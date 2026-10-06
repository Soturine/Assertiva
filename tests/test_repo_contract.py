import subprocess
import sys
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[1]


def test_repo_contract():
    result = subprocess.run([sys.executable, 'scripts/validate_repo.py'], capture_output=True, text=True)
    assert result.returncode == 0, result.stdout + result.stderr


def _ci():
    workflow = yaml.safe_load((ROOT / ".github" / "workflows" / "ci.yml").read_text(encoding="utf-8"))
    return workflow, workflow["jobs"]


def _script(job):
    return "\n".join(str(step.get("run", "")) for step in job["steps"])


def test_per_commit_ci_proves_the_essentials_without_recursive_self_qualification():
    _, jobs = _ci()
    commit_jobs = [job for job in jobs.values() if "if" not in job]
    script = "\n".join(_script(job) for job in commit_jobs)
    for required in (
        "scripts/validate_repo.py",
        '-m "not integration and not artifact"',  # fast/core suite
        '-m "(integration or artifact) and not browser and not jvm"',  # integration and artifact suites still run on every commit
        "python -m build --wheel",
        "/bin/assertiva\" audit",  # installed CLI smoke
        "--execute",  # read-only invariant with execution...
        "qualify-fixture",  # ...on a small generated fixture, not the whole repository
    ):
        assert required in script, required
    assert 'audit "$GITHUB_WORKSPACE" --execute' not in script


def test_full_self_dogfood_is_a_separate_on_demand_job():
    workflow, jobs = _ci()
    on = workflow.get("on") or workflow.get(True)  # YAML 1.1 reads the `on` key as True
    assert "workflow_dispatch" in on
    dogfood = [job for job in jobs.values() if 'audit "$GITHUB_WORKSPACE" --execute' in _script(job)]
    assert len(dogfood) == 1
    condition = dogfood[0]["if"]
    assert "workflow_dispatch" in condition and "refs/tags/v" in condition


def test_ci_installs_are_constrained_for_reproducibility():
    _, jobs = _ci()
    installs = [line for job in jobs.values() for line in _script(job).splitlines() if "pip install" in line]
    assert installs and all("constraints.txt" in line for line in installs), installs
    assert (ROOT / "constraints.txt").is_file()


def test_minimum_supported_python_runs_the_fast_suite():
    import re
    import tomllib

    requires = tomllib.loads((ROOT / "pyproject.toml").read_text(encoding="utf-8"))["project"]["requires-python"]
    minimum = re.search(r">=\s*(\d+\.\d+)", requires).group(1)
    _, jobs = _ci()
    matching = [
        job for job in jobs.values()
        if any(str((step.get("with") or {}).get("python-version")) == minimum for step in job["steps"])
    ]
    assert matching, f"no CI job runs Python {minimum} although requires-python is {requires}"
    assert any('-m "not integration and not artifact"' in _script(job) for job in matching)


def test_ci_checkouts_do_not_persist_credentials():
    _, jobs = _ci()
    checkouts = [step for job in jobs.values() for step in job["steps"] if str(step.get("uses", "")).startswith("actions/checkout")]
    assert checkouts and all((step.get("with") or {}).get("persist-credentials") is False for step in checkouts)


def test_ci_runs_the_js_adapter_against_a_real_runner_without_package_hooks():
    _, jobs = _ci()
    steps = [step for job in jobs.values() if "if" not in job for step in job["steps"]]
    installs = [str(step.get("run", "")) for step in steps if "npm ci" in str(step.get("run", ""))]
    assert installs and all("--ignore-scripts" in run and "tests/fixtures/js-" in run for run in installs)
    required = [step for step in steps if (step.get("env") or {}).get("ASSERTIVA_REQUIRE_JS") == "1"]
    assert any("integration" in str(step.get("run", "")) for step in required)  # JS tests may not silently skip in CI


def test_only_the_browser_job_downloads_a_browser_and_only_chromium():
    _, jobs = _ci()
    downloading = {name: job for name, job in jobs.items() if "cli.js install" in _script(job)}
    assert list(downloading) == ["browser"], list(downloading)
    script = _script(downloading["browser"])
    assert "--only-shell chromium" in script and "firefox" not in script and "webkit" not in script
    steps = downloading["browser"]["steps"]
    required = [step for step in steps if (step.get("env") or {}).get("ASSERTIVA_REQUIRE_PLAYWRIGHT") == "1"]
    assert any('-m browser' in str(step.get("run", "")) for step in required)  # may not silently skip
    assert "and not browser" in _script(jobs["validate"])  # the per-commit integration step never needs a browser


def test_only_the_java_job_needs_a_jdk_and_its_tests_cannot_skip():
    _, jobs = _ci()
    with_java = [name for name, job in jobs.items() if any(str(s.get("uses", "")).startswith("actions/setup-java") for s in job["steps"])]
    assert with_java == ["java"], with_java
    steps = jobs["java"]["steps"]
    required = [step for step in steps if (step.get("env") or {}).get("ASSERTIVA_REQUIRE_JAVA") == "1"]
    assert any("-m jvm" in str(step.get("run", "")) for step in required)
    assert "and not jvm" in _script(jobs["validate"])
