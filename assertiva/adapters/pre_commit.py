"""pre-commit adapter: declared local hook checks.

Whether hooks are installed on a developer machine is not observable from the
repository, so hook gates are UNKNOWN.
"""

from __future__ import annotations

from pathlib import Path

import yaml

from assertiva.verification import SupportLevel, VerificationCheck, VerificationKind, VerificationOrigin

from .commands import classify_command

CONFIG = ".pre-commit-config.yaml"


class PreCommitAdapter:
    adapter_id = "pre-commit"

    def supports(self, root: Path) -> SupportLevel:
        return SupportLevel.SUPPORTED if (Path(root) / CONFIG).is_file() else SupportLevel.UNSUPPORTED

    def discover(self, root: Path) -> list[VerificationCheck]:
        path = Path(root) / CONFIG
        try:
            document = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
            repos = document["repos"]
        except (yaml.YAMLError, KeyError, TypeError) as exc:
            return [
                VerificationCheck(
                    check_id="pre-commit", kind=VerificationKind.UNKNOWN, origin=VerificationOrigin.HOOK, source=CONFIG,
                    adapter_id=self.adapter_id, evidence_tier="E2",
                    limitations=(f"pre-commit configuration could not be parsed: {exc}".splitlines()[0],),
                )
            ]
        checks = []
        for repo in repos or []:
            for hook in (repo or {}).get("hooks") or []:
                hook_id = str(hook.get("id"))
                entry = hook.get("entry")
                cls = classify_command(str(entry) if entry else hook_id)
                checks.append(
                    VerificationCheck(
                        check_id=f"pre-commit:{hook_id}", kind=cls.kind, origin=VerificationOrigin.HOOK,
                        command=str(entry) if entry else None, tool=cls.tool, source=CONFIG, adapter_id=self.adapter_id,
                        evidence_tier="E2",
                        limitations=("hook installation on developer machines is not observable",),
                        metadata={"hook_id": hook_id, "repo": repo.get("repo"), "stages": hook.get("stages")},
                    )
                )
        return checks
