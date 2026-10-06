"""Python packaging adapter: qualify the built wheel, not the source tree.

build wheel (from a disposable copy) -> install it with --no-deps into a fresh venv
-> import its top-level packages from outside the tree and check they come from the
venv -> run the project's tests against the installed artifact with the source
packages removed, so the source tree cannot shadow a broken package.
"""

from __future__ import annotations

import hashlib
import json
import os
import shutil
import sys
import tempfile
import tomllib
import zipfile
from pathlib import Path

from assertiva.candidate import StageStatus
from assertiva.models import ArtifactCheck, ArtifactEvidence
from assertiva.process import CommandResult, module_available, run_command
from assertiva.verification import SupportLevel
from assertiva.workspace import project_files, snapshot

_IMPORT_PROBE = (
    "import importlib, json, sys\n"
    "out = {}\n"
    "for name in sys.argv[1:]:\n"
    "    try:\n"
    "        out[name] = importlib.import_module(name).__file__\n"
    "    except Exception as exc:\n"
    "        out[name] = 'ERROR: ' + type(exc).__name__ + ': ' + str(exc)\n"
    "print(json.dumps(out))\n"
)
# Every site directory the target interpreter really uses, including ones it inherits
# (system site packages, extra site dirs), so its installed dependencies stay visible.
_SITE_PROBE = (
    "import json, os, sys, sysconfig\n"
    "p = sysconfig.get_paths()\n"
    "dirs = [p['purelib'], p['platlib']] + [d for d in sys.path if os.path.basename(d.rstrip('/\\\\')) in ('site-packages', 'dist-packages')]\n"
    "print(json.dumps([d for d in dict.fromkeys(dirs) if os.path.isdir(d)]))"
)


def _pyproject(root: Path) -> dict:
    path = root / "pyproject.toml"
    try:
        return tomllib.loads(path.read_text(encoding="utf-8")) if path.is_file() else {}
    except tomllib.TOMLDecodeError:
        return {"build-system": {}}  # declared but unreadable: let the build report the failure


def _venv_python(venv: Path) -> Path:
    return venv / ("Scripts/python.exe" if os.name == "nt" else "bin/python")


def _top_level(names: list[str]) -> list[str]:
    tops = set()
    for name in names:
        first = name.split("/", 1)[0]
        if first.endswith((".dist-info", ".data")):
            continue
        if "/" in name and name.endswith("/__init__.py") and name.count("/") == 1:
            tops.add(first)
        elif "/" not in name and name.endswith(".py"):
            tops.add(name[:-3])
    return sorted(tops)


def _clean_env() -> dict:
    env = {k: v for k, v in os.environ.items() if k not in {"PYTHONPATH", "PYTHONHOME", "PYTEST_CURRENT_TEST"}}
    env["PYTHONPYCACHEPREFIX"] = str(Path(tempfile.gettempdir()) / "assertiva-pycache")
    return env


class PythonPackageAdapter:
    adapter_id = "python-package"

    def __init__(self, python: str | None = None, timeout_s: float = 900.0):
        self.python = python or sys.executable
        self.timeout_s = timeout_s

    def supports(self, root: Path) -> SupportLevel:
        root = Path(root)
        data = _pyproject(root)
        if "build-system" in data or "project" in data or (root / "setup.py").is_file():
            return SupportLevel.SUPPORTED
        return SupportLevel.UNSUPPORTED

    def _run(self, command: list, cwd: Path) -> CommandResult:
        return run_command([str(c) for c in command], cwd, env=_clean_env(), timeout_s=self.timeout_s)

    def _check(self, evidence: ArtifactEvidence, name: str, result: CommandResult, detail: str = "") -> bool:
        status = StageStatus.PASS if result.ok else (StageStatus.BLOCKED if result.error or result.timed_out else StageStatus.FAIL)
        evidence.checks.append(ArtifactCheck(name, status, " ".join(result.command), result.duration_s, detail or result.summary()))
        if status is not StageStatus.PASS:
            evidence.status = status
        return status is StageStatus.PASS

    def _backend_is_local(self, root: Path, work: Path) -> bool:
        backend = (_pyproject(root).get("build-system") or {}).get("build-backend", "setuptools.build_meta:__legacy__")
        return module_available(self.python, backend.split(":")[0].split(".")[0])

    def qualify(self, root: str | Path) -> ArtifactEvidence:
        root = Path(root)
        evidence = ArtifactEvidence(adapter_id=self.adapter_id, kind="wheel", status=StageStatus.PASS)
        evidence.limitations.append("only the wheel was built and verified; the sdist was not")
        with tempfile.TemporaryDirectory(prefix="assertiva-artifact-") as tmp:
            tmp = Path(tmp)
            work, dist, outside = snapshot(root, tmp / "src"), tmp / "dist", tmp / "outside"
            outside.mkdir()

            local_backend = self._backend_is_local(root, work)
            has_build = module_available(self.python, "build")
            if has_build:
                command = [self.python, "-m", "build", "--wheel", "--outdir", dist] + (["--no-isolation"] if local_backend else [])
            else:
                command = [self.python, "-m", "pip", "wheel", "--no-deps", "--disable-pip-version-check", "-w", dist] + (
                    ["--no-build-isolation"] if local_backend else []) + [work]
            evidence.environment = {"build_tool": "build" if has_build else "pip wheel", "build_isolation": not local_backend}
            if not local_backend:
                evidence.limitations.append("build backend not importable locally: isolated build may need network access")
            result = self._run(command, work)
            wheels = sorted(dist.glob("*.whl")) if dist.exists() else []
            if result.ok and not wheels:
                result.returncode = -1
            if not self._check(evidence, "build", result):
                return evidence
            wheel = wheels[0]
            evidence.artifact = wheel.name
            evidence.sha256 = hashlib.sha256(wheel.read_bytes()).hexdigest()
            with zipfile.ZipFile(wheel) as archive:
                names = archive.namelist()
            tops = _top_level(names)
            evidence.omitted_files = self._omitted(work, tops, set(names))

            venv = tmp / "venv"
            if not self._check(evidence, "install", self._install(venv, wheel, outside)):
                return evidence
            vpy = _venv_python(venv)

            probe = self._run([vpy, "-c", _IMPORT_PROBE, *tops], outside)
            origins = json.loads(probe.stdout.strip().splitlines()[-1]) if probe.ok and probe.stdout.strip() else {}
            broken = {k: v for k, v in origins.items() if not v or str(v).startswith("ERROR")}
            shadowed = {k: v for k, v in origins.items() if k not in broken and not Path(v).resolve().is_relative_to(venv.resolve())}
            if not tops:
                probe.returncode = -1
                detail = "the wheel contains no importable top-level package or module"
            elif broken:
                probe.returncode = 1
                detail = "; ".join(f"{k}: {v}" for k, v in broken.items())
            else:
                detail = "; ".join(f"{k} -> {v}" for k, v in origins.items())
            if not self._check(evidence, "import", probe, detail):
                return evidence
            if shadowed:
                evidence.status = StageStatus.UNKNOWN
                evidence.limitations.append("imports did not resolve to the installed artifact: " + ", ".join(shadowed))
                return evidence

            self._tests_against_artifact(evidence, work, tops, vpy, tmp)
        return evidence

    def _install(self, venv: Path, wheel: Path, cwd: Path) -> CommandResult:
        # A pip-less venv plus `pip --python` performs the same isolated install without
        # bootstrapping pip into every environment (seconds per venv).
        created = self._run([self.python, "-m", "venv", "--without-pip", venv], cwd)
        if not created.ok:
            return created
        # Make the target environment's dependencies visible *after* the venv's own site-packages.
        sites = self._run([self.python, "-c", _SITE_PROBE], cwd)
        venv_site = self._run([_venv_python(venv), "-c", "import sysconfig; print(sysconfig.get_paths()['purelib'])"], cwd)
        if sites.ok and venv_site.ok:
            Path(venv_site.stdout.strip()).joinpath("assertiva-target-env.pth").write_text(
                "\n".join(json.loads(sites.stdout)) + "\n", encoding="utf-8"
            )
        install = ["install", "--no-deps", "--no-index", "--disable-pip-version-check", wheel]
        result = self._run([self.python, "-m", "pip", "--python", _venv_python(venv), *install], cwd)
        if result.returncode and "no such option: --python" in result.stderr:  # pip < 22.3
            self._run([_venv_python(venv), "-m", "ensurepip", "--default-pip"], cwd)
            result = self._run([_venv_python(venv), "-m", "pip", *install], cwd)
        return result

    def _omitted(self, work: Path, tops: list[str], names: set[str]) -> list[str]:
        """Non-code files inside packaged directories that the wheel does not contain (E3 signal)."""
        omitted = []
        for rel in project_files(work):
            parts = rel.split("/")
            offset = 1 if parts[0] == "src" else 0
            if len(parts) <= offset + 1 or parts[offset] not in tops or rel.endswith((".py", ".pyc")):
                continue
            if "/".join(parts[offset:]) not in names:
                omitted.append("/".join(parts[offset:]))
        return sorted(omitted)

    def _tests_against_artifact(self, evidence: ArtifactEvidence, work: Path, tops: list[str], vpy: Path, tmp: Path) -> None:
        from .pytest_native import PytestNativeAdapter

        copy = snapshot(work, tmp / "tests-copy")
        for name in tops:
            for base in (copy, copy / "src"):
                shutil.rmtree(base / name, ignore_errors=True)
                (base / f"{name}.py").unlink(missing_ok=True)
        runner = PytestNativeAdapter(python=str(vpy), timeout_s=self.timeout_s)
        if runner.supports(copy) is not SupportLevel.SUPPORTED:
            evidence.checks.append(ArtifactCheck("tests", StageStatus.NOT_RUN, detail="no test runner adapter for this project"))
            evidence.limitations.append("only build, install and import were verified; no tests ran against the artifact")
            return
        run = runner.run(copy)
        failing = [inv.invocation_id for inv in run.invocations if inv.outcome and inv.outcome.value in {"FAILED", "ERROR"}]
        detail = f"{len(run.invocations)} invocations against the installed artifact: {run.status.value}"
        if failing:
            detail += "; failing: " + ", ".join(failing[:10])
        if run.collection_errors:
            detail += "; collection errors: " + ", ".join(run.collection_errors[:5])
        status = run.status
        evidence.checks.append(ArtifactCheck("tests", status, " ".join(run.command), run.wall_clock_s, detail))
        if status is StageStatus.UNKNOWN:
            evidence.limitations.append("no tests were collected against the installed artifact")
        if status is not StageStatus.PASS and evidence.status is StageStatus.PASS:
            evidence.status = status
