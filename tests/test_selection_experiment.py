"""Matched experiment: FULL suite vs Assertiva SELECTED + WIDENING on controlled, known defects.

Each defect is injected into a committed project; the full suite and the selected set run on the
same tree. A miss is a test file the full suite caught failing that the selected set did not run.
Zero misses on these controlled cases is a requirement of the slice, not a universal claim.
"""

import json
import os
import re
import subprocess
import sys
import time
from pathlib import Path

import pytest

from assertiva.adapters.pytest_native import PytestNativeAdapter
from assertiva.selection import select_changes

from conftest import write

IGNORE = "__pycache__/\n.pytest_cache/\n"

SHOP = {
    ".gitignore": IGNORE,
    "pytest.ini": "[pytest]\naddopts = -p no:cacheprovider\n",
    "money.py": "def cents(amount):\n    return round(amount * 100)\n",
    "pricing.py": "from money import cents\n\n\ndef price(total, tier):\n    return cents(total * 0.9) if tier == 'VIP' else cents(total)\n",
    "cart.py": "from pricing import price\n\n\ndef checkout(items, tier):\n    return price(sum(items), tier)\n",
    "tax.py": "import json\nimport warnings\nfrom pathlib import Path\n\n\ndef rate():\n"
              "    warnings.warn('rates file format will change', DeprecationWarning)\n"
              "    return json.loads((Path(__file__).parent / 'data' / 'rates.json').read_text())['standard']\n",
    "data/rates.json": '{"standard": 0.1}\n',
    "loader.py": "import importlib\n\n\ndef fee(name):\n    return importlib.import_module('plugins.' + name).FEE\n",
    "plugins/__init__.py": "",
    "plugins/express.py": "FEE = 5\n",
    "shop_fixtures.py": "import pytest\n\n\n@pytest.fixture\ndef catalog():\n    return {'pen': 2}\n",
    "tests/conftest.py": "import pytest\n\npytest_plugins = ['shop_fixtures']\n\n\n@pytest.fixture\ndef tier():\n    return 'VIP'\n",
    "tests/helpers.py": "def basket():\n    return [60, 40]\n",
    "tests/base.py": "class NonNegativeContract:\n    def test_never_negative(self):\n        assert self.compute() >= 0\n",
    "tests/test_money.py": "from money import cents\n\n\ndef test_cents():\n    assert cents(1.25) == 125\n",
    "tests/test_pricing.py": "from pricing import price\n\n\ndef test_vip_price():\n    assert price(100, 'VIP') == 9000\n",
    "tests/test_cart.py": "from cart import checkout\nfrom helpers import basket\n\n\ndef test_checkout(tier):\n    assert checkout(basket(), tier) == 9000\n",
    "tests/test_tax.py": "import pytest\nfrom tax import rate\n\n\ndef test_rate():\n    assert rate() == pytest.approx(0.1)\n",
    "tests/test_fees.py": "from loader import fee\n\n\ndef test_express_fee():\n    assert fee('express') == 5\n",
    "tests/test_catalog.py": "def test_pen_price(catalog):\n    assert catalog['pen'] == 2\n",
    "tests/test_contract.py": "from base import NonNegativeContract\nfrom money import cents\n\n\nclass TestCents(NonNegativeContract):\n"
                              "    def compute(self):\n        return cents(0.01)\n",
}

DEFECTS = {
    "direct dependency": {"tax.py": SHOP["tax.py"].replace("['standard']", "['standard'] * 2")},
    "transitive dependency": {"money.py": "def cents(amount):\n    return round(amount * 10)\n"},
    "shared fixture": {"tests/conftest.py": SHOP["tests/conftest.py"].replace("return 'VIP'", "return 'REGULAR'")},
    "declared fixture plugin": {"shop_fixtures.py": SHOP["shop_fixtures.py"].replace("'pen': 2", "'pen': 3")},
    "test helper": {"tests/helpers.py": "def basket():\n    return [60, 30]\n"},
    "base test class": {"tests/base.py": SHOP["tests/base.py"].replace(">= 0", "> 1")},
    "framework configuration": {"pytest.ini": "[pytest]\naddopts = -p no:cacheprovider\nfilterwarnings = error\n"},
    "dynamic import": {"plugins/express.py": "FEE = 7\n"},
    "data file": {"data/rates.json": '{"standard": 0.2}\n'},
    "renamed module": {"money.py": None, "currency.py": SHOP["money.py"]},
}

MONO = {
    ".gitignore": IGNORE,
    "packages/a/pyproject.toml": '[project]\nname = "acme-a"\nversion = "1"\n',
    "packages/a/src/acme_a/__init__.py": "",
    "packages/a/src/acme_a/core.py": "def base():\n    return 10\n",
    "packages/a/src/acme_a/registry.py": "import importlib\n\n\ndef load(name):\n    return importlib.import_module('acme_a.' + name)\n",
    "packages/a/src/acme_a/limits.py": "MAX = 3\n",
    "packages/a/tests/test_core.py": "from acme_a.core import base\n\n\ndef test_base():\n    assert base() == 10\n",
    "packages/b/pyproject.toml": '[project]\nname = "acme-b"\nversion = "1"\ndependencies = ["acme-a"]\n',
    "packages/b/src/acme_b/__init__.py": "",
    "packages/b/src/acme_b/api.py": "from acme_a.core import base\nfrom acme_a.registry import load\n\n\ndef total():\n"
                                     "    return base() + load('limits').MAX\n",
    "packages/b/tests/test_api.py": "from acme_b.api import total\n\n\ndef test_total():\n    assert total() == 13\n",
    "packages/c/pyproject.toml": '[project]\nname = "acme-c"\nversion = "1"\n',
    "packages/c/src/acme_c/__init__.py": "",
    "packages/c/src/acme_c/tool.py": "def tool():\n    return 0\n",
    "packages/c/tests/test_tool.py": "from acme_c.tool import tool\n\n\ndef test_tool():\n    assert tool() == 0\n",
    "conftest.py": "import sys\nfrom pathlib import Path\n\nfor src in Path(__file__).parent.glob('packages/*/src'):\n"
                   "    sys.path.insert(0, str(src))\n",
}

MONO_DEFECTS = {
    "cross-package dependency": {"packages/a/src/acme_a/core.py": "def base():\n    return 11\n"},
    "module loaded only dynamically by a dependent": {"packages/a/src/acme_a/limits.py": "MAX = 4\n"},
}

_RESULT = re.compile(r"^(FAILED|ERROR) ([^\s:]+\.py)")


def _git(root, *args):
    git = ["git", "-c", "user.name=fixture", "-c", "user.email=fixture@example.invalid", "-c", "commit.gpgsign=false"]
    subprocess.run([*git, *args], cwd=root, check=True, capture_output=True)


def _pytest(root, paths=()):
    started = time.perf_counter()
    # No bytecode: a restored file with the same size and mtime second would otherwise reuse a stale .pyc.
    env = {**os.environ, "PYTHONDONTWRITEBYTECODE": "1"}
    result = subprocess.run([sys.executable, "-m", "pytest", "-q", "--tb=no", "-rfE", "-p", "no:cacheprovider", *paths],
                            cwd=root, capture_output=True, text=True, env=env)
    failing = {m.group(2).replace("\\", "/") for line in result.stdout.splitlines() if (m := _RESULT.match(line))}
    if result.returncode not in (0, 1, 5) and not failing:
        failing = {"<run error>"}
    return failing, time.perf_counter() - started


def run_experiment(tmp_path: Path, files: dict, defects: dict) -> list[dict]:
    root = tmp_path / "project"
    for rel, text in files.items():
        write(root / rel, text)
    _git(root, "init", "-q")
    _git(root, "add", "-A")
    _git(root, "commit", "-q", "-m", "base")
    clean, _ = _pytest(root)
    assert not clean, f"the base project must be green: {clean}"
    rows = []
    for name, edits in defects.items():
        for rel, text in edits.items():
            if text is None:
                (root / rel).unlink()
            else:
                write(root / rel, text)
        selection = select_changes(root, "HEAD")
        full_failing, full_s = _pytest(root)
        if selection.full:
            ran, selected_failing, selected_s = "full suite", full_failing, full_s
        else:
            ran = sorted(selection.selected)
            # the selected run is built exactly as Assertiva builds it for the runner
            selected_failing, selected_s = _pytest(root, PytestNativeAdapter().selection_args(ran))
        tests = len(selection.selected) + len(selection.not_selected)
        rows.append({
            "defect": name, "changes": sorted(edits),
            "full_detected": sorted(full_failing), "selected": ran,
            "selection_ratio": 1.0 if selection.full else round(len(selection.selected) / max(tests, 1), 2),
            "widening": [w.trigger.value + (" (full)" if w.full else "") for w in selection.widening],
            "confidence": selection.confidence.value,
            "miss": sorted(full_failing - selected_failing),
            "full_s": round(full_s, 2), "selected_s": round(selected_s, 2),
        })
        _git(root, "checkout", "-q", "--", ".")
        _git(root, "clean", "-q", "-fd")
    return rows


@pytest.mark.integration
@pytest.mark.parametrize(("files", "defects"), [(SHOP, DEFECTS), (MONO, MONO_DEFECTS)], ids=["single-project", "monorepo"])
def test_selected_plus_widening_misses_no_controlled_defect(tmp_path, files, defects):
    rows = run_experiment(tmp_path, files, defects)
    print(json.dumps(rows, indent=1))
    assert all(row["full_detected"] for row in rows), [r["defect"] for r in rows if not r["full_detected"]]  # every defect is real
    assert [row["defect"] for row in rows if row["miss"]] == []
    assert any(row["selection_ratio"] < 1.0 for row in rows)  # selection actually narrows somewhere
