# Answer

**No. The pricing rules are not covered in CI.**

You have evidence of two different test suites running:
- **Local (pytest):** 152 tests pass — 140 unittest TestCase methods + 12 test functions
- **CI (unittest):** 140 tests pass — unittest TestCase methods only

The 12 test functions added last month are never invoked by CI's runner. Pytest finds plain `def test_...():` functions that unittest's discovery cannot. Both are green, but green does not mean the same thing at each end.

## What the evidence shows

**OBSERVED:** Engine audit with `--execute` ran unittest (CI's declared runner) and reported 140 PASS; the finding `CI_RUNS_PYTHON_UNITTEST` lists the 12 functions from `tests/test_rules.py` as never run by unittest.

**DECLARED:** The workflow runs `python -m unittest discover -s tests`. Unittest discovery finds TestCase subclasses, not plain test functions.

**INFERRED:** The 12 functions exist and are formatted as pytest test functions (`def test_...():`), but unittest cannot collect them. Pytest locally finds and runs all 152 because it has a separate discovery mechanism.

## What green proves and does not

- **Local green:** All 152 test invocations passed, including the 12 pricing-rule functions. The pricing rules have been exercised locally.
- **CI green:** All 140 unittest invocations passed. The pricing rules have *never been invoked* in the CI environment.

This is not a case of the same test suite running in two places. The test population differs by 12 tests. A defect in the pricing logic would be caught locally but would let CI stay green.

## Why this matters

You cannot conclude that CI proves the pricing rules because CI's test runner does not discover them. This is a revision-provenance gap (DELIVERY reference: "whether the provider is reachable... A CI run proves a revision only when its identity is confirmed"). A green CI run proves a *subset* of the behavior you test locally.

## What to do

**Option 1 (recommended):** Convert the 12 test functions to unittest-compatible form (TestCase subclasses or methods) so unittest.discover finds them. Verify with a local unittest run that all 152 now report as found.

**Option 2:** Change the CI workflow to run `pytest` instead of unittest, or run both. Confirm pytest reports all 152 passing in CI before merging.

**Option 3:** If the functions truly belong outside the CI test suite, mark them explicitly (place them outside `tests/`, rename them to not match the `test_*` pattern, add skip markers). Document why; unknown divergence is a maintenance hazard.

Until one of these resolves the discovery gap, you have local coverage of the pricing rules but zero CI evidence that they work.
