"""Oracle heuristics calibrated against the dogfood's false positives and misses, each with a control that must stay
flagged: AG-04 (expected-error idiom), AG-05 (determinism), AG-06 (decidable loop condition), AX-E03 (vacuous subset),
AX-E04 (mocking the subject), AX-E05 / TCC-A05 (imported helpers, no-raise contracts), TCC-A17 (Compose oracles)."""

from assertiva.adapters.test_facts import collect
from assertiva.pytest_audit import discover_pytest_definitions

from conftest import write


def facts(root, body, extra=None):
    write(root / "shop" / "__init__.py", "")
    write(root / "shop" / "pricing.py", "def discount(x):\n    return x\n\ndef parse(s):\n    return int(s)\n")
    for rel, text in (extra or {}).items():
        write(root / rel, text)
    write(root / "tests" / "test_cases.py", body)
    found, _ = collect(root)
    return {f.test_id.split("::")[-1]: f for f in found}


def definitions(root):
    return {d.name: d for d in discover_pytest_definitions(root)}


def test_ag04_expected_error_idiom_is_not_a_swallowed_exception(tmp_path):
    got = facts(tmp_path, '''from shop.pricing import parse
def test_idiom():
    try:
        parse("x")
        assert False, "must raise"
    except ValueError:
        pass

def test_pytest_fail_idiom():
    import pytest
    try:
        parse("x")
        pytest.fail("must raise")
    except (ValueError, TypeError):
        pass

def test_control_swallows_everything():
    try:
        parse("x")
        assert False
    except Exception:
        pass

def test_control_ignores_the_error():
    try:
        assert parse("x") == 1
    except ValueError:
        pass
''')
    assert "SWALLOWED_EXCEPTION" not in got["test_idiom"].smells
    assert "SWALLOWED_EXCEPTION" not in got["test_pytest_fail_idiom"].smells
    assert "SWALLOWED_EXCEPTION" in got["test_control_swallows_everything"].smells  # catches the AssertionError too
    assert "SWALLOWED_EXCEPTION" in got["test_control_ignores_the_error"].smells


def test_ag05_call_equals_call_is_a_determinism_check_not_a_tautology(tmp_path):
    got = facts(tmp_path, '''from shop.pricing import discount
def test_deterministic():
    assert discount(7) == discount(7)

def test_unittest_style():
    import unittest
    unittest.TestCase().assertEqual(discount(7), discount(7))

def test_control_same_name():
    total = discount(7)
    assert total == total

def test_control_same_attribute():
    class C:
        x = 1
    assert C.x == C.x
''')
    assert "TAUTOLOGY" not in got["test_deterministic"].smells
    assert got["test_deterministic"].oracles == ("DETERMINISM",)  # weak: still a WEAK_ORACLE candidate, not a false green
    assert "TAUTOLOGY" in got["test_control_same_name"].smells
    assert "TAUTOLOGY" in got["test_control_same_attribute"].smells


def test_ag06_a_literal_condition_in_a_literal_loop_that_holds_is_not_conditional(tmp_path):
    got = facts(tmp_path, '''from shop.pricing import discount
def test_strides():
    for i in range(100):
        if i % 17 == 0:
            assert discount(i) == i

def test_control_never_true():
    for i in range(10):
        if i % 17 == 16:
            assert discount(i) == i

def test_control_runtime_flag():
    import os
    if os.environ.get("CHECK"):
        assert discount(1) == 1
''')
    assert "CONDITIONAL_ASSERTION" not in got["test_strides"].smells
    assert "CONDITIONAL_ASSERTION" in got["test_control_never_true"].smells
    assert "CONDITIONAL_ASSERTION" in got["test_control_runtime_flag"].smells


def test_axe03_an_empty_left_operand_of_a_subset_check_is_vacuous(tmp_path):
    got = facts(tmp_path, '''from shop.pricing import discount
ALLOWED = {1, 2}
def test_vacuous_literal():
    assert set() <= {1, 2}

def test_vacuous_against_a_name():
    assert set() <= ALLOWED

def test_vacuous_issubset():
    assert frozenset().issubset(ALLOWED)

def test_control_real_subset():
    assert {discount(1)} <= ALLOWED

def test_control_result_subset():
    seen = {discount(2)}
    assert seen <= ALLOWED
''')
    for name in ("test_vacuous_literal", "test_vacuous_against_a_name", "test_vacuous_issubset"):
        assert "VACUOUS_ASSERTION" in got[name].smells, name
    for name in ("test_control_real_subset", "test_control_result_subset"):
        assert "VACUOUS_ASSERTION" not in got[name].smells, name


def test_axe04_patching_the_function_the_test_calls_and_checks_is_flagged(tmp_path):
    got = facts(tmp_path, '''from unittest.mock import patch
from shop import pricing

def test_mocks_the_subject():
    with patch("shop.pricing.discount", return_value=90):
        assert pricing.discount(100) == 90

@patch.object(pricing, "discount", return_value=90)
def test_mocks_the_subject_by_object(mocked):
    assert pricing.discount(100) == 90

def test_control_mocks_a_dependency():
    with patch("shop.pricing.parse", return_value=5):
        assert pricing.discount(5) == 5

def test_control_checks_the_interaction():
    with patch("shop.pricing.discount") as mocked:
        pricing.parse("1")
        mocked.assert_not_called()
''')
    assert "MOCKED_SUBJECT" in got["test_mocks_the_subject"].smells
    assert "MOCKED_SUBJECT" in got["test_mocks_the_subject_by_object"].smells
    assert "MOCKED_SUBJECT" not in got["test_control_mocks_a_dependency"].smells
    assert "MOCKED_SUBJECT" not in got["test_control_checks_the_interaction"].smells


def test_axe05_an_imported_helper_that_asserts_is_an_oracle(tmp_path):
    facts(tmp_path, '''from shop.pricing import discount
from tests.helpers import check_total, log_total
from tests import helpers

def test_imported_helper():
    check_total(discount(3))

def test_imported_module_helper():
    helpers.check_total(discount(3))

def test_control_helper_without_assert():
    log_total(discount(3))
''', {"tests/__init__.py": "", "tests/helpers.py": "def check_total(x):\n    assert x == 3\n\ndef log_total(x):\n    print(x)\n"})
    found = definitions(tmp_path)
    assert not found["test_imported_helper"].smoke_like
    assert not found["test_imported_module_helper"].smoke_like
    assert found["test_control_helper_without_assert"].smoke_like  # nothing checks the value


def test_tcc_a05_a_no_raise_acceptance_test_paired_with_its_rejection_test_is_a_contract(tmp_path):
    got = facts(tmp_path, '''import pytest
from shop.pricing import parse, discount

def test_accepts_valid_input():
    parse("12")

def test_rejects_invalid_input():
    with pytest.raises(ValueError):
        parse("twelve")

def test_explicit_contract():
    from contextlib import nullcontext as does_not_raise
    with does_not_raise():
        discount(1)

def test_control_just_runs():
    discount(1)
''')
    found = definitions(tmp_path)
    assert found["test_accepts_valid_input"].assertion_kinds == ("NO_RAISE_CONTRACT",)
    assert not found["test_accepts_valid_input"].smoke_like
    assert found["test_explicit_contract"].assertion_kinds == ("NO_RAISE_CONTRACT",)
    assert found["test_control_just_runs"].assertion_kinds == ("NO_ASSERTION",) and found["test_control_just_runs"].smoke_like
    assert got["test_accepts_valid_input"].oracles == ("NO_RAISE",) and got["test_control_just_runs"].oracles == ()


def test_tcc_a17_compose_state_and_count_assertions_are_oracles(tmp_path):
    write(tmp_path / "app" / "src" / "androidTest" / "kotlin" / "AlertScreenTest.kt", '''
class AlertScreenTest {
    @Test
    fun acknowledgeEnabledForCaregiver() {
        composeTestRule.onNodeWithText("Acknowledge").assertIsEnabled()
    }

    @Test
    fun noAlertsShown() {
        composeTestRule.onAllNodesWithText("Fall detected").assertCountEquals(0)
    }

    @Test
    fun viewerCannotAct() {
        composeTestRule.onNodeWithText("Acknowledge").assertDoesNotExist()
    }

    @Test
    fun controlSmoke() {
        composeTestRule.onNodeWithText("Alerts").assertExists()
    }
}
''')
    found, _ = collect(tmp_path)
    got = {f.test_id.split("#")[-1].split("::")[-1]: f for f in found}
    assert got["acknowledgeEnabledForCaregiver"].oracles == ("STATE",)
    assert got["noAlertsShown"].oracles == ("VALUE",)
    assert got["viewerCannotAct"].oracles == ("VALUE",)
    assert got["controlSmoke"].oracles == ("EXISTENCE",)  # the weak smoke stays weak
