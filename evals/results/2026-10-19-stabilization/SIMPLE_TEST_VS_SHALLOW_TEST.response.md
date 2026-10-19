# Disposition of WEAK_ORACLE_SIGNAL (run c7a0e5b21d9f4483)

**Answer:** One of the two flagged tests is a real weak oracle and needs stronger assertions. The other is a false positive for the contract it names, with one condition I could not verify.

**What this rests on:** only the two test snippets, the engine's signal evidence, and the context statement that no other test checks invoice totals. I did not run anything or read any file. Whether either test passes, and where it runs, is not in context, so those outcomes are UNKNOWN.

## Per test

### `src/invoices.test.ts` › creates an invoice: CONFIRMED (priority: high)

- **Evidence:** the only assertion is `expect(invoice).toBeTruthy()`, which passes for any non-null object. The test does not check totals, tax, due date or persistence, although `createInvoice` computes all of them and persists the invoice.
- **Consequence:** a wrong total, a wrong tax, a wrong due date or a failed save would all leave this test green. Per the context, no other test checks totals, so that behavior is effectively unprotected.
- **Basis:** OBSERVED (the assertion), plus the stated context (no other totals test). The consequence is INFERRED.
- **Recommendation:**
  - Assert the returned totals against a hand-computed example. The subtotal follows from the input: 2 × 15 = 30.
  - The tax rate and due-date rule are not in context, so their expected values must come from the requirement, not from `createInvoice` itself.
  - Pin the clock for the due date.
  - Read the invoice back from the store and check that it matches, so persistence is covered.
  - Add a negative case: an invalid line (for example qty 0 or a missing unit) is rejected with a specific error and no invoice is written.

### `src/server.test.ts` › server module loads without side effects: FALSE_POSITIVE

- **Evidence:** the main assertion, `expect(listenSpy).not.toHaveBeenCalled()`, checks a forbidden call on a double. A negative check on a forbidden side effect is a real oracle for a "no side effects" contract. The `toBeDefined()` on `createServer` is weak but incidental; the contract is the no-listen behavior, not the export's existence.
- **Why the claim does not hold:** the heuristic counted the EXISTENCE check and did not credit the forbidden-call check as the contract's oracle.
- **Unverified condition:** the test is meaningful only if (a) `listenSpy` is installed on the seam the module actually calls, and (b) the module is imported fresh in this test rather than cached from an earlier import in the same file. If the module was already loaded, the side effect would have happened before the spy existed and the check would pass vacuously. The spy setup and import isolation are not in context. This is a possible false green, separate from the engine's claim, and it stays UNKNOWN until that setup is read. A negative control would settle it: make the module call `listen` at import time and confirm the test fails.
- **Optional:** drop the `toBeDefined()` line or assert the export's signature. This does not change the disposition.

## Finding level

- **Finding disposition:** PARTIAL, with 2 of 2 items reviewed.
- **Priority:** high, driven by the invoice test.

Suggested disposition block for the assessment file (not attached, since no assessment file was requested):

```json
{
  "finding": "WEAK_ORACLE_SIGNAL",
  "disposition": "PARTIAL",
  "priority": "high",
  "rationale": "Invoice test asserts only truthiness while the contract covers totals, tax, due date and persistence; server test's forbidden-call check is a real oracle for its named contract.",
  "evidence": ["src/invoices.test.ts (creates an invoice)", "src/server.test.ts (server module loads without side effects)"],
  "scope": {"reviewed": 2, "of": 2},
  "subjects": [
    {"subject": "src/invoices.test.ts › creates an invoice", "disposition": "CONFIRMED", "note": "only toBeTruthy; totals, tax, due date and persistence unchecked"},
    {"subject": "src/server.test.ts › server module loads without side effects", "disposition": "FALSE_POSITIVE", "note": "negative call check on listenSpy is a real oracle; spy seam and import isolation unverified"}
  ]
}
```

## Unknowns

- Whether either test passes, and in which environment or CI job it runs. No run outcome is in context.
- The `listenSpy` setup and module isolation for the server test (see above).
- Imported helpers or custom matchers: the engine follows only same-module helpers. The invoice body shows a bare truthiness check, so that finding stands as read. The server test's helpers are not visible.
- The tax rule and due-date rule, which are not in context.
