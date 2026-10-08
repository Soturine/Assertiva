"""GitHub Actions adapter: workflow files -> declared CI VerificationChecks.

Declared configuration (E2), not run evidence: a workflow containing a step does not
prove that the step ran, ran on this revision, or gated a merge. Reusable workflows,
composite actions and expressions are preserved, not interpreted.
"""

from __future__ import annotations

from pathlib import Path

import yaml

from assertiva.verification import GateMode, SupportLevel, VerificationCheck

from .ci_common import command_check, matrix_values, merge_values, opaque_check, unreadable_check

_SETUP_ACTIONS = ("actions/checkout", "actions/setup-", "actions/cache", "actions/upload-artifact", "actions/download-artifact")
_SETUP_VERSIONS = {"actions/setup-python": ("python", "python-version"), "actions/setup-node": ("node", "node-version"),
                   "actions/setup-java": ("java", "java-version")}


def _gate(*continue_on_error) -> GateMode:
    # Whether a failing job blocks a merge depends on branch protection, which is not in
    # the repository; expression-valued continue-on-error is not evaluated either.
    return GateMode.ALLOWED_FAILURE if any(value is True for value in continue_on_error) else GateMode.UNKNOWN


class GitHubActionsAdapter:
    adapter_id = "github-actions"

    def supports(self, root: Path) -> SupportLevel:
        return SupportLevel.SUPPORTED if self._workflows(Path(root)) else SupportLevel.UNSUPPORTED

    def _workflows(self, root: Path) -> list[Path]:
        folder = root / ".github" / "workflows"
        return sorted([*folder.glob("*.yml"), *folder.glob("*.yaml")]) if folder.is_dir() else []

    def discover(self, root: Path) -> list[VerificationCheck]:
        root = Path(root)
        checks: list[VerificationCheck] = []
        for path in self._workflows(root):
            source = path.relative_to(root).as_posix()
            try:
                document = yaml.safe_load(path.read_text(encoding="utf-8"))
                jobs = document.get("jobs") if isinstance(document, dict) else None
                if not isinstance(jobs, dict):
                    raise ValueError("no jobs mapping")
            except (yaml.YAMLError, ValueError) as exc:
                checks.append(unreadable_check(self.adapter_id, f"gha:{source}", source, f"workflow could not be parsed: {exc}"))
                continue
            for job_id, job in jobs.items():
                checks.extend(self._job_checks(source, str(job_id), job if isinstance(job, dict) else {}))
        return checks

    def _job_checks(self, source: str, job_id: str, job: dict) -> list[VerificationCheck]:
        where = f"{source}#{job_id}"
        strategy = job.get("strategy") if isinstance(job.get("strategy"), dict) else {}
        steps = [s for s in job.get("steps") or [] if isinstance(s, dict)]
        setup = {}
        for step in steps:
            dim = _SETUP_VERSIONS.get(str(step.get("uses", "")).split("@")[0])
            if dim and isinstance(step.get("with"), dict) and step["with"].get(dim[1]) is not None:
                setup = merge_values(setup, {dim[0]: [str(step["with"][dim[1]])]})
        environment = job.get("environment")
        services = sorted(str(name) for name in job["services"]) if isinstance(job.get("services"), dict) else []
        if job.get("container"):
            services.append("container: " + str(job["container"].get("image") if isinstance(job["container"], dict) else job["container"]))
        job_meta = {
            "services": services,
            "job": job_id, "matrix": strategy.get("matrix"), "environment": environment.get("name") if isinstance(environment, dict) else environment,
            "matrix_values": merge_values(matrix_values(strategy.get("matrix")), {"os": [str(job["runs-on"])]} if isinstance(job.get("runs-on"), str) else {}, setup),
        }
        if "uses" in job:
            return [opaque_check(self.adapter_id, f"gha:{source}:{job_id}", str(job["uses"]).split("@")[0], where, GateMode.UNKNOWN,
                                 {**job_meta, "condition": job.get("if")}, "reusable workflow is not followed by this adapter")]
        checks = []
        for index, step in enumerate(steps, start=1):
            meta = {**job_meta, "step": step.get("name"), "condition": step.get("if") or job.get("if")}
            gate = _gate(step.get("continue-on-error"), job.get("continue-on-error"))
            check_id = f"gha:{source}:{job_id}:{index}"
            if "run" in step:
                check = command_check(self.adapter_id, check_id, str(step["run"]), where, gate,
                                      {**meta, "working_directory": step.get("working-directory")}, deploys=bool(environment))
                if check is not None:
                    checks.append(check)
            elif "uses" in step:
                action = str(step["uses"]).split("@")[0]
                if not action.startswith(_SETUP_ACTIONS):
                    checks.append(opaque_check(self.adapter_id, check_id, action, where, gate, meta,
                                               "action semantics are unknown and it cannot be reproduced locally", deploys=bool(environment)))
        return checks
