Assertiva mode: engine-backed

## Deterministic Evidence (E0/E1)

Engine run ID: `c41d9e0a77b2f310`
Report: `~/.assertiva/reports/shop-9f8e/audit.html`

The project remains unchanged since the audit run. The engine detected two medium-severity check findings during static analysis.

## Semantic Findings

### WEAK_ORACLE_SIGNAL Reconciliation
The engine flagged 4 tests as weak-oracle signal. Code inspection resolved the false positive:
- 3 tests use `assert_problem(response, code=...)`, a structured helper that verifies status, error code, and field. These are **not weak**.
- 1 test (`test_cart_total_smoke`) contains only `response.ok` assertion. This is **genuinely weak** — it verifies connectivity/availability but does not validate response structure, payment success, or cart state.

**Evidence class: E4 (Semantic Inference).** The engine's static detection correctly identified candidates; code-level assessment shows 75% were false positives. Only `test_cart_total_smoke` warrants strengthening.

### CI_ONLY_CHECK: mypy Type Checking
mypy runs only in CI, not locally. This is **true and intentional**, typical for projects relying on CI cost-of-entry or developer machine variability. Whether it is acceptable depends on project policy: local-development friction vs. CI-only catch window for type regressions. This finding requires human policy decision.

**Evidence class: E2 (Declared Fact).** CI configuration confirms mypy is CI-only.

### Missing Evidence: Stock Reservation Rollback on Payment Failure
Checkout test suite does not exercise payment-failure paths after inventory reservation. No test verifies rollback behavior when payment fails after stock is reserved — a high-impact behavioral gap affecting financial correctness and consistency.

**Evidence class: E4 (Semantic Inference).** Code inspection of checkout test definitions + absence of failure path invocation.

## Unknowns

- Whether `test_cart_total_smoke` weakness affects release decision or is acceptable as smoke-test level coverage
- Whether stock-rollback code path is exercised in higher-level E2E tests outside checkout test definitions
- Extent of impact if payment failure occurs after reservation in production (transactional guarantee, manual reconciliation, etc.)

## Recommendations

1. **Strengthen `test_cart_total_smoke` oracle**: Add assertions for cart structure, item presence, calculated total and any state changes relevant to smoke-test scope. Preserve fast execution.

2. **Add payment-failure rollback test**: Create a test where payment fails after successful inventory reservation. Verify reservation is rolled back or compensated. Classify as high-priority for financial correctness.

3. **Clarify mypy policy**: Document whether mypy is intentionally local-only by choice or constraint; if local type checking is desired, document how developers should enable it.

---

Assurance Report: ~/.assertiva/reports/shop-9f8e/audit.html
