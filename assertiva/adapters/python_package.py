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
from assertiva.process import CommandResult, active_target, execution_refusal, is_active, module_available, run_command, scoped
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

# Declared-dependency view: copy only the distributions the wheel declares (transitively,
# markers evaluated) from the target environment. Runs in the target interpreter; offline.
_DEPS_VIEW = r"""
import json, os, re, shutil, sys
from importlib import metadata
try:
    from packaging.requirements import Requirement
except ImportError:
    try:
        from pip._vendor.packaging.requirements import Requirement
    except ImportError:
        Requirement = None
requirements, view = json.loads(sys.argv[1]), sys.argv[2]
norm = lambda n: re.sub(r"[-_.]+", "-", n).lower()
seen, missing, unsupported, queue = set(), [], [], [(r, ()) for r in requirements]
while queue:
    text, extras = queue.pop()
    if Requirement is None:
        if ";" in text:
            unsupported.append(text)
            continue
        name, wanted = re.split(r"[ <>=!~\[(]", text.strip(), maxsplit=1)[0], ()
    else:
        req = Requirement(text)
        if req.marker and not any(req.marker.evaluate({"extra": e}) for e in (extras or ("",))):
            continue
        name, wanted = req.name, tuple(req.extras)
    if norm(name) in seen:
        continue
    seen.add(norm(name))
    try:
        dist = metadata.distribution(name)
    except metadata.PackageNotFoundError:
        missing.append(name)
        continue
    base = str(dist.locate_file(""))
    for entry in dist.files or []:
        source = str(dist.locate_file(entry))
        rel = os.path.relpath(source, base)
        if rel.startswith("..") or not os.path.isfile(source):
            continue
        target = os.path.join(view, rel)
        os.makedirs(os.path.dirname(target), exist_ok=True)
        shutil.copy2(source, target)
    queue.extend((r, wanted) for r in dist.requires or [])
print(json.dumps({"resolved": sorted(seen), "missing": missing, "unsupported": unsupported}))
"""
# Import every module of the installed package; report modules nothing declared provides.
_CLOSURE_PROBE = r"""
import importlib, json, pkgutil, sys
tops, missing, errors = sys.argv[1:], set(), []
def visit(name):
    try:
        return importlib.import_module(name)
    except ModuleNotFoundError as exc:
        missing.add(exc.name or str(exc))
    except Exception as exc:
        errors.append((name + ": " + type(exc).__name__ + ": " + str(exc))[:200])
for top in tops:
    module = visit(top)
    if module is not None and hasattr(module, "__path__"):
        for info in pkgutil.walk_packages(module.__path__, top + "."):
            visit(info.name)
print(json.dumps({"missing": sorted(m for m in missing if m.split(".")[0] not in tops), "errors": errors}))
"""


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


def _fidelity(evidence: ArtifactEvidence) -> dict[str, str]:
    """What the artifact evidence proves, dimension by dimension (never one blanket claim)."""
    checks = {c.name: c.status.value for c in evidence.checks}
    isolation = checks.get("import", "NOT_RUN")
    if isolation == "PASS" and evidence.status is StageStatus.UNKNOWN and "tests" not in checks:
        isolation = "UNKNOWN"  # imports resolved outside the artifact
    return {
        "ARTIFACT_SOURCE_ISOLATION": isolation,
        "ARTIFACT_TARGET_ENV_COMPATIBILITY": checks.get("tests", "NOT_RUN"),
        "DECLARED_DEPENDENCY_CLOSURE": checks.get("dependency_closure", "NOT_RUN"),
        "CLEAN_INSTALL": "NOT_RUN",
        "SDIST": "NOT_RUN",
    }


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

    def identity(self, root: Path) -> str:
        project = _pyproject(Path(root)).get("project") or {}
        return f"{project.get('name') or Path(root).resolve().name}=={project.get('version') or '?'}"

    @scoped
    def qualify(self, root: str | Path) -> ArtifactEvidence:
        root = Path(root)
        identity = self.identity(root)
        refusal = execution_refusal() or (
            f"recursive artifact qualification of {identity} refused: an outer run is already qualifying it"
            if is_active("artifact", identity) else None
        )
        if refusal:
            return ArtifactEvidence(adapter_id=self.adapter_id, kind="wheel", status=StageStatus.BLOCKED, limitations=[refusal])
        with active_target("artifact", identity):
            return self._qualify(root)

    def _qualify(self, root: Path) -> ArtifactEvidence:
        evidence = ArtifactEvidence(adapter_id=self.adapter_id, kind="wheel", status=StageStatus.PASS)
        evidence.limitations.append("only the wheel was built and verified; the sdist was not")
        evidence.limitations.append("no clean install from a package index was performed (offline)")
        try:
            self._qualify_into(root, evidence)
        finally:
            evidence.fidelity = _fidelity(evidence)
        return evidence

    def _qualify_into(self, root: Path, evidence: ArtifactEvidence) -> None:
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
                return
            wheel = wheels[0]
            evidence.artifact = wheel.name
            evidence.sha256 = hashlib.sha256(wheel.read_bytes()).hexdigest()
            with zipfile.ZipFile(wheel) as archive:
                names = archive.namelist()
            tops = _top_level(names)
            evidence.omitted_files = self._omitted(work, tops, set(names))

            with zipfile.ZipFile(wheel) as archive:
                metadata = next((archive.read(n).decode("utf-8", "replace") for n in names if n.endswith(".dist-info/METADATA")), "")
            requirements = [line.split(":", 1)[1].strip() for line in metadata.splitlines() if line.startswith("Requires-Dist:")]
            venv = tmp / "venv"
            sites = self._run([self.python, "-c", _SITE_PROBE], outside)
            target_sites = json.loads(sites.stdout) if sites.ok else []
            installed, wheel_site = self._install(venv, wheel, outside, target_sites)
            if not self._check(evidence, "install", installed):
                return
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
                return
            if shadowed:
                evidence.status = StageStatus.UNKNOWN
                evidence.limitations.append("imports did not resolve to the installed artifact: " + ", ".join(shadowed))
                return

            self._tests_against_artifact(evidence, work, tops, vpy, tmp)
            self._dependency_closure(evidence, wheel_site, tops, requirements, tmp, outside)

    def _dependency_closure(self, evidence: ArtifactEvidence, wheel_site: str | None, tops: list[str], requirements: list[str], tmp: Path, cwd: Path) -> None:
        """Import every module of the installed wheel where only its declared dependencies exist.

        The clean venv sees the wheel's installed files as a plain path entry (so the host
        environment linked from that venv stays invisible) plus a view of the declared
        dependencies copied from the target environment.
        """
        view, venv = tmp / "declared-deps", tmp / "closure-venv"
        view.mkdir()
        resolved = self._run([self.python, "-c", _DEPS_VIEW, json.dumps(requirements), view], cwd)
        created = self._run([self.python, "-m", "venv", "--without-pip", venv], cwd)
        closure_site = self._run([_venv_python(venv), "-c", "import sysconfig; print(sysconfig.get_paths()['purelib'])"], cwd)
        ready = resolved.ok and bool(wheel_site) and created.ok and closure_site.ok
        if ready:
            Path(closure_site.stdout.strip()).joinpath("assertiva-closure.pth").write_text(
                f"{wheel_site}\n{view}\n", encoding="utf-8"
            )
        if not ready:
            failed = next((r.summary() for r in (resolved, created, closure_site) if not r.ok), "installed wheel location unknown")
            status, detail = StageStatus.BLOCKED, "could not prepare the declared-dependency environment: " + failed
        else:
            deps = json.loads(resolved.stdout.strip().splitlines()[-1])
            probe = self._run([_venv_python(venv), "-c", _CLOSURE_PROBE, *tops], cwd)
            found = json.loads(probe.stdout.strip().splitlines()[-1]) if probe.ok and probe.stdout.strip() else None
            if deps["missing"] or deps["unsupported"]:
                status = StageStatus.UNKNOWN
                detail = "declared dependencies not available offline in the target environment: " + ", ".join(deps["missing"] + deps["unsupported"])
            elif found is None:
                status, detail = StageStatus.BLOCKED, "closure probe did not run: " + probe.summary()
            elif found["missing"]:
                status = StageStatus.FAIL
                detail = "imports modules no declared dependency provides: " + ", ".join(found["missing"])
            elif found["errors"]:
                status, detail = StageStatus.UNKNOWN, "modules failed to import for other reasons: " + "; ".join(found["errors"][:3])
            else:
                status = StageStatus.PASS
                detail = f"every module imports with only declared dependencies ({', '.join(deps['resolved']) or 'none'})"
        evidence.checks.append(ArtifactCheck("dependency_closure", status, "clean venv + declared dependencies only", None, detail))
        if status is StageStatus.FAIL or (status is not StageStatus.PASS and evidence.status is StageStatus.PASS):
            evidence.status = status

    def _install(self, venv: Path, wheel: Path, cwd: Path, visible_sites: list[str]) -> tuple[CommandResult, str | None]:
        """Install the wheel with --no-deps into a fresh venv that also sees ``visible_sites``.

        Returns the install result and the venv's site-packages (where the wheel's files are).
        """
        # A pip-less venv plus `pip --python` performs the same isolated install without
        # bootstrapping pip into every environment (seconds per venv).
        created = self._run([self.python, "-m", "venv", "--without-pip", venv], cwd)
        if not created.ok:
            return created, None
        venv_site = self._run([_venv_python(venv), "-c", "import sysconfig; print(sysconfig.get_paths()['purelib'])"], cwd)
        if venv_site.ok and visible_sites:  # visible *after* the venv's own site-packages
            Path(venv_site.stdout.strip()).joinpath("assertiva-visible-sites.pth").write_text(
                "\n".join(visible_sites) + "\n", encoding="utf-8"
            )
        install = ["install", "--no-deps", "--no-index", "--disable-pip-version-check", wheel]
        result = self._run([self.python, "-m", "pip", "--python", _venv_python(venv), *install], cwd)
        if result.returncode and "no such option: --python" in result.stderr:  # pip < 22.3
            self._run([_venv_python(venv), "-m", "ensurepip", "--default-pip"], cwd)
            result = self._run([_venv_python(venv), "-m", "pip", *install], cwd)
        return result, (venv_site.stdout.strip() if venv_site.ok else None)

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
