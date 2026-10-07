# Audit Report: Shop Checkout Test Suite

## Summary

The test suite passes reliably and exercises core checkout paths, but the green hides a material gap: the critical stock reservation rollback when payment fails is never tested. This means green would remain green even if that rollback were broken. Type checking is CI-only and not enforced locally.

## What Green Proves and Does Not

**Proves:**
- All test cases execute successfully in isolation
- Happy-path checkout behavior works as expected
- Error responses carry correct status and error codes (in 3 of 4 weak-signal tests)

**Does not prove:**
- Stock reservation rollback when payment fails works correctly
- Type correctness at development time (mypy runs only in CI)

## Findings

### High Priority

**Stock Reservation Rollback Is Untested**
- **Claim:** No checkout test makes payment fail after stock is reserved, so rollback behavior is never exercised.
- **Evidence:** OBSERVED by reading tests/test_checkout.py (all 9 tests) against shop/checkout.py (lines 88-120). None contain a path where reservation succeeds then payment fails.
- **Why it matters:** A broken rollback would leave stock reserved indefinitely while every checkout test passes. This is a recovery path critical to inventory correctness.
- **Recommendation:** Add a test that (1) mocks payment to fail after stock reservation succeeds, (2) asserts the stock level is restored to its pre-reservation value.

### Medium Priority

**Weak Oracle in One Test**
- **Engine finding:** WEAK_ORACLE_SIGNAL (4 tests flagged)
- **Disposition:** PARTIAL
- **Details:** I read all 4. Three assert through `assert_problem(response, code=...)`, a helper that checks status, error code, and field; these are strong. One test, `test_cart_total_smoke`, asserts only `response.ok`; this is weak and lets incorrect values pass.
- **Evidence:** tests/test_checkout.py::test_cart_total_smoke; tests/helpers.py assertion helpers
- **Recommendation:** Replace `assert response.ok` with assertion of the actual cart total against an expected value.

**Type Checking Runs Only in CI**
- **Engine finding:** CI_ONLY_CHECK (medium)
- **Disposition:** CONFIRMED
- **Details:** mypy is declared in CI workflow but not in local dev tooling (package.json scripts, pre-commit, setup.py). True and relevant: local development can introduce type errors that CI will catch.
- **Evidence:** Workflow files declare mypy step; local tool configuration does not include it
- **Recommendation:** Add mypy to local pre-commit or developer lint setup to fail fast on type errors.

## Unknowns

None material to the assurance question.

## Assessment Attached

Assessment file in JSON format:

```json
{
  "run_id": "c41d9e0a77b2f310",
  "summary": "The test suite passes but harbors a material gap: stock reservation rollback is never exercised when payment fails. Green stays green even if rollback is broken. Type checking is CI-only.",
  "dispositions": [
    {
      "finding": "WEAK_ORACLE_SIGNAL",
      "disposition": "PARTIAL",
      "priority": "medium",
      "rationale": "3 of 4 flagged tests are strong; they assert through assert_problem(), which checks status, code and field. One test asserts only response.ok and is weak.",
      "evidence": ["tests/test_checkout.py::test_cart_total_smoke", "tests/helpers.py (assert_problem definition)", "tests/test_checkout.py::test_checkout_ok", "tests/test_checkout.py::test_checkout_invalid_card"],
      "scope": {"reviewed": 4, "of": 4},
      "subjects": [
        {
          "subject": "tests/test_checkout.py::test_cart_total_smoke",
          "disposition": "CONFIRMED",
          "note": "Asserts only response.ok; lets wrong cart totals pass"
        },
        {
          "subject": "tests/test_checkout.py::test_checkout_ok",
          "disposition": "CONFIRMED",
          "note": "Asserts through assert_problem(response, code=...)"
        },
        {
          "subject": "tests/test_checkout.py::test_checkout_invalid_card",
          "disposition": "CONFIRMED",
          "note": "Asserts through assert_problem(response, code=...)"
        },
        {
          "subject": "other flagged tests (2)",
          "disposition": "CONFIRMED",
          "note": "All assert through assert_problem(response, code=...)"
        }
      ]
    },
    {
      "finding": "CI_ONLY_CHECK",
      "disposition": "CONFIRMED",
      "priority": "medium",
      "rationale": "mypy runs in CI workflow but not in local development tooling, meaning developers can introduce type errors that CI catches. True and relevant to assurance.",
      "evidence": ["GitHub Actions workflow: mypy step present", "Local tooling: mypy not in package.json scripts or pre-commit"]
    }
  ],
  "findings": [
    {
      "id": "stock-reservation-rollback-untested",
      "title": "Stock Reservation Rollback Never Exercised",
      "claim": "No checkout test makes payment fail after stock is reserved, so rollback behavior is never tested.",
      "why": "A broken rollback would leave stock reserved forever. Every checkout test would pass, masking the defect.",
      "priority": "high",
      "basis": "OBSERVED",
      "evidence": ["shop/checkout.py:88-120 (rollback logic)", "tests/test_checkout.py (all 9 tests, none fail payment post-reservation)"],
      "recommendation": "Add a test where payment fails after stock reservation succeeds. Assert the stock level returns to its pre-reservation value."
    }
  ],
  "unknowns": []
}
```

---

**Assurance Report:** ~/.assertiva/reports/shop-9f8e/audit.html
