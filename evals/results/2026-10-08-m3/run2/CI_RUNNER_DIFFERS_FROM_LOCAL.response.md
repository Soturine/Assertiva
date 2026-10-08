# Answer: Local and CI Parity Gap – Pricing Rules Untested in CI

## Direct Answer

**No.** The pricing rules are **not** covered in CI. Local pytest is green; CI unittest is green. They are not testing the same suite.

## What Green Proves and Does Not

- **CI proves:** The 140 `unittest.TestCase` methods pass. That is all.
- **CI does not prove:** The 12 plain `def test_...():` functions in `test_rules.py`, which assert pricing rules.
- **Local proves:** 152 tests pass — the 140 TestCase methods plus the 12 plain functions.
- **The gap:** Unittest's discovery mechanism (`python -m unittest discover`) does not find plain test functions. Only the TestCase subclasses are discovered in CI.

## Finding: Pricing Rules Never Run in CI

**Priority:** High

**Basis:** OBSERVED (engine audit `--execute` ran the project's declared runner, unittest, confirmed 140 passing and raised `CI_RUNS_PYTHON_UNITTEST` listing the 12 plain test functions as never invoked)

**Evidence:**
- CI declared: `python -m unittest discover -s tests` (DECLARED)
- Engine finding: `CI_RUNS_PYTHON_UNITTEST` lists the 12 plain test functions as never run (OBSERVED)
- Local vs CI test counts: pytest 152 passing, unittest 140 passing (OBSERVED)
- Unittest discovery excludes plain test functions by design (INFERRED from test runner semantics)

**Why it matters:** 
1. A defect in pricing rules would not be caught by CI.
2. Green CI is the gating signal. Local green is an optional safety check. When CI does not run a test, that test offers no assurance to the release process.
3. This is a classic CI/local parity gap: the two environments run different verification sets, yet both report green. The developer sees local green and assumes full coverage; CI is green and looks gated; neither is true for pricing rules.

## What Remains Unknown

Whether the 12 test functions have strong oracles (whether they would reliably detect a real pricing defect). This audit ran the declared runner only, not pytest, so per-test outcomes and mutation evidence for those functions are not available.

## Recommendation

Choose one:

1. **Convert plain test functions to unittest methods** and keep `python -m unittest discover` as the CI runner. Rename `def test_...():` to methods in a TestCase subclass.

2. **Add pytest to CI** as a separate step after or instead of unittest, running the full 152 tests. Ensure CI passes only when both pass (or only pytest if that becomes the authoritative runner).

3. **Change CI to pytest only**, deleting unittest from the CI step. Verify that pytest is installed and configured to match the local environment (no `pytest.ini` or `pyproject.toml` overrides that would change discovery in CI).

Without one of these, CI does not prove the pricing rules, and a regression there will ship.
