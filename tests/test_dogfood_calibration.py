"""Derivanta Engine dogfood calibration (0.10.1 candidate): each rule is tested on the reported case, on variants, and
on controls that look alike but must keep their earlier classification.

AXF-M2-01 always-true `or`; AXF-03 assigned determinism; AXF-06 typed error boundary; AXF-07 redundancy over
different modules; AXF-M3-02 what an error test asserts; DG-0101-04 rejection at construction."""


from assertiva.adapters.test_facts import collect
from assertiva.effectiveness import candidates
from assertiva.pytest_audit import audit_pytest_project, discover_pytest_definitions

from conftest import write


def facts_of(root, source, name="tests/test_x.py"):
    write(root / name, source)
    return {f.test_id.split("::")[-1]: f for f in collect(root)[0]}


# --- AXF-M2-01 ---------------------------------------------------------------------------------------------------

ALWAYS = {
    "test_or_true": "assert add(1, 2) == 4 or True",  # the reported case
    "test_true_or": "assert True or add(1, 2) == 4",
    "test_nested": "assert add(1, 2) == 4 or (add(2, 2) == 5 or 1)",
    "test_message_by_mistake": "assert add(1, 2) == 4 or 'add must sum'",
    "test_fstring_message": "assert add(1, 2) == 4 or f'got {add(1, 2)}'",
    "test_not_false": "assert not False",
}
CONTROLS = {
    "test_value": "assert add(1, 2) == 3",
    "test_runtime_or": "assert add(1, 2) == 3 or add(2, 1) == 3",
    "test_and_true": "assert add(1, 2) == 3 and True",
    "test_not_value": "assert not add(0, 0)",
    "test_empty_fstring_part": "assert f'{add(1, 2)}'",  # no literal text: truthiness depends on the value
}


def test_always_true_assertions_are_tautologies_and_lookalikes_are_not(tmp_path):
    body = "".join(f"def {name}():\n    {line}\n\n\n" for name, line in {**ALWAYS, **CONTROLS}.items())
    facts = facts_of(tmp_path, "from lib import add\n\n\n" + body)
    for name in ALWAYS:
        assert "TAUTOLOGY" in facts[name].smells, name
    for name in CONTROLS:
        assert "TAUTOLOGY" not in facts[name].smells, name


def test_assert_true_with_an_always_true_argument_is_a_tautology(tmp_path):
    facts = facts_of(tmp_path, "import unittest\nfrom lib import add\n\n\nclass T(unittest.TestCase):\n"
                               "    def test_or(self):\n        self.assertTrue(add(1, 2) == 4 or True)\n\n"
                               "    def test_ok(self):\n        self.assertTrue(add(1, 2) == 3)\n")
    assert "TAUTOLOGY" in facts["test_or"].smells and "TAUTOLOGY" not in facts["test_ok"].smells


# --- AXF-03 ------------------------------------------------------------------------------------------------------

def test_direct_and_assigned_repetition_are_the_same_weak_determinism_oracle(tmp_path):
    facts = facts_of(tmp_path, "from lib import f\n\n\n"
                               "def test_direct():\n    assert f(3) == f(3)\n\n\n"
                               "def test_assigned():\n    a = f(3)\n    assert a == f(3)\n\n\n"
                               "def test_value():\n    assert f(3) == 6\n\n\n"
                               "def test_other_input():\n    a = f(4)\n    assert a == f(3)\n\n\n"
                               "def test_action_between():\n    a = f(3)\n    reset()\n    assert a == f(3)\n")
    for name in ("test_direct", "test_assigned"):
        assert facts[name].oracles == ("DETERMINISM",) and "SELF_REFERENTIAL_ORACLE" not in facts[name].smells, name
    for name in ("test_value", "test_other_input", "test_action_between"):
        assert facts[name].oracles == ("VALUE",), name
    kinds = {c.kind for c in candidates(list(facts.values())) if set(c.tests) & {"tests/test_x.py::test_assigned"}}
    assert kinds == {"WEAK_ORACLE"}  # surfaced as weak, never as a false green


# --- AXF-06 ------------------------------------------------------------------------------------------------------

TYPED = """from lib import decode, DecodeError


def test_typed_boundary():
    for data in (b"", b"x"):
        try:
            decode(data)
        except (DecodeError, TypeError):
            pass


def test_swallows_everything():
    try:
        decode(b"")
    except Exception:
        pass


def test_swallows_assertions():
    try:
        decode(b"")
    except AssertionError:
        pass


def test_typed_but_assertion_inside():
    try:
        assert decode(b"x") == "x"
    except DecodeError:
        pass
"""


def test_a_typed_error_boundary_is_a_limited_oracle_and_broad_handlers_still_swallow(tmp_path):
    facts = facts_of(tmp_path, TYPED)
    assert facts["test_typed_boundary"].oracles == ("TYPED_ERROR",) and "SWALLOWED_EXCEPTION" not in facts["test_typed_boundary"].smells
    for name in ("test_swallows_everything", "test_swallows_assertions", "test_typed_but_assertion_inside"):
        assert "SWALLOWED_EXCEPTION" in facts[name].smells, name  # the assertion inside is skipped when the error happens
    definitions = {d.name: d for d in discover_pytest_definitions(tmp_path)}
    assert definitions["test_typed_boundary"].assertion_kinds == ("TYPED_ERROR_BOUNDARY",)  # 0.10.0: NO_ASSERTION
    assert definitions["test_swallows_everything"].assertion_kinds == ("NO_ASSERTION",)
    assert definitions["test_typed_boundary"].smoke_like  # weak: it says nothing about the returned values


def test_a_property_test_with_a_typed_boundary_is_read_the_same_way(tmp_path):
    facts = facts_of(tmp_path, "from hypothesis import given, strategies as st\nfrom lib import decode, DecodeError\n\n\n"
                               "@given(st.binary())\ndef test_never_escapes(data):\n    try:\n        decode(data)\n"
                               "    except (DecodeError, UnicodeError):\n        pass\n")
    assert facts["test_never_escapes"].oracles == ("TYPED_ERROR",)


# --- AXF-07 ------------------------------------------------------------------------------------------------------

UT = "import unittest\nfrom {imp}\n\n\nclass T(unittest.TestCase):\n    def test_add(self):\n        self.assertEqual({call}(1, 2), 3)\n"
LIB = "def add(a, b):\n    return a + b\n"


def redundancy(root):
    return [c for c in candidates(collect(root)[0]) if c.kind == "REDUNDANCY"]


def test_equal_bodies_over_different_modules_are_not_redundant(tmp_path):
    for side in ("a", "b"):  # the M1 C1 fixture: each suite tests its own lib.py
        write(tmp_path / side / "lib.py", LIB)
        write(tmp_path / side / "tests" / f"test_{side}.py", UT.format(imp="lib import add", call="add"))
    assert redundancy(tmp_path) == []  # 0.10.0: REDUNDANCY_CANDIDATE


def test_equal_bodies_over_the_same_module_stay_a_candidate_with_the_module_named(tmp_path):
    write(tmp_path / "lib.py", LIB)
    write(tmp_path / "tests" / "test_a.py", UT.format(imp="lib import add", call="add"))
    write(tmp_path / "tests" / "test_b.py", UT.format(imp="lib import add as plus", call="plus").replace("plus(1", "plus(1"))
    write(tmp_path / "tests" / "test_c.py", UT.format(imp="lib import add", call="add"))
    [found] = redundancy(tmp_path)
    assert set(found.tests) == {"tests/test_a.py::T::test_add", "tests/test_c.py::T::test_add"}  # the alias body differs
    assert found.detail["subjects"] == ["lib.py"] and found.detail["subject_identity"] == "SAME_MODULES"


def test_an_unresolved_subject_keeps_the_candidate_and_says_its_identity_is_unknown(tmp_path):
    for side in ("a", "b"):
        write(tmp_path / "tests" / f"test_{side}.py", UT.format(imp="installed_pkg import add", call="add"))
    [found] = redundancy(tmp_path)
    assert found.detail["subject_identity"] == "UNKNOWN" and found.detail["subjects"] == []


def test_a_relative_import_resolves_inside_its_package(tmp_path):
    for side in ("a", "b"):
        write(tmp_path / "pkg" / side / "__init__.py", "")
        write(tmp_path / "pkg" / side / "lib.py", LIB)
        write(tmp_path / "pkg" / side / "test_lib.py", UT.format(imp=".lib import add", call="add").replace("from .lib", "from .lib"))
    assert redundancy(tmp_path) == []


# --- AXF-M3-02 ---------------------------------------------------------------------------------------------------

ERRORS = """import pytest
from lib import AppError, run


def test_code_pinned():
    with pytest.raises(AppError) as raised:
        run(1)
    assert raised.value.code == "E_BAD"


def test_exit_code_only():
    with pytest.raises(AppError) as raised:
        run(2)
    assert raised.value.exit_code == 2


def test_type_only():
    with pytest.raises(AppError):
        run(3)
"""


def test_the_error_contract_finding_names_what_each_test_asserts(tmp_path):
    write(tmp_path / "tests" / "test_err.py", ERRORS)
    [found] = [f for f in audit_pytest_project(tmp_path).findings if f.code == "ERROR_CONTRACT_FIELD_NOT_OBSERVED"]
    assert "only check the type" not in found.summary  # 0.10.0 said so of a test asserting exit_code
    assert found.evidence["tests"] == ["tests/test_err.py::test_exit_code_only", "tests/test_err.py::test_type_only"]
    assert found.evidence["asserted"] == {"tests/test_err.py::test_exit_code_only": ["exit_code"]}
    assert found.evidence["detail_asserted_elsewhere"] == ["MACHINE_CODE"] and found.evidence["count"] == 2


# --- DG-0101-04 (Derivanta M3 OBS-M3-03) ---------------------------------------------------------------------------

REJECTIONS = """import pytest
from model import Invalid, Ledger, Price


def test_ledger_rejects_and_stays_empty():
    ledger = Ledger()
    with pytest.raises(Invalid):
        ledger.add(-1)
    assert ledger.entries == []


def test_ledger_rejection_without_state_check():
    ledger = Ledger()
    with pytest.raises(Invalid):
        ledger.add(-1)


def test_price_rejects_negative_at_construction():
    with pytest.raises(Invalid):
        Price(-1)


def test_rejected_construction_after_building_something():
    ledger = Ledger()
    with pytest.raises(Invalid):
        Price(-1)
"""


def test_a_rejection_at_construction_has_no_state_to_check(tmp_path):
    write(tmp_path / "tests" / "test_model.py", REJECTIONS)
    [found] = [f for f in audit_pytest_project(tmp_path).findings if f.code == "STATE_AFTER_REJECTION_NOT_EVIDENCED"]
    assert found.evidence["tests"] == ["tests/test_model.py::test_ledger_rejection_without_state_check",
                                       "tests/test_model.py::test_rejected_construction_after_building_something"]
