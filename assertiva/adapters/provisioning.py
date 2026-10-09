"""What a project needs to run its tests, what is already here, and how to prepare the rest in isolation.

Discovery reads files only (manifests, lockfiles, build files, CI); it never runs project code. Preparation
needs the user's consent (`audit --provision`, or `provision = true` in <ASSERTIVA_HOME>/consent.toml) because
it downloads and runs third-party installers; without it the plan is reported (BLOCKED) and everything that can
run without it still runs. Each ecosystem picks the path that matches the project, never every manager:

- Python: a compatible interpreter (`requires-python`) among the given one and those installed; a virtual
  environment in the run workspace; pip installs from the project's requirement files or declared dependencies
  (hash-pinned requirements are honored by pip). Lockfiles pip cannot read (uv, Poetry, PDM, Pipenv) are not
  honored, and that divergence is reported.
- Node: `npm ci --ignore-scripts` from package-lock.json into the run workspace (the project's node_modules is
  never created or used); other lockfiles are reported, not converted.
- JVM: a Temurin JDK (version from the build's toolchain declaration, else 21) from Adoptium and a Gradle
  distribution (the wrapper's declared version) from services.gradle.org, both verified against the publisher's
  sha256, into the tools cache; Gradle's caches go to the tools cache, never the user's ~/.gradle. The project's
  `gradle-wrapper.jar` is never executed.
"""

from __future__ import annotations

import json
import os
import platform
import re
import shutil
import sys
import time
import tomllib
from pathlib import Path

from assertiva.environment import Prepared, ProvisioningError, Step, download, extract, published_sha256, tools_dir
from assertiva.process import run_command

_LOCKFILES = {"uv.lock": "uv", "poetry.lock": "Poetry", "pdm.lock": "PDM", "Pipfile.lock": "Pipenv"}
_NODE_LOCKS = {"package-lock.json": "npm", "npm-shrinkwrap.json": "npm", "yarn.lock": "Yarn", "pnpm-lock.yaml": "pnpm", "bun.lockb": "Bun"}
_REQ_NAME = re.compile(r"^\s*([A-Za-z0-9][A-Za-z0-9._-]*)")
_TEST_GROUPS = ("test", "tests", "testing", "dev")
_JDK_DECLARED = (re.compile(r"JavaLanguageVersion\.of\(\s*(\d+)\s*\)"), re.compile(r"jvmToolchain\(\s*(\d+)\s*\)"),
                 re.compile(r"<maven\.compiler\.(?:release|source)>\s*(\d+)\s*<"), re.compile(r"<release>\s*(\d+)\s*</release>"))
DEFAULT_JDK = 21
MIN_GRADLE_JDK = 17  # current Gradle releases run on JDK 17+


# --- versions ------------------------------------------------------------------------------------

def _version_tuple(text: str) -> tuple[int, ...]:
    return tuple(int(p) for p in re.findall(r"\d+", text)[:3])


def satisfies(version: str, spec: str | None) -> bool:
    """Whether a Python version satisfies a `requires-python` specifier (>=, >, <=, <, ==, !=, ~=; wildcards)."""
    if not spec:
        return True
    have = _version_tuple(version)
    for clause in (c.strip() for c in spec.split(",") if c.strip()):
        match = re.match(r"(~=|==|!=|>=|<=|>|<)\s*([\d.*]+)", clause)
        if not match:
            continue
        op, raw = match.groups()
        want = _version_tuple(raw.replace("*", "0"))
        size = len(want)
        mine = (have + (0, 0, 0))[:size]
        if raw.endswith(".*"):
            prefix = want[:-1]
            equal = have[: len(prefix)] == prefix
            if (op == "==" and not equal) or (op == "!=" and equal):
                return False
            continue
        if op == "~=":
            if mine < want or have[: size - 1] != want[: size - 1]:
                return False
        elif not {"==": mine == want, "!=": mine != want, ">=": mine >= want, "<=": mine <= want,
                  ">": mine > want, "<": mine < want}[op]:
            return False
    return True


# --- Python ------------------------------------------------------------------------------------

def _pyproject(root: Path) -> dict:
    try:
        return tomllib.loads((root / "pyproject.toml").read_text(encoding="utf-8"))
    except (OSError, tomllib.TOMLDecodeError):
        return {}


UNVERIFIABLE = "<path or URL requirement>"


def python_requirements(root: Path) -> tuple[list[str], list[str], list[Path]]:
    """(distribution names, install arguments, requirement files) the tests need, from the project's own files.
    A path, URL or included file cannot be checked by name: it is listed as UNVERIFIABLE, so it is installed."""
    files = sorted(p for p in root.glob("requirements*.txt") if p.is_file())
    names: list[str] = []
    for path in files:
        for line in path.read_text(encoding="utf-8", errors="replace").splitlines():
            line = line.split(" #")[0].strip()
            if not line or line.startswith("#") or line.startswith(("--hash", "--index", "--extra-index", "--find-links", "--trusted")):
                continue
            if line.startswith((".", "/", "-e", "-r", "-c")) or "://" in line or "@" in line.split(";")[0] and " @ " in line:
                names.append(UNVERIFIABLE)
            elif (m := _REQ_NAME.match(line)) and not line.startswith("-"):
                names.append(m.group(1))
    if files:
        return list(dict.fromkeys(names)), [arg for path in files for arg in ("-r", str(path))], files
    project = _pyproject(root).get("project", {})
    specs = list(project.get("dependencies") or [])
    for group in _TEST_GROUPS:
        specs += list((project.get("optional-dependencies") or {}).get(group) or [])
        specs += [s for s in (_pyproject(root).get("dependency-groups") or {}).get(group) or [] if isinstance(s, str)]
    names = [m.group(1) for s in specs if (m := _REQ_NAME.match(s))]
    return names, specs, []


def _probe(python: str) -> dict | None:
    script = "import json, platform, sys; print(json.dumps({'version': platform.python_version(), 'executable': sys.executable}))"
    result = run_command([python, "-c", script], Path.cwd(), timeout_s=60)
    try:
        return json.loads(result.stdout.strip().splitlines()[-1]) if result.ok else None
    except (ValueError, IndexError):
        return None


def _managed_interpreters() -> list[str]:
    """Interpreters already installed by version managers and per-user installers (never downloaded here):
    uv (UV_PYTHON_INSTALL_DIR or its default), pyenv / pyenv-win, python.org per-user installs on Windows."""
    home = Path.home()
    roots = [Path(os.environ["UV_PYTHON_INSTALL_DIR"])] if os.environ.get("UV_PYTHON_INSTALL_DIR") else []
    if os.name == "nt":
        appdata, local = Path(os.environ.get("APPDATA", home)), Path(os.environ.get("LOCALAPPDATA", home))
        roots += [appdata / "uv" / "python"]
        patterns = [(r, "cpython-*/python.exe") for r in roots] + [
            (home / ".pyenv" / "pyenv-win" / "versions", "*/python.exe"), (local / "Programs" / "Python", "Python3*/python.exe")]
    else:
        roots += [Path(os.environ.get("XDG_DATA_HOME", home / ".local" / "share")) / "uv" / "python"]
        patterns = [(r, "cpython-*/bin/python3") for r in roots] + [(Path(os.environ.get("PYENV_ROOT", home / ".pyenv")) / "versions", "*/bin/python3")]
    found = []
    for base, pattern in patterns:
        if base.is_dir():
            found += sorted((str(p) for p in base.glob(pattern) if p.is_file()), reverse=True)
    return found


def candidate_interpreters(given: str | None) -> list[str]:
    """The interpreter the caller named first, then this one, then those installed (the py launcher, PATH, version
    managers). Interpreters are found, never downloaded: a missing compatible one leaves the run BLOCKED."""
    out = [p for p in (given, sys.executable) if p]
    if os.name == "nt" and shutil.which("py"):
        listed = run_command(["py", "-0p"], Path.cwd(), timeout_s=30)
        out += [line.split()[-1] for line in listed.stdout.splitlines() if line.strip().endswith(".exe")]
    for minor in range(14, 7, -1):
        found = shutil.which(f"python3.{minor}")
        if found:
            out.append(found)
    out += _managed_interpreters()
    return list(dict.fromkeys(out))


def _missing(python: str, names: list[str]) -> list[str]:
    script = ("import importlib.metadata as m, json, sys\nout = []\nfor n in json.loads(sys.argv[1]):\n"
              "    try:\n        m.version(n)\n    except m.PackageNotFoundError:\n        out.append(n)\nprint(json.dumps(out))")
    result = run_command([python, "-c", script, json.dumps(names)], Path.cwd(), timeout_s=60)
    try:
        return json.loads(result.stdout.strip().splitlines()[-1])
    except (ValueError, IndexError):
        return list(names)


def _python_plan(root: Path, given: str | None, runner_needs: list[str], prepared: Prepared) -> list[Step]:
    from .python_discovery import declared_runners, python_runners

    if not (any(root.glob("**/test*.py")) or declared_runners(root)):
        return []
    spec = _pyproject(root).get("project", {}).get("requires-python")
    names, install, files = python_requirements(root)
    runner = sorted({{"pytest": "pytest", "django": "Django"}.get(r, "") for r in python_runners(root)} - {""})
    names = list(dict.fromkeys([*names, *runner, *runner_needs]))
    current = _probe(given or sys.executable)
    prepared.requirements.append({"ecosystem": "python", "requires_python": spec, "distributions": names,
                                  "files": [p.name for p in files], "interpreter": current})
    divergences = [f"{tool} lockfile {name} is not honored: dependencies come from "
                   + ("the requirement files" if files else "pyproject.toml ranges") for name, tool in _LOCKFILES.items() if (root / name).is_file()]
    compatible = current if current and satisfies(current["version"], spec) else None
    probed = {current["version"]} if current else set()
    if compatible is None:
        for candidate in candidate_interpreters(given)[1:]:
            probe = _probe(candidate)
            if probe:
                probed.add(probe["version"])
            if probe and satisfies(probe["version"], spec):
                compatible = probe
                break
    if compatible is None:
        return [Step("python-interpreter", "python", "select a compatible interpreter",
                     f"requires-python {spec}; available {current['version'] if current else 'none'}", status="BLOCKED",
                     detail=f"no installed Python satisfies {spec} (probed: {', '.join(sorted(probed)) or 'none'}); interpreters are "
                            "found, never downloaded by this version: install a matching one (python.org, uv python install, pyenv) "
                            "and pass --python, or rerun; runtime incompatible, not a project defect")]
    missing = _missing(compatible["executable"], [n for n in names if n != UNVERIFIABLE])
    if UNVERIFIABLE in names:
        missing.append(UNVERIFIABLE)
    if compatible is current and not missing:
        prepared.python = current["executable"]
        return [Step("python-env", "python", "use the given interpreter", "every declared distribution is installed",
                     status="NOT_NEEDED", divergences=divergences)]
    # coverage.py is the engine's measuring instrument: added to an environment being created anyway, and said so
    instrument = ["coverage"] if "coverage" not in {n.lower() for n in names} else []
    if instrument:
        divergences.append("coverage.py is added to the prepared environment by Assertiva to measure coverage; the project does not declare it")
    return [Step("python-env", "python", f"create a virtual environment with Python {compatible['version']} and install "
                 + (", ".join(missing[:8]) + ("…" if len(missing) > 8 else "") if missing else "nothing"),
                 ("interpreter " + (current or {}).get("version", "none") + f" does not satisfy {spec}; " if compatible is not current else "")
                 + (f"{len(missing)} declared distributions are not installed" if missing else "all distributions present"),
                 downloads=["PyPI (pip)"] if missing else [], runs_third_party_code=bool(missing), divergences=divergences,
                 detail=json.dumps({"root": str(root), "base": compatible["executable"],
                                    "install": [*(install if files else [*install, *runner, *runner_needs]), *instrument],
                                    "missing": missing}))]


def _prepare_python(step: Step, prepared: Prepared) -> None:
    data = json.loads(step.detail)
    venv = prepared.workspace / "env" / "py"
    created = run_command([data["base"], "-m", "venv", str(venv)], Path.cwd(), timeout_s=300)
    if not created.ok:
        hint = (f"; the path ({len(str(venv))} characters) may exceed the Windows 260-character limit: a shorter ASSERTIVA_HOME helps"
                if os.name == "nt" and len(str(venv)) > 120 else "")
        raise ProvisioningError(f"virtual environment could not be created: {created.summary()}{hint}")
    python = str(venv / ("Scripts/python.exe" if os.name == "nt" else "bin/python"))
    if data["missing"]:
        from assertiva.workspace import snapshot

        # pip resolves relative requirement paths from its working directory, and builds may write next to the
        # sources (egg-info): it runs in a copy of the project in the run workspace, never in the project.
        source = snapshot(data["root"], prepared.workspace / "env" / "install-source")
        install = [str(source / Path(a).relative_to(data["root"])) if Path(a).is_absolute() and Path(a).is_relative_to(data["root"]) else a
                   for a in data["install"]]
        env = {**os.environ, "PIP_CACHE_DIR": str(tools_dir() / "pip-cache"), "PIP_DISABLE_PIP_VERSION_CHECK": "1", "PIP_NO_INPUT": "1"}
        installed = run_command([python, "-m", "pip", "install", *install], source, env=env, timeout_s=1800)
        if not installed.ok:
            raise ProvisioningError(f"dependencies could not be installed: {installed.summary()}")
    prepared.python = python
    step.detail = f"virtual environment {venv}"


# --- Node --------------------------------------------------------------------------------------

def _node_plan(root: Path, prepared: Prepared) -> list[Step]:
    package = root / "package.json"
    if not package.is_file():
        return []
    try:
        data = json.loads(package.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return []
    deps = {**(data.get("dependencies") or {}), **(data.get("devDependencies") or {})}
    locks = [name for name in _NODE_LOCKS if (root / name).is_file()]
    prepared.requirements.append({"ecosystem": "node", "dependencies": len(deps), "lockfiles": locks,
                                  "engines": (data.get("engines") or {}).get("node"), "installed": (root / "node_modules").is_dir()})
    if not deps or (root / "node_modules").is_dir():
        return [Step("node-modules", "node", "use the project's installed node_modules (linked, not copied)" if deps else "no dependencies",
                     "already installed" if deps else "package.json declares none", status="NOT_NEEDED")]
    npm_lock = next((n for n in locks if _NODE_LOCKS[n] == "npm"), None)
    if not npm_lock:
        manager = _NODE_LOCKS[locks[0]] if locks else None
        return [Step("node-modules", "node", "install dependencies", "node_modules is missing", status="BLOCKED",
                     detail=(f"the project locks dependencies with {manager}; only npm lockfiles are provisioned" if manager
                             else "no lockfile: installing unlocked dependency ranges would not reproduce the project"))]
    if not shutil.which("npm"):
        return [Step("node-modules", "node", "install dependencies with npm ci", "node_modules is missing", status="BLOCKED",
                     detail="npm was not found on PATH; this version does not download Node.js")]
    return [Step("node-modules", "node", f"npm ci --ignore-scripts from {npm_lock} into the run workspace", "node_modules is missing",
                 downloads=["npm registry"], runs_third_party_code=False,
                 divergences=["package install scripts are not run (--ignore-scripts); packages that need them can fail"],
                 detail=json.dumps({"lock": npm_lock}))]


def _prepare_node(step: Step, prepared: Prepared, root: Path) -> None:
    lock = json.loads(step.detail)["lock"]
    target = prepared.workspace / "env" / "node"
    target.mkdir(parents=True, exist_ok=True)
    for name in ("package.json", lock, ".npmrc"):
        if (root / name).is_file() and name != ".npmrc":
            shutil.copy2(root / name, target / name)
    env = {**os.environ, "npm_config_cache": str(tools_dir() / "npm-cache"), "npm_config_audit": "false", "npm_config_fund": "false"}
    installed = run_command([shutil.which("npm"), "ci", "--ignore-scripts", "--no-audit", "--no-fund"], target, env=env, timeout_s=1800)
    if not installed.ok:
        raise ProvisioningError(f"npm ci failed: {installed.summary()}")
    prepared.dirs["node_modules"] = target / "node_modules"
    step.detail = f"node_modules in {target}"


# --- JVM ---------------------------------------------------------------------------------------

def _java_home() -> str | None:
    home = os.environ.get("JAVA_HOME")
    if home and (Path(home) / "bin" / ("java.exe" if os.name == "nt" else "java")).is_file():
        return home
    java = shutil.which("java")
    return str(Path(java).resolve().parent.parent) if java else None


def jdk_major(home: str | Path) -> int | None:
    """The feature version of the JDK at ``home``, from its ``release`` file (``JAVA_VERSION="21.0.5"`` or ``"1.8.0_402"``)."""
    try:
        text = (Path(home) / "release").read_text(encoding="utf-8", errors="replace")
    except OSError:
        return None
    match = re.search(r'^JAVA_VERSION="(\d+)(?:\.(\d+))?', text, re.M)
    if not match:
        return None
    major = int(match.group(1))
    return int(match.group(2) or 0) if major == 1 else major


def declared_jdk(root: Path) -> int | None:
    for path in [*root.glob("*.gradle"), *root.glob("*.gradle.kts"), *root.glob("*/build.gradle*"), root / "pom.xml"]:
        try:
            text = path.read_text(encoding="utf-8", errors="replace")
        except OSError:
            continue
        for pattern in _JDK_DECLARED:
            if match := pattern.search(text):
                return int(match.group(1))
    return None


def gradle_wrapper(root: Path) -> dict | None:
    """Declared Gradle version and checksum from gradle/wrapper/gradle-wrapper.properties (read, never executed)."""
    path = root / "gradle" / "wrapper" / "gradle-wrapper.properties"
    try:
        text = path.read_text(encoding="utf-8")
    except OSError:
        return None
    props = dict(line.split("=", 1) for line in text.splitlines() if "=" in line and not line.lstrip().startswith("#"))
    url = props.get("distributionUrl", "").replace("\\:", ":")
    match = re.search(r"gradle-([0-9][0-9A-Za-z.\-]*?)-(bin|all)\.zip$", url)
    return {"version": match.group(1), "sha256": props.get("distributionSha256Sum", "").strip() or None, "url": url} if match else None


def _os_arch() -> tuple[str, str]:
    system = {"Windows": "windows", "Darwin": "mac", "Linux": "linux"}.get(platform.system(), platform.system().lower())
    machine = platform.machine().lower()
    arch = {"amd64": "x64", "x86_64": "x64", "arm64": "aarch64", "aarch64": "aarch64"}.get(machine, machine)
    return system, arch


def _jvm_plan(root: Path, prepared: Prepared) -> list[Step]:
    gradle = any((root / n).is_file() for n in ("build.gradle", "build.gradle.kts", "settings.gradle", "settings.gradle.kts"))
    maven = (root / "pom.xml").is_file()
    if not (gradle or maven):
        return []
    feature = declared_jdk(root)
    home = _java_home()
    installed = jdk_major(home) if home else None
    wrapper = gradle_wrapper(root) if gradle else None
    prepared.requirements.append({"ecosystem": "jvm", "build": "gradle" if gradle else "maven", "jdk_declared": feature,
                                  "jdk_available": home, "gradle_wrapper": wrapper})
    steps = []
    # the installed JDK serves when the build's toolchain is that version (or none is declared) and it can run Gradle
    mismatch = home is not None and ((feature is not None and installed != feature) or (gradle and (installed or 0) < MIN_GRADLE_JDK))
    if home is None or mismatch:
        version = feature or DEFAULT_JDK
        why = ("no JDK on this machine" if home is None else
               f"the installed JDK ({installed or 'unknown version'}) is not the build's toolchain {feature}" if feature is not None
               else f"the installed JDK ({installed or 'unknown version'}) cannot run Gradle (needs {MIN_GRADLE_JDK}+)")
        steps.append(Step("jdk", "jvm", f"Temurin JDK {version} into the tools cache",
                          why + ("" if feature else f"; the build declares no toolchain, JDK {DEFAULT_JDK} is used"),
                          downloads=["api.adoptium.net / github.com/adoptium"], detail=json.dumps({"feature": version})))
    else:
        prepared.tools["java_home"] = home
        steps.append(Step("jdk", "jvm", f"use the JDK at {home}", "a JDK is installed", status="NOT_NEEDED"))
    if gradle and any(re.search(r"com\.android\.(application|library)", p.read_text(encoding="utf-8", errors="replace"))
                      for p in [*root.glob("*/build.gradle*"), *root.glob("build.gradle*")] if "apply false" not in p.read_text(encoding="utf-8", errors="replace")):
        sdk = os.environ.get("ANDROID_HOME") or os.environ.get("ANDROID_SDK_ROOT")
        steps.append(Step("android-sdk", "jvm", f"use the Android SDK at {sdk}" if sdk else "an Android SDK",
                          "the build applies the Android Gradle plugin", status="NOT_NEEDED" if sdk else "BLOCKED",
                          detail="" if sdk else "this version does not download the Android SDK (a large download): set ANDROID_HOME to an "
                          "installed SDK; local unit tests stay BLOCKED and instrumented tests need a device or emulator either way"))
    if gradle:
        version = (wrapper or {}).get("version")
        steps.append(Step("gradle", "jvm", f"Gradle {version or 'current'} distribution into the tools cache",
                          "the build declares Gradle" + ("" if wrapper else " without a wrapper; the current release is used"),
                          downloads=["services.gradle.org"],
                          divergences=[] if wrapper else ["no wrapper: the Gradle version the project expects is unknown"],
                          detail=json.dumps(wrapper or {})))
    return steps


def _prepare_jdk(step: Step, prepared: Prepared) -> None:
    feature = json.loads(step.detail)["feature"]
    system, arch = _os_arch()
    home = tools_dir() / "jdk" / f"temurin-{feature}-{system}-{arch}"
    if not (home / "bin").is_dir():
        query = f"https://api.adoptium.net/v3/assets/latest/{feature}/hotspot?architecture={arch}&image_type=jdk&os={system}&vendor=eclipse"
        from assertiva.environment import _extended, _read_url

        assets = json.loads(_read_url(query, 1 << 20))
        package = assets[0]["binary"]["package"]
        archive = download(package["link"], package["checksum"], package["name"])
        staging = home.with_name(home.name + ".staging")
        shutil.rmtree(_extended(staging), ignore_errors=True)  # deep entries: extended-length paths on Windows
        extract(archive, staging)
        [top] = [p for p in staging.iterdir() if p.is_dir()]
        shutil.rmtree(_extended(home), ignore_errors=True)
        os.replace(top, home)
        shutil.rmtree(_extended(staging), ignore_errors=True)
        step.status = "DONE"
    else:
        step.status = "REUSED"
    prepared.tools["java_home"] = str(home)
    step.detail = str(home)


def _prepare_gradle(step: Step, prepared: Prepared) -> None:
    wrapper = json.loads(step.detail) if step.detail else {}
    version = wrapper.get("version")
    if not version:
        from assertiva.environment import _read_url

        version = json.loads(_read_url("https://services.gradle.org/versions/current", 1 << 16))["version"]
    home = tools_dir() / "gradle" / version
    if not (home / "bin").is_dir():
        url = f"https://services.gradle.org/distributions/gradle-{version}-bin.zip"
        sha = wrapper.get("sha256") if wrapper.get("url", "").endswith("-bin.zip") else None
        sha = sha or published_sha256(url + ".sha256")
        archive = download(url, sha, f"gradle-{version}-bin.zip")
        staging = home.with_name(version + ".staging")
        shutil.rmtree(staging, ignore_errors=True)
        extract(archive, staging)
        [top] = [p for p in staging.iterdir() if p.is_dir()]
        home.parent.mkdir(parents=True, exist_ok=True)
        shutil.rmtree(home, ignore_errors=True)
        os.replace(top, home)
        shutil.rmtree(staging, ignore_errors=True)
        if os.name != "nt":
            os.chmod(home / "bin" / "gradle", 0o755)
        step.status = "DONE"
    else:
        step.status = "REUSED"
    prepared.tools["gradle"] = str(home / "bin" / ("gradle.bat" if os.name == "nt" else "gradle"))
    prepared.env["GRADLE_USER_HOME"] = str(tools_dir() / "gradle-home")
    step.detail = str(home)


# --- plan and prepare --------------------------------------------------------------------------

def plan(root: str | Path, python: str | None, prepared: Prepared) -> list[Step]:
    root = Path(root)
    steps = [*_python_plan(root, python, [], prepared), *_node_plan(root, prepared), *_jvm_plan(root, prepared)]
    from .services import service_plan

    steps += service_plan(root, prepared)
    return steps


def prepare(root: str | Path, steps: list[Step], prepared: Prepared, consented: bool) -> None:
    """Carry out the plan in the run workspace when the user consented; otherwise mark what needed consent BLOCKED."""
    from .services import prepare_service

    root = Path(root)
    handlers = {"python-env": lambda s: _prepare_python(s, prepared), "node-modules": lambda s: _prepare_node(s, prepared, root),
                "jdk": lambda s: _prepare_jdk(s, prepared), "gradle": lambda s: _prepare_gradle(s, prepared)}
    for step in steps:
        if step.status != "PLANNED":
            continue
        handler = handlers.get(step.step_id) or (lambda s: prepare_service(s, prepared))
        if not consented:
            step.status = "BLOCKED"
            step.detail = "needs the user's consent to download and install (audit --provision, or provision = true in consent.toml)"
            continue
        started = time.perf_counter()
        try:
            handler(step)
            if step.status == "PLANNED":
                step.status = "DONE"
        except (ProvisioningError, OSError, ValueError, KeyError, IndexError) as exc:
            step.status = "FAILED"
            step.detail = f"{type(exc).__name__}: {exc}"[:400]
        step.duration_s = round(time.perf_counter() - started, 3)
    if "java_home" in prepared.tools:
        prepared.env["JAVA_HOME"] = prepared.tools["java_home"]
        prepared.path_prefix.insert(0, str(Path(prepared.tools["java_home"]) / "bin"))
