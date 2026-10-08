# Answer: Local and CI Are Not Running the Same Tests

No. CI being green does **not** mean the pricing rules are covered in CI. The 12 pricing-rule tests never run there.

## What CI green proves and does not

**OBSERVED:** 
- CI runs `python -m unittest discover -s tests` and 140 unittest.TestCase invocations pass.
- Locally, pytest reports 152 passed tests.
- The engine audit via `--execute` confirmed: unittest discovers and runs 140 invocations; the 12 plain-function tests in `tests/test_rules.py` are never discovered by unittest.

**What this means:**
- CI green proves the 140 unittest.TestCase tests pass in the CI environment (OBSERVED via the engine execution of the declared runner).
- CI green **does not** prove the 12 pricing-rule tests because they do not run in CI (OBSERVED: finding `CI_RUNS_PYTHON_UNITTEST` lists them as never run by unittest).
- Locally, pytest green means 152 tests pass in the local environment (OBSERVED: pytest report).
- The local green includes the 12 pricing-rule tests. The CI green does not.

## The gap

The 12 pricing-rule test functions are plain Python functions (`def test_...():`), not `unittest.TestCase` methods. The unittest discovery mechanism in CI (`unittest discover -s tests`) does not find plain-function tests—only TestCase methods. Pytest finds both. 

This is a **verification surface gap**: the 12 pricing-rule tests are part of the source tree (`tests/test_rules.py`), exist locally, and pass locally, but are excluded from the CI verification path because of the runner and discovery mechanism mismatch.

## What remains unknown

- Whether those 12 tests would pass if run in the CI environment (UNKNOWN: they have never been executed in CI, so their stability in that environment is unknown).
- Whether the pricing-rule implementation is tested elsewhere or if these 12 tests are the only pricing coverage (UNKNOWN: would require reading the tests and code).

## Recommendation

Align the verification surface: either (1) add the 12 tests as TestCase methods so unittest discovers them, (2) configure CI to also run `pytest` or include plain-function tests, or (3) confirm that pricing rules are adequately tested by the 140 unittest tests. Without one of these, CI green is evidence of the 140 unittest tests only, not the full test suite.
