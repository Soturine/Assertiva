"""Jenkins adapter: a declarative ``Jenkinsfile`` -> declared CI VerificationChecks (E2).

A Jenkinsfile is Groovy code, so only what is literally declared is read: ``stage('...')``
blocks, literal ``sh``/``bat``/``powershell`` steps, ``when`` conditions, matrix ``axis``
values and docker agent images. Scripted logic, shared libraries and computed commands
are UNKNOWN, never guessed; nothing is ever run against Jenkins.
"""

from __future__ import annotations

import re
from pathlib import Path

from assertiva.verification import GateMode, SupportLevel, VerificationCheck

from .ci_common import command_check, dimension, image_runtime, merge_values, opaque_check

_STAGE = re.compile(r"""\bstage\s*\(\s*['"]([^'"]+)['"]\s*\)""")
_STEP = re.compile(r"""\b(sh|bat|powershell)\s*\(?\s*(?:script\s*:\s*)?('''(.*?)'''|\"\"\"(.*?)\"\"\"|'([^'\n]*)'|"([^"\n]*)")""", re.S)
_AXIS = re.compile(r"""axis\s*\{\s*name\s+['"]([^'"]+)['"]\s*values\s+((?:['"][^'"]+['"]\s*,?\s*)+)\}""")
_IMAGE = re.compile(r"""docker\s*\{?\s*(?:image\s+)?['"]([^'"]+)['"]""")
_DYNAMIC = re.compile(r"\$\{|\$[A-Za-z_]")


class JenkinsAdapter:
    adapter_id = "jenkins"

    def supports(self, root: Path) -> SupportLevel:
        return SupportLevel.SUPPORTED if (Path(root) / "Jenkinsfile").is_file() else SupportLevel.UNSUPPORTED

    def discover(self, root: Path) -> list[VerificationCheck]:
        source = "Jenkinsfile"
        text = (Path(root) / source).read_text(encoding="utf-8", errors="replace")
        stages = list(_STAGE.finditer(text))
        segments = [(m.group(1), text[m.end(): stages[i + 1].start() if i + 1 < len(stages) else len(text)]) for i, m in enumerate(stages)]
        if not segments:
            segments = [("pipeline", text)]
        axes = {}
        for name, values in _AXIS.findall(text):
            axes[name] = re.findall(r"""['"]([^'"]+)['"]""", values)
        axis_values = {dimension(name): values for name, values in axes.items() if dimension(name)}
        global_values = merge_values(axis_values, *(image_runtime(image) for image in _IMAGE.findall(text)))
        checks: list[VerificationCheck] = []
        for stage, body in segments:
            condition = "when" if re.search(r"\bwhen\s*\{", body) else None
            gate = GateMode.ALLOWED_FAILURE if re.search(r"catchError|unstable\s*\(|returnStatus\s*:\s*true", body) else GateMode.UNKNOWN
            meta = {"job": stage, "condition": condition, "matrix": axes or None, "matrix_values": global_values}
            for index, match in enumerate(_STEP.finditer(body), start=1):
                command = next(g for g in match.groups()[2:] if g is not None)
                check_id = f"jenkins:{source}:{stage}:{index}"
                if _DYNAMIC.search(command):
                    checks.append(opaque_check(self.adapter_id, check_id, match.group(1), f"{source}#{stage}", gate,
                                               {**meta, "command": command}, "the command interpolates Groovy/shell variables; its value is unknown"))
                    continue
                check = command_check(self.adapter_id, check_id, command, f"{source}#{stage}", gate, meta)
                if check is not None:
                    checks.append(check)
        if re.search(r"@Library|\bload\s+['\"]", text):
            checks.append(opaque_check(self.adapter_id, f"jenkins:{source}:library", "shared library", source, GateMode.UNKNOWN, {},
                                       "shared libraries and loaded scripts are not followed by this adapter"))
        return checks
