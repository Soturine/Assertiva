"""GitHub Actions adapter: workflow files -> declared CI VerificationChecks.

Declared configuration (E2), not run evidence: a workflow containing a step does not
prove that the step ran, ran on this revision, or gated a merge. Reusable workflows,
composite actions and expressions are preserved, not interpreted.
"""

from __future__ import annotations

from pathlib import Path

import yaml

from assertiva.verification import GateMode, SupportLevel, VerificationCheck, VerificationKind, VerificationOrigin

from .commands import classify_command

_SETUP_ACTIONS = ("actions/checkout", "actions/setup-", "actions/cache", "actions/upload-artifact", "actions/download-artifact")


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
                checks.append(
                    VerificationCheck(
                        check_id=f"gha:{source}", kind=VerificationKind.UNKNOWN, origin=VerificationOrigin.CI,
                        source=source, adapter_id=self.adapter_id, evidence_tier="E2",
                        limitations=(f"workflow could not be parsed: {exc}".splitlines()[0],),
                    )
                )
                continue
            for job_id, job in jobs.items():
                checks.extend(self._job_checks(source, str(job_id), job if isinstance(job, dict) else {}))
        return checks

    def _job_checks(self, source: str, job_id: str, job: dict) -> list[VerificationCheck]:
        base = {"origin": VerificationOrigin.CI, "source": f"{source}#{job_id}", "adapter_id": self.adapter_id, "evidence_tier": "E2"}
        strategy = job.get("strategy") if isinstance(job.get("strategy"), dict) else {}
        job_meta = {"job": job_id, "matrix": strategy.get("matrix")}
        if "uses" in job:
            return [
                VerificationCheck(
                    check_id=f"gha:{source}:{job_id}", kind=VerificationKind.UNKNOWN, tool=str(job["uses"]).split("@")[0],
                    limitations=("reusable workflow is not followed by this adapter",), metadata=job_meta, **base,
                )
            ]
        checks = []
        for index, step in enumerate(job.get("steps") or [], start=1):
            if not isinstance(step, dict):
                continue
            meta = {**job_meta, "step": step.get("name"), "condition": step.get("if") or job.get("if")}
            gate = _gate(step.get("continue-on-error"), job.get("continue-on-error"))
            check_id = f"gha:{source}:{job_id}:{index}"
            if "run" in step:
                command = str(step["run"]).strip()
                cls = classify_command(command)
                if cls.setup_only:
                    continue
                limitations = []
                if cls.kind is VerificationKind.UNKNOWN:
                    limitations.append("no adapter classifies this command; its semantics are unknown")
                if cls.unclassified and cls.kind is not VerificationKind.UNKNOWN:
                    limitations.append("step also runs unclassified commands: " + "; ".join(cls.unclassified))
                checks.append(
                    VerificationCheck(
                        check_id=check_id, kind=cls.kind, gate=gate, command=command, tool=cls.tool,
                        limitations=tuple(limitations),
                        metadata={**meta, **cls.metadata, "runner_args": list(cls.runner_args), "working_directory": step.get("working-directory")},
                        **base,
                    )
                )
            elif "uses" in step:
                action = str(step["uses"]).split("@")[0]
                if action.startswith(_SETUP_ACTIONS):
                    continue
                checks.append(
                    VerificationCheck(
                        check_id=check_id, kind=VerificationKind.UNKNOWN, gate=gate, tool=action,
                        limitations=("action semantics are unknown and it cannot be reproduced locally",),
                        metadata=meta, **base,
                    )
                )
        return checks
