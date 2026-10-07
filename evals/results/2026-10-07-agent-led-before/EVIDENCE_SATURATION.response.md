# Assertiva Audit Report: invoicing Package Test Suite

Assertiva mode: engine-backed

## Overview

The invoicing package is a small Python library (92 lines across 5 source/test files) providing integer-cent invoice arithmetic and SQLite-backed invoice persistence. Static analysis identified three material findings affecting test quality and delivery-surface completeness.

## Test Suite Composition

**DETERMINISTIC FACT (E0)** — Static inventory from pytest discovery:
- 6 test cases defined across 2 modules:
  - `tests/test_totals.py`: 5 test definitions (1 parametrized → 2 invocations)
  - `tests/test_storage.py`: 2 test definitions (both skipped without INVOICING_DB_URL environment variable)
- 57 lines of test code
- Project declares Python >=3.11 support

## Findings

### 1. Broad Error Type Expectation (MEDIUM)

**HEURISTIC SIGNAL (E3)** — `test_duplicate_invoice_number_is_rejected` (tests/test_storage.py:22-26):

```python
with pytest.raises(Exception):
    save_invoice(conn, "INV-2", 200)
```

**Observation**: Test catches `Exception` (the base class), not the specific error type the contract defines. The storage module uses SQLite's PRIMARY KEY constraint; duplicate inserts raise `sqlite3.IntegrityError`.

**Risk**: An overly broad exception expectation allows silent failures. If `save_invoice` raises an unrelated exception (e.g., database connection error, type mismatch), the test passes incorrectly.

**Recommendation**: Replace with `pytest.raises(sqlite3.IntegrityError)` to assert the specific contract violation the function documents.

---

### 2. Declared Python 3.11 Not Tested in CI (MEDIUM)

**DECLARED FACT (E2)** — Configuration:
- `pyproject.toml` declares `requires-python = ">=3.11"`
- `.github/workflows/ci.yml` specifies only Python 3.12 in the test job

**DETERMINISTIC FACT (E1)** — Matrix gap identified by static analysis:
- Declared support: Python 3.11+
- CI test coverage: 3.12 only
- Missing: 3.11

**Risk**: Python 3.11 behavior differences (language, standard library, type annotation semantics) are not evidenced by CI execution. A compatibility regression in 3.11 could ship undetected.

**Recommendation**: Add a CI job targeting Python 3.11 to gate merges, or narrow the declared support range if 3.11 is not genuinely required.

---

### 3. Single Operating System in CI (INFO)

**DECLARED FACT (E2)** — CI matrix:
- `.github/workflows/ci.yml`: `runs-on: ubuntu-latest` (Linux only)
- No Windows, macOS, or other platform jobs declared

**Observation**: The project uses SQLite with file paths managed by os.environ. While the code does not show platform-specific logic, single-OS testing provides limited signal for cross-platform compatibility.

**Recommendation**: If the package targets multiple platforms, add platform-specific CI jobs. If Linux-only delivery is intentional, document it explicitly.

---

## Assertion Strength and Oracle Adequacy

**HEURISTIC SIGNALS (E3)** — Test inventory metrics:

| Metric | Count | Assessment |
|--------|-------|------------|
| Test definitions | 6 | Small suite; reasonable for library scope |
| Parametrized invocations | 2 (from 1 definition) | `test_negative_inputs_are_rejected` covers quantity/price combinations |
| Error-contract tests | 2 | Both use `ValueError` with `match` patterns (specific); invoice storage uses broad `Exception` |
| Negative-path tests | 3 | Covers discount boundary, negative inputs, duplicate key |
| Tests with state assertion | 5 / 6 | Good: most verify observable side effects after rejection |

**Observation**: The totals.py module has well-scoped error assertions with regex matching on message content. The storage.py module's duplicate-key test has weak oracle strength due to broad exception type.

**UNKNOWN**: Whether tests execute and pass. The suite requires `INVOICING_DB_URL` environment variable; CI does not set it, so storage tests skip in pipeline.

---

## Verification Surface Completeness

**DECLARED FACT (E2)** — CI check inventory:

```yaml
Tool: pytest
Command: pytest -q
Declared: .github/workflows/ci.yml (test job, step 4)
Matrix: ubuntu-latest, Python 3.12
Execution status: UNKNOWN (not executed in audit scope)
```

**Limitations**:
- No linting, type checking, or static analysis declared beyond pytest
- No coverage measurement configured or reported
- Storage tests skip without INVOICING_DB_URL setup
- Build and package behavior not tested

**UNKNOWN**: Whether the declared CI check actually runs on merges, on which revisions, and its pass/fail history.

---

## Test Execution Status

**DETERMINISTIC FACT (E1)** — Audit scope:
- Static analysis only (no `--execute` flag)
- Tests were not run
- Test outcomes: UNKNOWN
- Coverage: UNKNOWN
- Mutation / negative-control strength: UNKNOWN

---

## Recommendations for Improvement

### High Priority

1. **Narrow error expectations in storage tests**
   - Replace `pytest.raises(Exception)` with `pytest.raises(sqlite3.IntegrityError)`
   - Add a brief docstring to `test_duplicate_invoice_number_is_rejected` explaining the IntegrityError contract
   - Rationale: Strengthens the oracle; prevents accidental masking of unrelated failures

2. **Add Python 3.11 to CI**
   - Update `.github/workflows/ci.yml` to include a job for Python 3.11
   - Rationale: Enforces declared compatibility; detects version-specific regressions before release

### Medium Priority

3. **Provision INVOICING_DB_URL in CI**
   - Configure the environment variable in the CI test job (e.g., `INVOICING_DB_URL=:memory:`)
   - Remove the skip condition on storage tests
   - Rationale: Executes persistence tests in the pipeline; currently they are skipped, leaving storage.py untested

4. **Add coverage reporting**
   - Install pytest-cov and add `--cov=invoicing --cov-report=term-missing` to the pytest command
   - Set a coverage target (e.g., 80%) in CI
   - Rationale: Provides objective evidence of test surface; identifies untested code paths

### Optional / Future

5. Consider mutation testing on arithmetic boundary logic (discount rounding in line_total)
6. Document the file-based vs. in-memory SQLite usage expectations
7. Add type hints to test fixtures if linting is added

---

## Claim Boundaries and Evidence Limitations

**What this audit covers (DETERMINISTIC)**:
- Static structure of test suite and source code
- Declared CI configuration and matrix gaps
- Heuristic signals about exception scope and parameter coverage

**What this audit does NOT cover (UNKNOWN without --execute)**:
- Actual test execution outcomes (pass/fail)
- Line/branch/condition coverage achieved
- Assertion behavior under real execution
- Mutation test results
- Build, package, startup, or deployment verification
- Flaky behavior or retry dependence

**Why static-only audit is appropriate here**: The project is small (92 lines total), test suite is visible in full, and findings (broad exception type, matrix gap) are configuration-level issues that don't require execution evidence.

---

## Summary

The invoicing package has a **small, focused test suite** with **mixed oracle strength**:

- ✓ Totals.py tests have specific error assertions with regex matching
- ✓ Negative-path and parameterized coverage is reasonable for scope
- ✗ Storage.py exception expectation is too broad
- ✗ Declared Python 3.11 support is not tested
- ✗ Storage tests skip in CI due to missing environment setup

**Overall assessment**: READY_WITH_GAPS

The suite can detect basic arithmetic and constraint violations but cannot prove storage behavior correctness in the pipeline. Recommended actions are low-effort configuration changes (CI matrix, environment variable, error type) that materially improve delivery confidence without expanding test scope.

---

## Evidence Log

### Files Read
- `C:\Users\RAFAEL~1\AppData\Local\Temp\claude\c--Users-rafaelryan-Desktop-github-Assertiva\e77d3565-51c0-4283-92ea-3b9d860d6a63\scratchpad\evals-before\EVIDENCE_SATURATION\agent.md`
- `C:\Users\RAFAEL~1\AppData\Local\Temp\claude\c--Users-rafaelryan-Desktop-github-Assertiva\e77d3565-51c0-4283-92ea-3b9d860d6a63\scratchpad\evals-before\EVIDENCE_SATURATION\workspace\pyproject.toml`
- `C:\Users\RAFAEL~1\AppData\Local\Temp\claude\c--Users-rafaelryan-Desktop-github-Assertiva\e77d3565-51c0-4283-92ea-3b9d860d6a63\scratchpad\evals-before\EVIDENCE_SATURATION\workspace\tests\test_storage.py`
- `C:\Users\RAFAEL~1\AppData\Local\Temp\claude\c--Users-rafaelryan-Desktop-github-Assertiva\e77d3565-51c0-4283-92ea-3b9d860d6a63\scratchpad\evals-before\EVIDENCE_SATURATION\workspace\tests\test_totals.py`
- `C:\Users\RAFAEL~1\AppData\Local\Temp\claude\c--Users-rafaelryan-Desktop-github-Assertiva\e77d3565-51c0-4283-92ea-3b9d860d6a63\scratchpad\evals-before\EVIDENCE_SATURATION\workspace\invoicing\storage.py`
- `C:\Users\RAFAEL~1\AppData\Local\Temp\claude\c--Users-rafaelryan-Desktop-github-Assertiva\e77d3565-51c0-4283-92ea-3b9d860d6a63\scratchpad\evals-before\EVIDENCE_SATURATION\workspace\invoicing\totals.py`
- `C:\Users\RAFAEL~1\AppData\Local\Temp\claude\c--Users-rafaelryan-Desktop-github-Assertiva\e77d3565-51c0-4283-92ea-3b9d860d6a63\scratchpad\evals-before\EVIDENCE_SATURATION\workspace\.github\workflows\ci.yml`
- `C:\Users\rafaelryan\.assertiva\reports\workspace-9a7eca33e0d51d6a\audit.html` (partial read for validation)

### Commands Executed
- `assertiva --version`
  - Result: assertiva 0.5.8
  - Evidence: Engine availability confirmed
  
- `assertiva audit . --output json` (from workspace directory)
  - Result: Audit completed; 3 findings identified; report generated at C:\Users\rafaelryan\.assertiva\reports\workspace-9a7eca33e0d51d6a\audit.html
  - Evidence: E0 deterministic engine output; static analysis only (no test execution)
  - Output: audit_output.json (57KB JSON structure)
  - Trace: C:\Users\rafaelryan\.assertiva\traces\workspace-9a7eca33e0d51d6a\audit-20261007T220549163409Z.jsonl
  
- File discovery (find command)
  - Located: 5 Python source files (pyproject.toml, 2 source modules, 2 test modules, 1 CI workflow)

### Assurance Report

Assurance Report: C:\Users\rafaelryan\.assertiva\reports\workspace-9a7eca33e0d51d6a\audit.html

Run ID: e719050ccea04b71  
Generated: 2026-10-07T22:05:49+00:00  
Assertiva Version: 0.5.8
