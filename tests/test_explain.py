"""Test Effectiveness Explorer: one test's chain of evidence, read back from the last audit.

The demo project has a strong test, a false green, a test that mocks its own subject, a negative-path test and a test
no runner collects; each explanation must say what the evidence shows and nothing more."""

import json
import os
import subprocess
import sys

import pytest

from assertiva import cli
from assertiva.workspace import tree_fingerprint

from conftest import write

pytestmark = pytest.mark.integration

TESTS = '''import pytest
from unittest.mock import patch
import shop

def test_discount_value():
    assert shop.discount(100, "VIP") == 90

def test_discount_swallowed():
    try:
        assert shop.discount(100, "VIP") == 1
    except AssertionError:
        pass

def test_discount_mocked():
    with patch("shop.discount", return_value=90):
        assert shop.discount(100, "VIP") == 90

def test_rejects_negative():
    with pytest.raises(ValueError, match="negative"):
        shop.discount(-1, "VIP")
'''


def demo(root):
    write(root / "shop.py", "def discount(amount, tier):\n    if amount < 0:\n        raise ValueError('negative amount')\n"
                            "    return amount * 9 // 10 if tier == 'VIP' else amount\n")
    write(root / "tests" / "test_shop.py", TESTS)
    write(root / "pytest.ini", "[pytest]\ntestpaths = tests\n")
    write(root / "extra" / "test_never_collected.py", "import shop\n\ndef test_orphan():\n    assert shop.discount(1, 'X') == 1\n")
    return root


def call(capsys, *args):
    code = cli.main([*args, "--output", "json"])
    out, err = capsys.readouterr()
    assert code == 0, err
    return json.loads(out)


def test_each_kind_of_test_is_explained_from_its_evidence(tmp_path, capsys, assertiva_home):
    root = demo(tmp_path / "shop")
    call(capsys, "audit", str(root), "--execute", "--python", sys.executable)
    before = tree_fingerprint(root)
    strong = call(capsys, "explain", str(root), "--test", "test_discount_value")
    assert strong["oracle"]["kinds"] == ["VALUE"] and strong["oracle"]["smells"] == []
    assert strong["executed"][0]["outcomes"] == {"tests/test_shop.py::test_discount_value": "PASSED"}
    assert strong["executed"][0]["provenance"] == "ENGINE_EXECUTED" and strong["executed"][0]["code_identity"] == "SOURCE_TREE"
    assert any("no mutation evidence" in u for u in strong["unknowns"])

    swallowed = call(capsys, "explain", str(root), "--test", "test_discount_swallowed")
    assert "SWALLOWED_EXCEPTION" in swallowed["oracle"]["smells"]
    assert any(c["kind"] == "FALSE_GREEN" for c in swallowed["candidates"])
    assert swallowed["executed"][0]["outcomes"]["tests/test_shop.py::test_discount_swallowed"] == "PASSED"  # green, and wrong

    mocked = call(capsys, "explain", str(root), "--test", "test_discount_mocked")
    assert "MOCKED_SUBJECT" in mocked["oracle"]["smells"]

    negative = call(capsys, "explain", str(root), "--test", "test_rejects_negative")
    assert negative["oracle"]["kinds"] == ["SPECIFIC_ERROR"] and "EXCEPTION" in negative["oracle"]["surfaces"]

    orphan = call(capsys, "explain", str(root), "--test", "test_orphan")
    assert orphan["scope"] == "OUTSIDE_RUNNER_SCOPE" and orphan["executed"] == []
    assert any("no run in the audit executed this test" in u for u in orphan["unknowns"])
    assert tree_fingerprint(root) == before  # explaining reads only


def test_explain_without_an_audit_or_with_an_ambiguous_name_is_refused(tmp_path, capsys, assertiva_home):
    root = demo(tmp_path / "shop")
    assert cli.main(["explain", str(root), "--test", "test_discount_value"]) == 2
    call(capsys, "audit", str(root))
    assert cli.main(["explain", str(root), "--test", "test_discount"]) == 2
    assert "several tests" in capsys.readouterr().err


def test_mutants_detected_by_the_strong_test_are_shown(tmp_path, capsys, assertiva_home):
    python = os.environ.get("ASSERTIVA_MUTATION_PYTHON") or sys.executable
    if subprocess.run([python, "-c", "import cosmic_ray"], capture_output=True).returncode != 0:
        if os.environ.get("ASSERTIVA_REQUIRE_MUTATION"):
            pytest.fail("needs an interpreter with cosmic-ray")
        pytest.skip("needs an interpreter with cosmic-ray")
    root = demo(tmp_path / "shop")
    call(capsys, "audit", str(root), "--execute", "--python", python, "--mutate", "shop.py")
    chain = call(capsys, "explain", str(root), "--test", "test_discount_value")
    [mutation] = chain["mutation"]
    assert mutation["provenance"] == "ENGINE_EXECUTED" and mutation["tool"] == "Cosmic Ray"
