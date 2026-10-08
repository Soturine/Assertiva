"""Technologies in the report header: identified by evidence, labeled by how they are known, drawn offline."""

import json
import re

from assertiva.adapters.technologies import project_technologies
from assertiva.report import render_html
from assertiva.report_icons import PATHS
from conftest import write


def detect(root, executed=()):
    files = sorted(p.relative_to(root).as_posix() for p in root.rglob("*") if p.is_file())
    return project_technologies(root, files, list(executed))


def test_primary_language_and_frameworks_carry_their_basis(tmp_path):
    write(tmp_path / "manage.py", "import django\n")
    for name in ("a.py", "b.py", "c.py"):
        write(tmp_path / "app" / name, "x = 1\n")
    write(tmp_path / "static" / "site.js", "let x = 1;\n")
    found = detect(tmp_path, ["django"])
    assert found["language"] == {"id": "python", "name": "Python", "basis": "SOURCE", "evidence": "4/5"}
    assert found["technologies"] == [{"id": "django", "name": "Django", "basis": "EXECUTED", "evidence": "the django adapter ran the tests"}]


def test_a_dependency_is_presence_not_proven_use(tmp_path):
    write(tmp_path / "package.json", json.dumps({"dependencies": {"react": "19.0.0"}, "devDependencies": {"vitest": "5.0.3"}}))
    write(tmp_path / "vitest.config.ts", "export default {}\n")
    write(tmp_path / "src" / "app.tsx", "export {}\n")
    found = detect(tmp_path)
    assert found["language"]["id"] == "typescript"  # the primary language is not repeated as a technology
    assert [(t["id"], t["basis"]) for t in found["technologies"]] == [("vitest", "CONFIGURED"), ("react", "DECLARED")]


def test_configuration_inside_fixtures_or_subprojects_is_not_the_projects_own(tmp_path):
    write(tmp_path / "tool.py", "x = 1\n")
    write(tmp_path / "tests" / "fixtures" / "java" / "pom.xml", "<project/>\n")
    write(tmp_path / "tests" / "fixtures" / "web" / "playwright.config.js", "module.exports = {}\n")
    assert detect(tmp_path)["technologies"] == []


def test_at_most_three_technologies_and_the_rest_is_counted(tmp_path):
    write(tmp_path / "index.ts", "export {}\n")
    write(tmp_path / "package.json", json.dumps({"dependencies": {"react": "1", "vue": "1", "@angular/core": "1", "jest": "1"}}))
    found = detect(tmp_path, ["vitest"])
    assert len(found["technologies"]) == 3 and found["technologies"][0]["basis"] == "EXECUTED" and found["omitted"] == 2


def test_an_unknown_project_shows_nothing_rather_than_a_guess(tmp_path):
    write(tmp_path / "README", "notes\n")
    assert detect(tmp_path) == {"language": None, "technologies": [], "stack": [], "omitted": 0}


def test_icons_are_plain_path_data_only():
    for tid, path in PATHS.items():
        assert re.fullmatch(r"[MmLlHhVvCcSsQqTtAaZz0-9eE.,\- ]+", path), tid


def _report(tmp_path, technologies):
    from assertiva.audit import run_audit

    write(tmp_path / "p" / "tests" / "test_x.py", "def test_x():\n    assert 1 == 1\n")
    report = run_audit(tmp_path / "p")
    report["project"]["technologies"] = technologies
    return report


def test_the_header_renders_known_icons_inline_and_a_generic_one_otherwise(tmp_path):
    report = _report(tmp_path, {"language": {"id": "python", "name": "Python", "basis": "SOURCE", "evidence": "3/3"},
                                "technologies": [{"id": "bazel", "name": "Bazel", "basis": "CONFIGURED", "evidence": "BUILD"}], "omitted": 0})
    page = render_html(report)
    header = page[page.index('<ul class="tech"'):page.index("</ul>", page.index('<ul class="tech"'))]
    assert 'viewBox="0 0 24 24"' in header and PATHS["python"][:40] in header
    assert 'class="tech-ic generic"' in header and "Bazel" in header
    assert "configured in the project (BUILD)" in header and "primary language: 3/3 source files" in header
    assert not re.search(r"(?:src|href)=\"https?:", page)  # the page stays self-contained and offline
    portuguese = render_html(report, lang="pt-BR")
    assert "configurado no projeto (BUILD)" in portuguese and "Tecnologias identificadas no projeto" in portuguese


def test_no_technologies_means_no_header_row(tmp_path):
    page = render_html(_report(tmp_path, {"language": None, "technologies": [], "omitted": 0}))
    assert '<ul class="tech"' not in page


def test_the_stack_comes_from_services_and_settings_and_a_driver_alone_is_only_declared(tmp_path):
    write(tmp_path / "app.py", "x = 1\n")
    write(tmp_path / "docker-compose.yml", "services:\n  db:\n    image: postgres:16-alpine\n  cache:\n    image: redis:7\n  web:\n    build: .\n")
    write(tmp_path / ".github" / "workflows" / "ci.yml",
          "jobs:\n  t:\n    services:\n      mongo:\n        image: docker.io/library/mongo:7\n    steps:\n      - run: pytest\n")
    write(tmp_path / "requirements.txt", "pymysql==1.1\n")
    stack = {t["id"]: (t["basis"], t["evidence"]) for t in detect(tmp_path)["stack"]}
    assert stack["docker"] == ("CONFIGURED", "docker-compose.yml")
    assert stack["postgresql"] == ("CONFIGURED", "docker-compose.yml service db (postgres:16-alpine)")
    found = detect(tmp_path)
    assert len(found["stack"]) == 3 and found["omitted"] == 2  # docker, mongodb, postgresql shown; redis, mysql counted
    assert {t["id"] for t in found["stack"]} == {"docker", "mongodb", "postgresql"}


def test_a_database_driver_without_configuration_is_declared_only(tmp_path):
    write(tmp_path / "app.js", "1\n")
    write(tmp_path / "package.json", json.dumps({"dependencies": {"mongoose": "8"}}))
    assert detect(tmp_path)["stack"] == [{"id": "mongodb", "name": "MongoDB", "basis": "DECLARED", "evidence": "package.json dependency mongoose"}]


def test_the_stack_renders_after_the_frameworks_with_a_separator(tmp_path):
    report = _report(tmp_path, {"language": {"id": "python", "name": "Python", "basis": "SOURCE", "evidence": "3/3"},
                                "technologies": [{"id": "django", "name": "Django", "basis": "EXECUTED", "evidence": "x"}],
                                "stack": [{"id": "postgresql", "name": "PostgreSQL", "basis": "CONFIGURED", "evidence": "compose.yml service db (postgres:16)"}],
                                "omitted": 0})
    page = render_html(report)
    row = page[page.index('<ul class="tech"'):page.index("</ul>", page.index('<ul class="tech"'))]
    assert row.index("Django") < row.index('class="tech-sep"') < row.index("PostgreSQL")
    assert PATHS["postgresql"][:40] in row and 'class="tech-chip stack basis-configured"' in row
