# Audit result: shop

## Answer

Most checkout and cart error paths are protected by meaningful assertions. The highest-consequence gap is one no tool reported: **stock-reservation rollback when payment fails is never exercised by any checkout test.** A broken rollback would leave stock reserved forever while the suite stays green. Separately, one cart test (`test_cart_total_smoke`) would pass with a wrong total, and type checking (`mypy`) protects only changes that reach CI, not local runs.

What this rests on: engine run `c41d9e0a77b2f310`; reading all 4 tests flagged by `WEAK_ORACLE_SIGNAL` together with the `assert_problem` helper; reading the checkout code and its tests for the payment-failure path; the engine's `CI_ONLY_CHECK` finding against the CI configuration. The project has not changed since that run.

## What is protected

- **Error contracts on the 3 tests that use `assert_problem(response, code=...)`.** The helper checks the HTTP status, the error code and the field, which is a specific oracle, not a weak one. These tests would fail if the API returned the wrong error code or blamed the wrong field.
- **Type correctness in CI:** `mypy` runs in the CI workflow (declared), so changes that go through CI get type-checked.

## What is not protected

1. **Stock-reservation rollback on payment failure (high).** No checkout test makes payment fail after stock is reserved, so the rollback path is never exercised and nothing checks the stock level afterwards. A regression that skips or breaks the rollback would leak reserved stock, and every test would stay green. *How I know:* INFERRED from reading the checkout code (the reservation-then-payment sequence and its rollback) and the checkout tests (no test produces a payment failure after reservation). The engine did not raise this.
2. **Cart total correctness in `test_cart_total_smoke` (medium).** It asserts only `response.ok`, so a wrong total, missing items or a wrong currency would pass. *How I know:* OBSERVED by reading the test. This confirms the engine's `WEAK_ORACLE_SIGNAL` for that one test.
3. **Type checking outside CI (medium).** `mypy` runs only in CI. Local runs and hooks don't type-check, so type errors surface only after push, and only for changes that go through CI. *How I know:* DECLARED (CI configuration), confirmed by the engine's `CI_ONLY_CHECK`.

## Decisions on the engine's findings

| Finding | Disposition | Reason |
| --- | --- | --- |
| `WEAK_ORACLE_SIGNAL` (4 tests) | **PARTIAL**: reviewed 4 of 4 | `test_cart_total_smoke` is weak (CONFIRMED). The other 3 are FALSE_POSITIVE: they assert through `assert_problem`, an imported helper the heuristic does not follow, which checks status, error code and field |
| `CI_ONLY_CHECK` (`mypy`) | **CONFIRMED**, medium | True and relevant: type checking is not part of any local path |

## What stays unknown

- Whether CI ran green on this exact revision. No provider run with a head SHA was checked, so "CI green" cannot be claimed for HEAD.
- Whether the rollback is actually correct today. The gap is that no test would tell. Whether the code is broken is not established.

## Recommendations

1. Add a checkout test where payment fails after stock has been reserved, and assert the stock level (and the order/reservation state) afterwards, not just the error response. Take the expected values from the business rule (stock returns to its pre-checkout level), not from what the code returns today.
2. Strengthen `test_cart_total_smoke` to assert the total (and line items) against a hand-computed expected value, or rename it so it is clearly a smoke check, if "responds OK" is all it is meant to cover.
3. Offer `mypy` locally: a pre-commit hook or a documented `make typecheck`/tox env, so type errors are caught before CI.

I can draft items 1 and 2 through `assertiva improve`, in a candidate workspace, qualified with a negative control that breaks the rollback (and one that breaks the total). That would show the baseline missing those breaks and the candidate catching them. Nothing gets applied to the project without your explicit approval of the named change ids.

## Assessment attached to the engine report

The report must carry the same conclusion and dispositions as this answer. The assessment below is attached to run `c41d9e0a77b2f310` with:

```
assertiva audit <project> --assessment assessment.json
```

```json
{
  "run_id": "c41d9e0a77b2f310",
  "summary": "Most checkout and cart error paths are protected by specific assertions, but stock-reservation rollback on payment failure is never exercised by any test: a broken rollback would leave stock reserved while the suite stays green. One cart test (test_cart_total_smoke) asserts only response.ok and would pass with a wrong total; mypy runs only in CI. Whether CI ran green on this exact revision is unknown (no provider run checked).",
  "lang": "en",
  "dispositions": [
    {
      "finding": "WEAK_ORACLE_SIGNAL",
      "disposition": "PARTIAL",
      "rationale": "Reviewed all 4 tests. 3 assert through assert_problem(response, code=...), an imported helper that checks status, error code and field, so they are not weak (FALSE_POSITIVE). test_cart_total_smoke asserts only response.ok and would pass with a wrong total (CONFIRMED).",
      "evidence": ["assert_problem helper (checks status, error code, field)", "the 4 tests listed in the finding's evidence"],
      "scope": {"reviewed": 4, "of": 4},
      "subjects": [
        {"subject": "test_cart_total_smoke", "disposition": "CONFIRMED", "note": "asserts only response.ok"}
      ]
    },
    {
      "finding": "CI_ONLY_CHECK",
      "disposition": "CONFIRMED",
      "priority": "medium",
      "rationale": "mypy runs only in CI; no local or hook path type-checks, so type errors surface only after push.",
      "evidence": ["CI_ONLY_CHECK evidence: CI workflow step running mypy"]
    }
  ],
  "findings": [
    {
      "id": "reservation-rollback-untested",
      "title": "Stock reservation rollback on payment failure is never exercised",
      "claim": "No checkout test makes payment fail after stock is reserved, so the rollback path is never run or checked.",
      "why": "A broken or skipped rollback would leave stock reserved forever while every test stays green.",
      "priority": "high",
      "basis": "INFERRED",
      "evidence": ["checkout code: reservation followed by payment, rollback on failure", "checkout tests: none produce a payment failure after reservation"],
      "recommendation": "Add a test where payment fails after reservation and assert the stock level and reservation state afterwards, with expected values from the business rule."
    }
  ],
  "unknowns": [
    "Whether CI ran green on this revision: no provider run with a head SHA was checked.",
    "Whether the rollback code is correct today: no test exercises it."
  ]
}
```

This context did not allow running commands, so I have not run the attach command, and I have not verified its validation result. Once it runs, the engine re-renders the same report with these dispositions next to its raw evidence. If it refuses (exit 2), the reason names the field to fix.

Assurance Report: ~/.assertiva/reports/shop-9f8e/audit.html
