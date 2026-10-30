"""Dependency inventory and migration readiness (opt-in: ``assertiva audit --dependencies``). Offline; changes nothing.

For each dependency the manifests declare, four versions are kept apart because they answer different questions:
the declared range (what the project accepts), the locked version (what a lockfile resolves), the installed version
(what this machine has: ``node_modules`` or the target interpreter) and the version a run used (only an execution
says that; it is not inferred here). A lock outside its declared range, a dependency with no lock and an installed
version that differs from the lock are findings with their basis.

Usage is read statically for Python: which product modules import a dependency and whether any test imports those
modules. Migration readiness is READY_WITH_GAPS at most from this static view (tests reach the code that uses the
dependency, nothing ran a candidate upgrade), BLOCKED when the dependency cannot be resolved offline, UNKNOWN
otherwise; READY needs an executed upgrade in a disposable copy, which this version does not perform.

Vulnerabilities are not looked up: no advisory database is bundled or downloaded. ``vulnerabilities`` says so and
names the tool to reuse (OSV-Scanner on the lockfile), instead of an empty list that would read as "none".
"""

from __future__ import annotations

import ast
import json
import re
import subprocess
import tomllib
from pathlib import Path

from .adapters.workspaces import REQUIREMENT_NAME

# folders that hold environments, dependencies or build output, never the project's own source
SKIPPED_DIRS = frozenset({".git", ".venv", "venv", "node_modules", "__pycache__", "build", "dist", ".tox", "site-packages"})
_IMPORT_NAMES = {"pyyaml": "yaml", "pillow": "PIL", "beautifulsoup4": "bs4", "scikit-learn": "sklearn", "python-dateutil": "dateutil",
                 "opencv-python": "cv2", "attrs": "attr", "protobuf": "google", "pyjwt": "jwt", "python-dotenv": "dotenv"}


def _norm(name: str) -> str:
    return re.sub(r"[-_.]+", "-", name).lower()


def _python_declared(root: Path) -> dict[str, dict]:
    out: dict[str, dict] = {}
    try:
        data = tomllib.loads((root / "pyproject.toml").read_text(encoding="utf-8"))
    except (OSError, tomllib.TOMLDecodeError):
        data = {}
    project = data.get("project") or {}
    groups = [("runtime", project.get("dependencies") or [])] + [
        (f"extra:{k}", v) for k, v in (project.get("optional-dependencies") or {}).items()]
    for path in sorted(root.glob("requirements*.txt")):
        lines = path.read_text(encoding="utf-8", errors="replace").splitlines()
        groups.append((path.name, [l for l in lines if l.strip() and not l.strip().startswith(("#", "-"))]))
    for group, reqs in groups:
        for req in reqs if isinstance(reqs, list) else []:
            match = REQUIREMENT_NAME.match(str(req))
            if match:
                name = _norm(match.group(1))
                entry = out.setdefault(name, {"ecosystem": "python", "name": match.group(1), "declared": [], "groups": []})
                entry["declared"].append(re.sub(r"^\s*\[[^\]]*\]", "", str(req)[match.end():]).split(";")[0].split("#")[0].strip() or "*")
                entry["groups"].append(group)
    return out


def _python_locked(root: Path) -> tuple[dict[str, str], str | None]:
    for lock in ("uv.lock", "poetry.lock", "pdm.lock"):
        path = root / lock
        if path.is_file():
            try:
                data = tomllib.loads(path.read_text(encoding="utf-8"))
            except tomllib.TOMLDecodeError:
                return {}, f"{lock} (unreadable)"
            return {_norm(p["name"]): str(p.get("version")) for p in data.get("package") or [] if p.get("name")}, lock
    pinned = {}
    for path in sorted(root.glob("requirements*.txt")):
        for line in path.read_text(encoding="utf-8", errors="replace").splitlines():
            match = re.match(r"^\s*([A-Za-z0-9][A-Za-z0-9._-]*)\s*==\s*([^\s;#]+)", line)
            if match:
                pinned[_norm(match.group(1))] = match.group(2)
    return pinned, ("pinned requirements" if pinned else None)


def _python_installed(python: str | None, names: list[str]) -> dict[str, str]:
    if not python or not names:
        return {}
    probe = ("import json, sys\nfrom importlib import metadata\nout = {}\nfor n in sys.argv[1:]:\n    try:\n"
             "        out[n] = metadata.version(n)\n    except metadata.PackageNotFoundError:\n        pass\nprint(json.dumps(out))")
    from .process import probe_directory

    with probe_directory() as cwd:
        done = subprocess.run([python, "-I", "-c", probe, *names], cwd=cwd, capture_output=True, text=True, timeout=60, check=False)
    try:
        return {_norm(k): v for k, v in json.loads(done.stdout or "{}").items()}
    except ValueError:
        return {}


def _satisfies_python(version: str, spec: str) -> bool | None:
    try:
        from packaging.specifiers import InvalidSpecifier, SpecifierSet
        from packaging.version import InvalidVersion, Version
    except ImportError:
        try:
            from pip._vendor.packaging.specifiers import InvalidSpecifier, SpecifierSet
            from pip._vendor.packaging.version import InvalidVersion, Version
        except ImportError:
            return None
    if spec in ("", "*"):
        return True
    try:
        return Version(version) in SpecifierSet(spec)
    except (InvalidSpecifier, InvalidVersion):
        return None


def _js(root: Path) -> tuple[dict[str, dict], dict[str, str], str | None, dict[str, str]]:
    try:
        package = json.loads((root / "package.json").read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}, {}, None, {}
    declared = {}
    for group in ("dependencies", "devDependencies", "optionalDependencies"):
        for name, spec in (package.get(group) or {}).items():
            declared[name] = {"ecosystem": "npm", "name": name, "declared": [str(spec)], "groups": [group]}
    locked, lock = {}, None
    try:
        data = json.loads((root / "package-lock.json").read_text(encoding="utf-8"))
        lock = "package-lock.json"
        locked = {key.split("node_modules/")[-1]: str(v.get("version")) for key, v in (data.get("packages") or {}).items()
                  if key.startswith("node_modules/") and "/node_modules/" not in key[len("node_modules/"):] and v.get("version")}
    except (OSError, ValueError):
        pass
    installed = {}
    for name in declared:
        try:
            installed[name] = str(json.loads((root / "node_modules" / name / "package.json").read_text(encoding="utf-8"))["version"])
        except (OSError, ValueError, KeyError):
            pass
    return declared, locked, lock, installed


def _satisfies_npm(version: str, spec: str) -> bool | None:
    """Exact, ^, ~, >=, x-ranges and *; anything else (||, tags, URLs, workspaces) is not decided."""
    def parts(text):
        nums = re.findall(r"\d+", text)
        return [int(n) for n in nums[:3]] + [0] * (3 - len(nums[:3]))

    spec = spec.strip()
    if spec in ("*", ""):
        return True
    if not re.fullmatch(r"[\^~]?\s*\d+(\.(\d+|x|\*))*(\.(\d+|x|\*))?|>=\s*\d+(\.\d+){0,2}", spec) or not re.match(r"\d", version):
        return None
    have, want = parts(version), parts(spec)
    if spec.startswith(">="):
        return have >= want
    if "x" in spec or "*" in spec:
        fixed = len([p for p in spec.lstrip("^~").split(".") if p.isdigit()])
        return have[:fixed] == want[:fixed]
    if spec.startswith("^"):
        lead = next((i for i, n in enumerate(want) if n != 0), 2)
        return have[: lead + 1] == want[: lead + 1] and have >= want
    if spec.startswith("~"):
        return have[:2] == want[:2] and have >= want
    return have == want


def _python_usage(root: Path) -> tuple[dict[str, set[str]], dict[str, set[str]]]:
    """(top-level import -> product files importing it, dotted module a test imports -> those test files)."""
    from .adapters.python_discovery import test_files

    tests = {p.resolve() for p in test_files(root)}
    imports: dict[str, set[str]] = {}
    reached: dict[str, set[str]] = {}
    for path in sorted(root.rglob("*.py")):
        rel_parts = path.relative_to(root).parts
        if SKIPPED_DIRS & set(rel_parts):
            continue
        try:
            tree = ast.parse(path.read_text(encoding="utf-8"))
        except (SyntaxError, UnicodeDecodeError, OSError):
            continue
        dotted = {a.name for n in ast.walk(tree) if isinstance(n, ast.Import) for a in n.names}
        for n in ast.walk(tree):
            if isinstance(n, ast.ImportFrom) and n.module and not n.level:
                dotted |= {n.module, *(f"{n.module}.{a.name}" for a in n.names)}
        rel = path.relative_to(root).as_posix()
        if path.resolve() in tests:
            for name in dotted:
                reached.setdefault(name, set()).add(rel)
        else:
            for name in {d.split(".")[0] for d in dotted}:
                imports.setdefault(name, set()).add(rel)
    return imports, reached


def inventory(root: str | Path, python: str | None = None) -> dict:
    root = Path(root)
    entries = []
    py_declared = _python_declared(root)
    py_locked, py_lock = _python_locked(root)
    py_installed = _python_installed(python, sorted(py_declared))
    imports, reached = _python_usage(root) if py_declared else ({}, {})
    for key, entry in sorted(py_declared.items()):
        module = _IMPORT_NAMES.get(key, key.replace("-", "_"))
        product = sorted(imports.get(module, set()))
        product_modules = {Path(f).with_suffix("").as_posix().removeprefix("src/").removesuffix("/__init__").replace("/", ".")
                           for f in product}
        tests = sorted({t for m in product_modules for name, files in reached.items()
                        if name == m or name.startswith(m + ".") for t in files})
        entries.append(_entry(entry, py_locked.get(key), py_lock, py_installed.get(key), _satisfies_python,
                              {"basis": "STATIC: imports read from the source", "import_name": module, "product_files": product[:20],
                               "tests_reaching_them": tests[:20]}))
    js_declared, js_locked, js_lock, js_installed = _js(root)
    for name, entry in sorted(js_declared.items()):
        entries.append(_entry(entry, js_locked.get(name), js_lock, js_installed.get(name), _satisfies_npm,
                              {"basis": "NOT_ANALYZED: JavaScript usage is not mapped in this version"}))
    return {"dependencies": entries, "lockfiles": [x for x in (py_lock, js_lock) if x],
            "vulnerabilities": {"status": "UNKNOWN", "why": "no advisory database is bundled or downloaded (offline)",
                                "reuse": "OSV-Scanner on the lockfile (osv-scanner scan source -L <lockfile>), offline mode with a local database"},
            "used_version": "UNKNOWN: which version a run imported is known only from an execution",
            "note": "nothing was installed, upgraded or sent anywhere"}


def _entry(entry: dict, locked: str | None, lock: str | None, installed: str | None, satisfies, usage: dict) -> dict:
    spec = ",".join(s for s in entry["declared"] if s and s != "*") or "*"
    lock_ok = satisfies(locked, spec) if locked else None
    if not locked:
        lock_state = "NOT_LOCKED"
    else:
        lock_state = {True: "LOCK_SATISFIES_RANGE", False: "LOCK_OUTSIDE_RANGE", None: "UNKNOWN"}[lock_ok]
    install_state = ("NOT_INSTALLED_HERE" if installed is None else "INSTALLED_MATCHES_LOCK" if installed == locked
                     else "INSTALLED_DIFFERS_FROM_LOCK" if locked else "INSTALLED_UNLOCKED")
    product = usage.get("product_files")
    if product is None:
        readiness, why = "UNKNOWN", "usage of this ecosystem is not mapped"
    elif not product:
        readiness, why = "UNKNOWN", "no product module imports it under its usual name (plugins, entry points or another import name)"
    elif usage.get("tests_reaching_them"):
        readiness, why = "READY_WITH_GAPS", "tests import the product modules that use it; no candidate upgrade was executed"
    else:
        readiness, why = "READY_WITH_GAPS", "product code uses it and no test imports those modules: an upgrade would be unverified"
    return {**{k: entry[k] for k in ("ecosystem", "name", "groups")}, "declared_range": spec, "locked": locked, "lockfile": lock,
            "installed": installed, "lock_state": lock_state, "install_state": install_state, "usage": usage,
            "migration_readiness": readiness, "readiness_basis": why}


def findings(data: dict) -> list:
    from .models import Finding

    out = []
    outside = [d for d in data["dependencies"] if d["lock_state"] == "LOCK_OUTSIDE_RANGE"]
    if outside:
        out.append(Finding("DEPENDENCY_LOCK_OUTSIDE_RANGE", "A lockfile resolves dependencies to versions their declared range does not accept.",
                           {"dependencies": [{"name": d["name"], "declared": d["declared_range"], "locked": d["locked"]} for d in outside][:20]}))
    drift = [d for d in data["dependencies"] if d["install_state"] == "INSTALLED_DIFFERS_FROM_LOCK"]
    if drift:
        out.append(Finding("DEPENDENCY_INSTALLED_DIFFERS_FROM_LOCK", "The installed versions differ from the locked ones; local runs test other dependencies than the lock.",
                           {"dependencies": [{"name": d["name"], "locked": d["locked"], "installed": d["installed"]} for d in drift][:20]}))
    untested = [d for d in data["dependencies"] if d["usage"].get("product_files") and not d["usage"].get("tests_reaching_them")]
    if untested:
        out.append(Finding("DEPENDENCY_USAGE_UNTESTED", "Product code uses dependencies that no test reaches; upgrading them would be unverified.",
                           {"dependencies": [{"name": d["name"], "product_files": d["usage"]["product_files"][:5]} for d in untested][:20],
                            "basis": "STATIC"}, severity="info"))
    return out
