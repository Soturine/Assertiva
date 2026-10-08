"""Native Django evidence: `manage.py test` as the project runs it, read test by test through its own TEST_RUNNER.

The fixture (tests/fixtures/django-site) has models, a migration, views behind login, the test client, the async
client, SimpleTestCase / TestCase / TransactionTestCase / LiveServerTestCase and a transactional rollback. Needs an
interpreter with Django: the current one, or ASSERTIVA_DJANGO_PYTHON. CI sets ASSERTIVA_REQUIRE_DJANGO=1 so a
missing Django fails instead of skipping."""

import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

from assertiva import cli
from assertiva.adapters import runner_adapters
from assertiva.adapters.unittest_native import DjangoAdapter
from assertiva.candidate import StageStatus
from assertiva.models import Outcome
from assertiva.workspace import tree_fingerprint
from conftest import write

pytestmark = pytest.mark.integration

FIXTURE = Path(__file__).parent / "fixtures" / "django-site"


def _django_python() -> str | None:
    for candidate in (os.environ.get("ASSERTIVA_DJANGO_PYTHON"), sys.executable):
        if candidate and subprocess.run([candidate, "-c", "import django"], capture_output=True).returncode == 0:
            return candidate
    return None


PYTHON = _django_python()
if PYTHON is None:
    if os.environ.get("ASSERTIVA_REQUIRE_DJANGO"):
        raise RuntimeError("ASSERTIVA_REQUIRE_DJANGO is set but no interpreter with Django was found")
    pytest.skip("no interpreter with Django (set ASSERTIVA_DJANGO_PYTHON)", allow_module_level=True)


def site(tmp_path: Path) -> Path:
    root = tmp_path / "site"
    shutil.copytree(FIXTURE, root)
    return root


def test_a_django_project_runs_through_manage_py_test_with_per_test_outcomes(tmp_path):
    root = site(tmp_path)
    assert [a.adapter_id for a in runner_adapters(root, PYTHON)] == ["django"]
    run = DjangoAdapter(python=PYTHON).run(root, coverage=True)
    assert run.status is StageStatus.PASS and run.exit_code == 0
    assert run.metadata["session"]["test_runner"] == "django.test.runner.DiscoverRunner"
    names = {inv.invocation_id.rsplit("::", 1)[1]: inv.outcome for inv in run.invocations}
    assert len(names) == 9 and set(names.values()) == {Outcome.PASSED}
    assert {"test_the_live_server_answers", "test_health_answers_asynchronously", "test_a_duplicate_code_rolls_back_the_whole_pair"} <= set(names)
    assert run.coverage is not None and run.coverage.counts["line"]["covered"] > 0
    assert not (root / "db.sqlite3").exists()  # the runner created its own test database


def test_failures_skips_subtests_and_load_errors_are_distinct(tmp_path):
    root = site(tmp_path)
    write(root / "orders" / "tests" / "test_extra.py",
          "from django.test import SimpleTestCase\nimport unittest\n\n\nclass Extra(SimpleTestCase):\n"
          "    def test_wrong(self):\n        self.assertEqual(1, 2)\n"
          "    @unittest.skip('later')\n    def test_later(self):\n        pass\n"
          "    def test_cases(self):\n        for n in (1, 2):\n            with self.subTest(n=n):\n                self.assertEqual(n, 1)\n")
    write(root / "orders" / "tests" / "test_broken.py", "import not_installed_module_xyz\n")
    run = DjangoAdapter(python=PYTHON).run(root)
    by_name = {inv.invocation_id.split("::", 1)[1]: inv.outcome for inv in run.invocations}
    assert by_name["Extra::test_wrong"] is Outcome.FAILED and by_name["Extra::test_later"] is Outcome.SKIPPED
    assert by_name["Extra::test_cases[(n=1)]"] is Outcome.PASSED and by_name["Extra::test_cases[(n=2)]"] is Outcome.FAILED
    assert run.collection_errors == ["orders.tests.test_broken"] and run.status is StageStatus.FAIL


def test_an_unavailable_database_blocks_the_run_instead_of_passing_it(tmp_path):
    root = site(tmp_path)
    settings = root / "site_config" / "settings.py"
    settings.write_text(settings.read_text(encoding="utf-8").replace(
        '{"default": {"ENGINE": "django.db.backends.sqlite3", "NAME": BASE_DIR / "db.sqlite3"}}',
        '{"default": {"ENGINE": "django.db.backends.postgresql", "NAME": "x", "HOST": "127.0.0.1", "PORT": "1"}}'), encoding="utf-8")
    run = DjangoAdapter(python=PYTHON).run(root)
    assert run.status is StageStatus.BLOCKED and not run.invocations  # never a pass, never a test failure
    assert any("psycopg" in lim or "could not connect" in lim for lim in run.limitations)  # Django's own reason


def test_the_projects_own_test_runner_is_kept(tmp_path):
    root = site(tmp_path)
    write(root / "site_config" / "runner.py", "from django.test.runner import DiscoverRunner\n\n\nclass FastRunner(DiscoverRunner):\n"
                                              "    def __init__(self, *args, **kwargs):\n        kwargs['exclude_tags'] = kwargs.get('exclude_tags') or ['slow']\n"
                                              "        super().__init__(*args, **kwargs)\n")
    with open(root / "site_config" / "settings.py", "a", encoding="utf-8") as handle:
        handle.write('TEST_RUNNER = "site_config.runner.FastRunner"\n')
    write(root / "orders" / "tests" / "test_slow.py", "from django.test import SimpleTestCase, tag\n\n\n@tag('slow')\n"
                                                     "class Slow(SimpleTestCase):\n    def test_slow(self):\n        self.assertTrue(False)\n")
    run = DjangoAdapter(python=PYTHON).run(root)
    assert run.metadata["session"]["test_runner"] == "site_config.runner.FastRunner"
    assert run.status is StageStatus.PASS and len(run.invocations) == 9  # the runner's exclusion still applies


def test_audit_reproduces_the_ci_django_check_and_leaves_the_project_unchanged(tmp_path, capsys):
    root = site(tmp_path)
    write(root / ".github" / "workflows" / "ci.yml",
          "on: push\njobs:\n  test:\n    runs-on: ubuntu-latest\n    steps:\n      - run: python manage.py test orders.tests.test_models\n")
    before = tree_fingerprint(root)
    code = cli.main(["audit", str(root), "--python", PYTHON, "--run-check", "gha:.github/workflows/ci.yml:test:1", "--output", "json"])
    report = json.loads(capsys.readouterr().out)
    assert code == 0 and tree_fingerprint(root) == before
    [check] = report["declared_checks"]
    assert check["status"] == "PASS" and check["execution"]["via"] == "django"
    [run] = report["states"]["current"]["runs"]
    assert run["adapter"] == "django" and run["outcomes"] == {"PASSED": 3}  # only what CI selects
