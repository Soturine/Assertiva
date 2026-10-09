# Disposition: WEAK_ORACLE_SIGNAL Finding

## Summary
The finding nominates two tests with weak oracles. One has both weak and meaningful assertions; the other proves minimal behavior despite significant implementation complexity.

## Per-Test Dispositions

### Test 1: `src/server.test.ts › server module loads without side effects`
- **Signal**: EXISTENCE (`expect(mod.createServer).toBeDefined()`)
- **Disposition**: `CONTEXTUAL`
- **Priority**: `low`
- **Rationale**: The EXISTENCE signal is weak in isolation — checking that a function is defined proves nothing about its behavior. However, the test's actual contract is side-effect safety, established by the spy assertion `expect(listenSpy).not.toHaveBeenCalled()`. The spy check is a meaningful oracle: if the module called `listen()` during import, the test fails. The `toBeDefined()` assertion is incidental; the real work is the spy. This is an intentionally simple test whose contract is "module imports without calling listen()," not "function exists."
- **Evidence**: Test code shows two assertions; the spy assertion carries the meaningful contract.
- **Basis**: INFERRED from test structure and contract claim.

### Test 2: `src/invoices.test.ts › creates an invoice`
- **Signal**: TRUTHY (`expect(invoice).toBeTruthy()`)
- **Disposition**: `CONFIRMED`
- **Priority**: `high`
- **Rationale**: This test has a genuine weakness. The implementation claims to compute totals, tax, and a due date, and to persist the invoice. The test checks only that invoice is not null/falsy — it observes no computed values, no state persistence, no side effects. The oracle is a tautology: `createInvoice` would return a truthy object under nearly any circumstance, even if totals were wrong, tax uncalculated, or the database write silently failed. This is a false green. The context notes no other test checks invoice totals, which makes this gap material: a broken computation or persistence layer would pass the entire suite.
- **Evidence**: Test body; implementation contract (persists, computes); absence of alternative coverage noted in context.
- **Basis**: OBSERVED from test code and contract.

## Recommendation
Test 2 is the actionable finding: add assertions for the computed and persisted values. Test 1 is correctly structured; the heuristic signal is a false positive on a weak sub-assertion whose role is incidental.
