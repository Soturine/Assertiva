"""Which languages and frameworks a project uses, and how we know (adapter knowledge, not core policy).

The primary language's basis is SOURCE (counted files). The stack (containers, databases, brokers) is listed apart, with the same bases: a service image in Compose or CI
or a database engine in settings is CONFIGURED; a driver in the dependencies is DECLARED. Every other entry carries its basis, strongest first: EXECUTED (a runner adapter ran it in this run), CONFIGURED (the
project's own configuration or entry point for it exists), DECLARED (only listed as a dependency: presence, not
proven use). The primary language is the one with the most source files among the project's files. Used for the
report header only; it never changes what is measured.
"""

from __future__ import annotations

import json
import re
import tomllib
from collections import Counter
from pathlib import Path

LANGUAGES = {
    ".py": ("python", "Python"), ".js": ("javascript", "JavaScript"), ".mjs": ("javascript", "JavaScript"),
    ".cjs": ("javascript", "JavaScript"), ".jsx": ("javascript", "JavaScript"), ".ts": ("typescript", "TypeScript"),
    ".tsx": ("typescript", "TypeScript"), ".mts": ("typescript", "TypeScript"), ".java": ("java", "Java"),
    ".kt": ("kotlin", "Kotlin"), ".kts": ("kotlin", "Kotlin"), ".cs": ("csharp", "C#"), ".go": ("go", "Go"),
    ".rs": ("rust", "Rust"), ".php": ("php", "PHP"), ".rb": ("ruby", "Ruby"), ".swift": ("swift", "Swift"),
}
NAMES = {
    "django": "Django", "pytest": "pytest", "unittest": "unittest", "jest": "Jest", "vitest": "Vitest", "playwright": "Playwright",
    "maven": "Maven", "gradle": "Gradle", "react": "React", "vue": "Vue", "angular": "Angular", "dotnet": ".NET",
    "typescript": "TypeScript", "go": "Go", "rust": "Rust", "php": "PHP", "node": "Node.js",
    "docker": "Docker", "postgresql": "PostgreSQL", "mysql": "MySQL", "mariadb": "MariaDB", "mongodb": "MongoDB", "redis": "Redis",
    "sqlite": "SQLite", "rabbitmq": "RabbitMQ", "elasticsearch": "Elasticsearch",
}
STACK = {"docker", "postgresql", "mysql", "mariadb", "mongodb", "redis", "sqlite", "rabbitmq", "elasticsearch"}
_DOCKER_FILES = ("Dockerfile", "docker-compose.yml", "docker-compose.yaml", "compose.yml", "compose.yaml")
# service image name (last path segment, before the tag) -> technology
_IMAGES = {"postgres": "postgresql", "postgis": "postgresql", "mysql": "mysql", "mariadb": "mariadb", "mongo": "mongodb",
           "redis": "redis", "rabbitmq": "rabbitmq", "elasticsearch": "elasticsearch"}
_ENGINES = {"postgresql": "postgresql", "postgis": "postgresql", "mysql": "mysql", "sqlite3": "sqlite"}
_PY_DRIVERS = {"psycopg": "postgresql", "psycopg2": "postgresql", "psycopg2-binary": "postgresql", "asyncpg": "postgresql",
               "mysqlclient": "mysql", "pymysql": "mysql", "mysql-connector-python": "mysql", "pymongo": "mongodb", "motor": "mongodb",
               "mongoengine": "mongodb", "redis": "redis", "django-redis": "redis", "pika": "rabbitmq", "elasticsearch": "elasticsearch"}
_NPM_DRIVERS = {"pg": "postgresql", "mysql": "mysql", "mysql2": "mysql", "mongodb": "mongodb", "mongoose": "mongodb", "redis": "redis",
                "ioredis": "redis", "sqlite3": "sqlite", "better-sqlite3": "sqlite", "amqplib": "rabbitmq"}
MAX_STACK = 3
# configuration file (exact name or suffix) -> technology it configures
_CONFIGURED = [
    ("vitest.config.", "vitest"), ("jest.config.", "jest"), ("playwright.config.", "playwright"), ("pom.xml", "maven"),
    ("build.gradle", "gradle"), ("settings.gradle", "gradle"), ("tsconfig.json", "typescript"), (".csproj", "dotnet"),
    (".sln", "dotnet"), ("go.mod", "go"), ("Cargo.toml", "rust"), ("composer.json", "php"),
]
_NPM = {"react": "react", "vue": "vue", "@angular/core": "angular", "jest": "jest", "vitest": "vitest", "@playwright/test": "playwright",
        "typescript": "typescript"}
_RUNNERS = {"pytest-native": "pytest"}
_ORDER = {"EXECUTED": 0, "CONFIGURED": 1, "DECLARED": 2}
MAX_TECHNOLOGIES = 3


def _python_dependencies(root: Path) -> set[str]:
    names: set[str] = set()
    for path in root.glob("requirements*.txt"):
        try:
            names |= {line.split("#")[0].strip().split("[")[0].split("=")[0].split(">")[0].split("<")[0].split("~")[0].strip().lower()
                      for line in path.read_text(encoding="utf-8", errors="replace").splitlines()}
        except OSError:
            pass
    try:
        project = tomllib.loads((root / "pyproject.toml").read_text(encoding="utf-8")).get("project", {})
        for spec in project.get("dependencies", []):
            names.add(spec.split("[")[0].split("=")[0].split(">")[0].split("<")[0].split("~")[0].split(";")[0].strip().lower())
    except (OSError, ValueError, AttributeError):
        pass
    return names


def _service_images(root: Path, files: list[str]) -> list[tuple[str, str]]:
    """(technology, evidence) for service images declared by Compose files and CI workflow services."""
    import yaml

    found = []
    sources = [f for f in files if f in _DOCKER_FILES[1:]]
    sources += [f for f in files if f.startswith(".github/workflows/") and f.endswith((".yml", ".yaml"))]
    for rel in sources:
        try:
            document = yaml.safe_load((root / rel).read_text(encoding="utf-8")) or {}
        except (OSError, UnicodeDecodeError, yaml.YAMLError):
            continue
        groups = [document.get("services")] if rel in _DOCKER_FILES else [
            job.get("services") for job in (document.get("jobs") or {}).values() if isinstance(job, dict)]
        for services in groups:
            for name, service in (services or {}).items() if isinstance(services, dict) else ():
                image = str(service.get("image", "")) if isinstance(service, dict) else ""
                base = image.split("@")[0].split(":")[0].rsplit("/", 1)[-1].lower()
                if base in _IMAGES:
                    found.append((_IMAGES[base], f"{rel} service {name} ({image})"))
    return found


def _settings_engines(root: Path, files: list[str]) -> list[tuple[str, str]]:
    """Database engines a Django settings module configures (`django.db.backends.<engine>`)."""
    found = []
    for rel in files:
        if rel.count("/") <= 2 and Path(rel).name.startswith("settings") and rel.endswith(".py"):
            try:
                text = (root / rel).read_text(encoding="utf-8", errors="replace")
            except OSError:
                continue
            for engine in re.findall(r"django\.(?:contrib\.gis\.)?db\.backends\.(\w+)", text):
                if engine in _ENGINES:
                    found.append((_ENGINES[engine], f"{rel} ENGINE {engine}"))
    return found


def project_technologies(root: str | Path, files: list[str], executed: list[str]) -> dict:
    """``files``: the project's files (relative paths); ``executed``: adapter ids that ran in this run."""
    from .python_discovery import django_manage

    root = Path(root)
    counts = Counter(LANGUAGES[Path(f).suffix.lower()] for f in files if Path(f).suffix.lower() in LANGUAGES)
    language = None
    if counts:
        (tid, name), n = counts.most_common(1)[0]
        language = {"id": tid, "name": name, "basis": "SOURCE", "evidence": f"{n}/{sum(counts.values())}"}
    found: dict[str, dict] = {}

    def add(tid: str, basis: str, evidence: str) -> None:
        current = found.get(tid)
        if (language and tid == language["id"]) or (current and _ORDER[current["basis"]] <= _ORDER[basis]):
            return
        found[tid] = {"id": tid, "name": NAMES.get(tid, tid), "basis": basis, "evidence": evidence}

    for adapter_id in executed:
        tid = _RUNNERS.get(adapter_id, adapter_id)
        add(tid, "EXECUTED", f"the {adapter_id} adapter ran the tests")
    if django_manage(root):
        add("django", "CONFIGURED", "manage.py")
    names = {f for f in files if "/" not in f}  # the project's own configuration lives at its root (not in fixtures)
    for marker, tid in _CONFIGURED:
        hit = next((n for n in sorted(names) if n == marker or (marker.startswith(".") and n.endswith(marker))
                    or (marker.endswith(".") and n.startswith(marker))), None)
        if hit:
            add(tid, "CONFIGURED", hit)
    try:
        package = json.loads((root / "package.json").read_text(encoding="utf-8"))
        deps = {**(package.get("dependencies") or {}), **(package.get("devDependencies") or {})}
    except (OSError, ValueError, AttributeError):
        deps = {}
    for dep, tid in _NPM.items():
        if dep in deps:
            add(tid, "DECLARED", f"package.json dependency {dep}")
    python_deps = _python_dependencies(root)
    if "django" in python_deps:
        add("django", "DECLARED", "Python dependency django")
    hit = next((n for n in _DOCKER_FILES if n in names), None)
    if hit:
        add("docker", "CONFIGURED", hit)
    for tid, evidence in [*_service_images(root, files), *_settings_engines(root, files)]:
        add(tid, "CONFIGURED", evidence)
    for dep, tid in _NPM_DRIVERS.items():
        if dep in deps:
            add(tid, "DECLARED", f"package.json dependency {dep}")
    for dep, tid in _PY_DRIVERS.items():
        if dep in python_deps:
            add(tid, "DECLARED", f"Python dependency {dep}")
    ranked = sorted(found.values(), key=lambda t: (_ORDER[t["basis"]], t["name"].lower()))
    frameworks = [t for t in ranked if t["id"] not in STACK]
    stack = [t for t in ranked if t["id"] in STACK]
    return {"language": language, "technologies": frameworks[:MAX_TECHNOLOGIES], "stack": stack[:MAX_STACK],
            "omitted": max(len(frameworks) - MAX_TECHNOLOGIES, 0) + max(len(stack) - MAX_STACK, 0)}


def project_version(root: str | Path) -> dict | None:
    """The version the project declares for itself, with the manifest that declares it; None when none does.

    First match wins: pyproject.toml [project], package.json, Cargo.toml [package], pom.xml (the project's own
    <version>, not its parent's), setup.cfg [metadata], a VERSION file. A dynamic or interpolated version is not a value."""
    import configparser
    import xml.etree.ElementTree as ET

    root = Path(root)

    def toml(name: str, table: str):
        try:
            return tomllib.loads((root / name).read_text(encoding="utf-8")).get(table, {}).get("version")
        except (OSError, ValueError, AttributeError):
            return None

    def package_json():
        try:
            return json.loads((root / "package.json").read_text(encoding="utf-8")).get("version")
        except (OSError, ValueError, AttributeError):
            return None

    def pom():
        try:
            tree = ET.parse(root / "pom.xml").getroot()
        except (OSError, ET.ParseError):
            return None
        ns = tree.tag.split("}")[0] + "}" if tree.tag.startswith("{") else ""
        node = tree.find(f"{ns}version")
        return node.text.strip() if node is not None and node.text else None

    def setup_cfg():
        parser = configparser.ConfigParser(interpolation=None)
        try:
            parser.read_string((root / "setup.cfg").read_text(encoding="utf-8"))
            return parser.get("metadata", "version", fallback=None)
        except (OSError, configparser.Error):
            return None

    def version_file():
        try:
            text = (root / "VERSION").read_text(encoding="utf-8").strip()
        except OSError:
            return None
        return text if text and "\n" not in text and len(text) <= 40 else None

    for source, read in (("pyproject.toml", lambda: toml("pyproject.toml", "project")), ("package.json", package_json),
                         ("Cargo.toml", lambda: toml("Cargo.toml", "package")), ("pom.xml", pom), ("setup.cfg", setup_cfg),
                         ("VERSION", version_file)):
        value = read()
        if isinstance(value, str) and value.strip() and not any(m in value for m in ("${", "attr:", "file:")):
            return {"value": value.strip()[:40], "source": source}
    return None
