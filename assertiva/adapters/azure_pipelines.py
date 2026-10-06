"""Azure Pipelines adapter: ``azure-pipelines.yml`` -> declared CI VerificationChecks (E2).

Reads stages/jobs/steps (and deployment jobs' runOnce steps); ``script``/``bash``/``pwsh``/
``powershell`` steps are classified commands, ``task`` steps are opaque. Templates and runtime
expressions are preserved, not interpreted; nothing is ever run against Azure DevOps.
"""

from __future__ import annotations

from pathlib import Path

import yaml

from assertiva.verification import GateMode, SupportLevel, VerificationCheck

from .ci_common import command_check, matrix_values, merge_values, opaque_check, unreadable_check

_FILES = ("azure-pipelines.yml", "azure-pipelines.yaml", ".azure-pipelines.yml")
_SCRIPT_KEYS = ("script", "bash", "pwsh", "powershell")


def _os(pool) -> dict[str, list[str]]:
    image = pool.get("vmImage") if isinstance(pool, dict) else None
    return {"os": [str(image)]} if image else {}


class AzurePipelinesAdapter:
    adapter_id = "azure-pipelines"

    def supports(self, root: Path) -> SupportLevel:
        return SupportLevel.SUPPORTED if self._file(Path(root)) else SupportLevel.UNSUPPORTED

    def _file(self, root: Path) -> Path | None:
        return next((root / name for name in _FILES if (root / name).is_file()), None)

    def discover(self, root: Path) -> list[VerificationCheck]:
        path = self._file(Path(root))
        source = path.name
        try:
            document = yaml.safe_load(path.read_text(encoding="utf-8"))
            if not isinstance(document, dict):
                raise ValueError("not a mapping")
        except (yaml.YAMLError, ValueError) as exc:
            return [unreadable_check(self.adapter_id, f"azure:{source}", source, f"pipeline could not be parsed: {exc}")]
        jobs = []
        for stage in document.get("stages") or []:
            if isinstance(stage, dict):
                jobs += [(stage.get("stage"), stage.get("condition"), job) for job in stage.get("jobs") or [] if isinstance(job, dict)]
        jobs += [(None, None, job) for job in document.get("jobs") or [] if isinstance(job, dict)]
        if document.get("steps"):
            jobs.append((None, None, {"job": "default", "steps": document["steps"]}))
        checks = [check for index, (stage, condition, job) in enumerate(jobs)
                  for check in self._job(source, stage, condition, job, index, document.get("pool"))]
        if document.get("extends") or any("template" in (j or {}) for _, _, j in jobs):
            checks.append(opaque_check(self.adapter_id, f"azure:{source}:templates", "template", source, GateMode.UNKNOWN, {},
                                       "templates are not followed by this adapter"))
        return checks

    def _job(self, source, stage, stage_condition, job, index, root_pool) -> list[VerificationCheck]:
        name = str(job.get("job") or job.get("deployment") or f"job{index}")
        deploys = "deployment" in job
        steps = job.get("steps") or []
        if deploys:
            strategy = (job.get("strategy") or {}).get("runOnce") or {}
            steps = (strategy.get("deploy") or {}).get("steps") or steps
        environment = job.get("environment")
        meta = {
            "job": f"{stage}/{name}" if stage else name, "environment": environment.get("name") if isinstance(environment, dict) else environment,
            "matrix": (job.get("strategy") or {}).get("matrix") if not deploys else None,
            "matrix_values": merge_values(matrix_values((job.get("strategy") or {}).get("matrix")), _os(job.get("pool") or root_pool)),
        }
        where = f"{source}#{meta['job']}"
        checks = []
        for number, step in enumerate(steps, start=1):
            if not isinstance(step, dict):
                continue
            condition = step.get("condition") or job.get("condition") or stage_condition
            gate = GateMode.ALLOWED_FAILURE if True in (step.get("continueOnError"), job.get("continueOnError")) else GateMode.UNKNOWN
            check_id = f"azure:{source}:{meta['job']}:{number}"
            step_meta = {**meta, "step": step.get("displayName"), "condition": condition}
            key = next((k for k in _SCRIPT_KEYS if k in step), None)
            if key:
                check = command_check(self.adapter_id, check_id, str(step[key]), where, gate, step_meta, deploys=deploys)
                if check is not None:
                    checks.append(check)
            elif "task" in step:
                checks.append(opaque_check(self.adapter_id, check_id, str(step["task"]), where, gate, step_meta,
                                           "task semantics are unknown and it cannot be reproduced locally", deploys=deploys))
        return checks
