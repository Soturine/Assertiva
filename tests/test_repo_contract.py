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
    assert len(commit_jobs) == 1
    script = _script(commit_jobs[0])
    for required in (
        "scripts/validate_repo.py",
        '-m "not integration and not artifact"',  # fast/core suite
        '-m "integration or artifact"',  # integration and artifact suites still run on every commit
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
