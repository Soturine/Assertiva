# An intentionally simple test and a shallow one

## Identity
- case ID: SIMPLE_TEST_VS_SHALLOW_TEST
- status: grader-ready
- primary behavior: distinguish a test whose contract is simple from a test that is superficial for its contract
- related owner documents: SKILL.md, references/TEST_QUALITY.md

## Context / fixture
A TypeScript API (Vitest). `assertiva audit . --execute` (run_id `c7a0e5b21d9f4483`) reports, among others:

```json
{"id": "WEAK_ORACLE_SIGNAL", "code": "WEAK_ORACLE_SIGNAL", "severity": "medium",
 "evidence": {"language": "javascript", "count": 2,
   "tests": ["src/server.test.ts › server module loads without side effects",
             "src/invoices.test.ts › creates an invoice"],
   "signals": {"EXISTENCE": 1, "TRUTHY": 1}}}
```

```ts
// src/server.test.ts
test('server module loads without side effects', async () => {
  const mod = await import('./server')
  expect(mod.createServer).toBeDefined()
  expect(listenSpy).not.toHaveBeenCalled()
})

// src/invoices.test.ts
test('creates an invoice', async () => {
  const invoice = await createInvoice({ customerId: 'c1', lines: [{ sku: 'A', qty: 2, unit: 15 }] })
  expect(invoice).toBeTruthy()
})
```

`createInvoice` computes totals, tax and a due date, and persists the invoice. No other test checks invoice totals.

## Prompt / task
Give your disposition of this finding for each test.

## Expected behavior
- The module-load test checks its actual contract (the module exports its factory and does not start listening on import); a presence check is appropriate there — contextual, no change needed.
- The invoice test is shallow for its contract: any truthy object passes, so wrong totals, tax or due date would stay green, and nothing else covers them — confirmed as material, with concrete assertions to add (totals, tax, due date, persisted state).
- Uses per-test dispositions (partial) rather than one verdict for the whole finding.

## Prohibited behavior
- Treating both tests alike (both weak, or both fine).
- Recommending that the module-load test assert unrelated values to "strengthen" it.

## Evidence requirements
Each test's body and what its subject promises.

## Scoring dimensions
- contract-relative judgment per test (critical);
- concrete, contract-based recommendation (major);
- disposition granularity (major).

## Acceptable alternatives
Suggesting that the load test also check a second export is fine as optional; any assertion style that pins the invoice's values works.

## Pass condition
The simple test is kept as adequate for its contract, the shallow one is confirmed with specific missing checks, and the dispositions are per test.
