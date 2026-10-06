"""GitLab CI adapter: ``.gitlab-ci.yml`` -> declared CI VerificationChecks (E2).

Each ``script``/``before_script`` entry of a job is a classified command. ``rules``/``only``/
``except``/``when`` make a job conditional; ``allow_failure`` is an allowed failure; ``include``
and ``extends`` are preserved, not followed; nothing is ever run against GitLab.
"""

from __future__ import annotations

from pathlib import Path

import yaml

from assertiva.verification import GateMode, SupportLevel, VerificationCheck

from .ci_common import command_check, image_runtime, matrix_values, merge_values, opaque_check, unreadable_check

_RESERVED = {"stages", "variables", "default", "include", "workflow", "image", "services", "before_script", "after_script", "cache", "pages"}
_CONDITIONS = ("rules", "only", "except", "when")


def _lines(value) -> list[str]:
    return [str(v) for v in value] if isinstance(value, list) else ([str(value)] if value else [])


class GitLabCiAdapter:
    adapter_id = "gitlab-ci"

    def supports(self, root: Path) -> SupportLevel:
        return SupportLevel.SUPPORTED if (Path(root) / ".gitlab-ci.yml").is_file() else SupportLevel.UNSUPPORTED

    def discover(self, root: Path) -> list[VerificationCheck]:
        source = ".gitlab-ci.yml"
        try:
            document = yaml.safe_load((Path(root) / source).read_text(encoding="utf-8"))
            if not isinstance(document, dict):
                raise ValueError("not a mapping")
        except (yaml.YAMLError, ValueError) as exc:
            return [unreadable_check(self.adapter_id, f"gitlab:{source}", source, f"pipeline could not be parsed: {exc}")]
        default = document.get("default") if isinstance(document.get("default"), dict) else {}
        default_image = default.get("image") or document.get("image")
        default_before = _lines(default.get("before_script") or document.get("before_script"))
        checks = []
        if document.get("include"):
            checks.append(opaque_check(self.adapter_id, f"gitlab:{source}:include", "include", source, GateMode.UNKNOWN, {},
                                       "included configuration is not followed by this adapter"))
        for name, job in document.items():
            if name in _RESERVED or str(name).startswith(".") or not isinstance(job, dict):
                continue
            image = job.get("image", default_image)
            image = image.get("name") if isinstance(image, dict) else image
            environment = job.get("environment")
            environment = environment.get("name") if isinstance(environment, dict) else environment
            matrix = (job.get("parallel") or {}).get("matrix") if isinstance(job.get("parallel"), dict) else None
            condition = {key: job[key] for key in _CONDITIONS if key in job and job[key] != "on_success"} or None
            meta = {"job": name, "stage": job.get("stage"), "environment": environment, "matrix": matrix, "condition": condition,
                    "image": image, "matrix_values": merge_values(matrix_values(matrix), image_runtime(image))}
            gate = GateMode.ALLOWED_FAILURE if job.get("allow_failure") is True else GateMode.UNKNOWN
            if job.get("extends"):
                meta["extends"] = job["extends"]
            before = _lines(job.get("before_script")) if "before_script" in job else default_before
            for index, command in enumerate([*before, *_lines(job.get("script"))], start=1):
                check = command_check(self.adapter_id, f"gitlab:{source}:{name}:{index}", command, f"{source}#{name}", gate, meta,
                                      deploys=bool(environment))
                if check is not None:
                    checks.append(check)
        return checks
