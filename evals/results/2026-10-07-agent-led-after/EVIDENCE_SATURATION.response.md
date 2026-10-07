# Audit: Test Suite Quality

## Summary

The invoicing package test suite provides partial assurance. The totals module is reasonably protected with good parameterization and error case testing, but a critical rounding implementation bug is present (correctly detected by tests). The storage module is completely untested due to an environment variable gate that skips all persistence tests. The suite has 74% line coverage and 64% branch coverage on the tested portions, but 100% of the storage module (3 functions, ~17 lines) is uncovered.

**What this green suite proves:** The arithmetic logic for line and invoice totals works correctly (or would, if the rounding bug were fixed). Error handling for invalid inputs (negative quantities, invalid discounts) works. Constraint enforcement on duplicate invoice numbers is likely correct (untested).

**What it does not prove:** That persistence works. That the built and installed artifact behaves as expected (it inherits the source rounding bug). That Python 3.11 or other declared runtimes work. That cross-platform behavior is correct. That tax calculation always rounds correctly when not divisible by 100.

## Findings (by consequence)

### High Priority

**1. Discount rounding does not round half-up as documented**  
**OBSERVED** — The implementation bug is real and the test correctly catches it.

- `invoicing/totals.py:4` documents the contract: "discounts round half up to the nearest cent"
- `invoicing/totals.py:11` implements it as: `int(gross * (100 - discount_pct) / 100)`
- `int()` truncates toward zero, not rounds: `int(7.5)` = 7, not 8
- Test `test_discount_rounds_half_up_to_the_cent` expects 8 and fails correctly
- Execution evidence: Engine run, test failure signature `AssertionError at test_totals.py:16`

This is material for financial software. The test suite is doing its job by catching this.

**2. Storage module completely untested**  
**OBSERVED** — The storage module is protected by a skip gate, resulting in zero execution.

- `tests/test_storage.py:7` skips all tests when `INVOICING_DB_URL` is not set
- Engine run outcome: 2 invocations skipped, coverage reports 0 lines from storage.py
- Untested: `connect()`, `save_invoice()`, `load_total()`, and all database initialization and constraint handling
- Risk: A broken migration, missing schema, or database transaction bug would not be detected

Evidence: pytest output shows 2 SKIPPED, environment variable not present in test run.

**3. Artifact qualification failed**  
**OBSERVED** — The built wheel fails the same test as source.

- The package builds successfully and installs
- Tests run against the installed artifact and fail on `test_discount_rounds_half_up_to_the_cent`
- This is a direct consequence of the source test failure
- Will not resolve until the rounding bug is fixed

Evidence: Engine artifact qualification report, test invocation against wheel.

### Medium Priority

**4. Broad error expectation in one test**  
**OBSERVED** — Storage test uses `pytest.raises(Exception)` instead of specific error type.

- `tests/test_storage.py:24` expects `Exception` not `sqlite3.IntegrityError`
- This is loose but not materially weak because the test also checks state after rejection (line 26: `assert load_total(conn, "INV-2") == 100`)
- The test is currently skipped, so this does not affect current assurance
- If storage tests run in the future, this is a trap for error-handling regressions

Disposition: The signal is real but low-impact given the state verification.

**5. Python 3.11 declared but not tested in CI**  
**OBSERVED** — Matrix gap between declared support and CI coverage.

- `pyproject.toml:4` declares `requires-python >=3.11`
- `.github/workflows/ci.yml:10` runs only on `python-version: 3.12`
- Python 3.11-specific behavior (if any) will not be caught
- Possible unknowns: syntax compatibility, standard library API changes

Evidence: Configuration files read directly.

**6. No integration testing between modules**  
**INFERRED** — The totals and storage modules are tested independently but never together.

- No test calls `invoice_total()`, then `save_invoice()` with the result, then `load_total()` to verify round-trip
- Risk: A change to one module could break the other without detection
- Especially risky given the rounding bug: persisting and retrieving a malformed total would go undetected

Evidence: Test suite structure, storage tests skipped.

### Low Priority

**7. Tax rounding behavior not explicit**  
**INFERRED** — Tax calculation uses integer division (floor) but behavior is undocumented.

- `invoicing/totals.py:16`: `subtotal * tax_pct // 100`
- Test at line 30-31 uses values that produce exact results (1000 with 10% tax = 200)
- Rounding rule for non-divisible taxes is not specified or tested
- Contrast: discounts claim to round half-up; tax uses floor

Evidence: Code inspection and test case coverage.

**8. Single OS in CI**  
**OBSERVED** — All CI runs on Linux only.

- `.github/workflows/ci.yml:5` runs-on: ubuntu-latest
- Acceptable for a library with no platform-specific code, but Windows or macOS regressions would not be caught
- Informational for packages with platform claims

## Engine Findings: Dispositions

- **NATIVE_TESTS_FAILING** → CONFIRMED, HIGH priority. The test catches a real bug.
- **ARTIFACT_QUALIFICATION_FAILED** → CONFIRMED, HIGH priority. Consequence of source bug.
- **BROAD_ERROR_EXPECTATION_SIGNAL** → PARTIAL. One test lacks specificity; state check partially compensates. Currently moot (test skipped).
- **MATRIX_GAP** → CONFIRMED, MEDIUM priority. Python 3.11 unsupported in CI.
- **CI_SINGLE_OS** → CONTEXTUAL, INFO priority. No cross-platform testing.

## Unknowns and Limitations

1. **CI execution:** Whether the declared test job has ever run on this revision or whether it gates merges. No GitHub API access.
2. **Python 3.11 behavior:** Any version-specific issues specific to 3.11 cannot be ruled out.
3. **Storage module runtime:** Whether database initialization, queries, and constraints actually work (tests skipped).
4. **Tax rounding intent:** Whether floor (// operator) is acceptable or if half-up is required to match discount rounding.
5. **Flakiness:** Single test run provides no baseline for instability; insufficient data to classify the one failure as flaky.

## Recommendations

**Before shipping:**
1. **Fix the rounding bug** in `invoicing/totals.py:11`. Use `decimal.Decimal` with `ROUND_HALF_UP` or implement manual rounding.
2. **Unskip storage tests** by providing an in-memory SQLite database or `INVOICING_DB_URL` in CI. Remove the environment variable gate.
3. **Clarify tax rounding** — either document that floor rounding is intentional or match discount rounding to half-up.

**Strengthen assurance:**
1. Add Python 3.11 to CI matrix.
2. Add an integration test combining totals and storage.
3. Replace `pytest.raises(Exception)` with `pytest.raises(sqlite3.IntegrityError)`.
4. Add a negative control: a test case where tax does not divide evenly, documenting expected rounding.

## Assurance Report

Assurance Report: `C:\Users\rafaelryan\.assertiva\reports\workspace-9370f26776997331\audit.html`

---

## Evidence Log

### Files Read
- `C:\Users\RAFAEL~1\AppData\Local\Temp\claude\c--Users-rafaelryan-Desktop-github-Assertiva\e77d3565-51c0-4283-92ea-3b9d860d6a63\scratchpad\evals-after\EVIDENCE_SATURATION\workspace\pyproject.toml` — Project metadata and pytest config
- `C:\Users\RAFAEL~1\AppData\Local\Temp\claude\c--Users-rafaelryan-Desktop-github-Assertiva\e77d3565-51c0-4283-92ea-3b9d860d6a63\scratchpad\evals-after\EVIDENCE_SATURATION\workspace\invoicing\__init__.py` — Package init (empty)
- `C:\Users\RAFAEL~1\AppData\Local\Temp\claude\c--Users-rafaelryan-Desktop-github-Assertiva\e77d3565-51c0-4283-92ea-3b9d860d6a63\scratchpad\evals-after\EVIDENCE_SATURATION\workspace\invoicing\storage.py` — Persistence module (unexecuted)
- `C:\Users\RAFAEL~1\AppData\Local\Temp\claude\c--Users-rafaelryan-Desktop-github-Assertiva\e77d3565-51c0-4283-92ea-3b9d860d6a63\scratchpad\evals-after\EVIDENCE_SATURATION\workspace\invoicing\totals.py` — Arithmetic module (partially tested)
- `C:\Users\RAFAEL~1\AppData\Local\Temp\claude\c--Users-rafaelryan-Desktop-github-Assertiva\e77d3565-51c0-4283-92ea-3b9d860d6a63\scratchpad\evals-after\EVIDENCE_SATURATION\workspace\tests\test_storage.py` — Storage tests (all skipped)
- `C:\Users\RAFAEL~1\AppData\Local\Temp\claude\c--Users-rafaelryan-Desktop-github-Assertiva\e77d3565-51c0-4283-92ea-3b9d860d6a63\scratchpad\evals-after\EVIDENCE_SATURATION\workspace\tests\test_totals.py` — Totals tests (7 of 9 invocations execute)
- `C:\Users\RAFAEL~1\AppData\Local\Temp\claude\c--Users-rafaelryan-Desktop-github-Assertiva\e77d3565-51c0-4283-92ea-3b9d860d6a63\scratchpad\evals-after\EVIDENCE_SATURATION\workspace\.github\workflows\ci.yml` — CI configuration

### Commands Executed
1. `assertiva --version` — Confirmed engine availability (0.5.8)
2. `assertiva audit . --output json` — Static analysis only (no execution)
3. `assertiva audit . --execute --output json` — Full audit with execution, coverage, and artifact qualification
4. `python -c "from invoicing.totals import line_total; result = line_total(1, 15, 50); ..."` — Manual verification of rounding bug
5. `python -m pytest tests/ -v` — Direct pytest execution to observe test outcomes
6. `assertiva audit . --execute --output json | python -c "..."` — Parsed JSON reports for metrics and findings
7. `assertiva audit . --assessment <file>` — Attached assessment to report with dispositions

### Test Execution Evidence (Observed)
- **Total invocations:** 9
- **Passed:** 6 (test_line_without_discount, test_full_discount_is_free, test_negative_inputs_are_rejected[2 variants], test_discount_out_of_range_is_rejected, test_invoice_total_adds_tax_on_the_subtotal)
- **Failed:** 1 (test_discount_rounds_half_up_to_the_cent)
- **Skipped:** 2 (test_saved_invoice_total_round_trips, test_duplicate_invoice_number_is_rejected)
- **Exit code:** 1 (test suite failed)
- **Coverage:** 74.4% line (67/90), 64.3% branch (9/14)

### Artifact Qualification Evidence
- **Build:** PASS
- **Install:** PASS
- **Import:** PASS
- **Tests against installed artifact:** FAIL (same test, same failure)
- **Dependency closure:** PASS

### Static Analysis Signals
- **Weak oracle signal:** 0 tests
- **Broad error expectation signal:** 1 test (test_duplicate_invoice_number_is_rejected)
- **Error status only signal:** 0 tests
- **Negative path tests:** 3 tests with error expectations
- **Negative paths with state checks:** 1 test (duplicate invoice test checks state after rejection)
