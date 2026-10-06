"""package.json scripts as declared local verification checks.

Scripts are discovered, classified by their command and never executed by discovery.
"""

from __future__ import annotations

import json
from pathlib import Path

from assertiva.verification import SupportLevel, VerificationCheck, VerificationKind, VerificationOrigin

from .commands import classify_command


class PackageScriptsAdapter:
    adapter_id = "package-scripts"

    def supports(self, root: Path) -> SupportLevel:
        return SupportLevel.SUPPORTED if (Path(root) / "package.json").is_file() else SupportLevel.UNSUPPORTED

    def discover(self, root: Path) -> list[VerificationCheck]:
        try:
            scripts = json.loads((Path(root) / "package.json").read_text(encoding="utf-8")).get("scripts") or {}
        except (OSError, ValueError) as exc:
            return [VerificationCheck(check_id="package-scripts", kind=VerificationKind.UNKNOWN, origin=VerificationOrigin.LOCAL,
                                      source="package.json", adapter_id=self.adapter_id, evidence_tier="E2",
                                      limitations=(f"package.json could not be read: {exc}"[:200],))]
        checks = []
        for name, command in sorted(scripts.items()):
            cls = classify_command(str(command))
            if cls.setup_only:
                continue
            checks.append(VerificationCheck(
                check_id=f"package-script:{name}", kind=cls.kind, origin=VerificationOrigin.LOCAL, command=str(command),
                tool=cls.tool, source="package.json", adapter_id=self.adapter_id, evidence_tier="E2",
                limitations=("no adapter classifies this script; its semantics are unknown",) if cls.kind is VerificationKind.UNKNOWN else (),
                metadata={"script": name, "runner_args": list(cls.runner_args)},
            ))
        return checks
