# Mocked-away payment "integration" test: what can and cannot be claimed

## Answer

This test does **not** prove payment integration. It replaces both boundaries it says it integrates, the payment gateway and the repository. So a pass shows only that the orchestration code behaves as expected **against doubles that encode its own assumptions**. It shows nothing about the real gateway (protocol, auth, error mapping, timeouts, idempotency) or the real persistence (schema, constraints, transactions, commit). It is a fidelity mismatch: a unit/orchestration test labeled as integration.

What this answer rests on: only the task description. I read no test code or implementation, and I ran no suite or engine. Every claim below is labeled with how it is known.

## Claims and their basis

| Claim | Basis | Evidence | Matters because |
| --- | --- | --- | --- |
| The test is named or presented as integration coverage of real payment integration | DECLARED | the test's name/claim as given in the context | Readers and CI dashboards will count it as integration assurance |
| The test replaces the payment gateway and the repository with doubles | OBSERVED (as stated in the context; I have not read the file myself) | the context's statement that both are mocked | These are exactly the two boundaries the integration claim is about |
| The test cannot prove gateway or persistence behavior | INFERRED | follows from the two facts above: no real boundary is crossed, so failures only a real collaborator produces cannot happen | This is the false green: the real gateway contract or the DB mapping can break and this test stays green |
| The test may still prove something useful about the unit (call sequencing, branching on gateway results, what gets saved) | INFERRED, unconfirmed | depends on its assertions, which I have not read | Keep it, reclassify it, don't delete it |
| Whether the doubles match the real collaborators (signatures, error types, declined/timeout responses, idempotency keys, return shapes) | UNKNOWN | needs the doubles compared with the real gateway client/SDK and the repository implementation | Doubles shaped by the caller can hide mismatches entirely |
| Whether **any other** test crosses the gateway or repository boundary for real (sandbox gateway, recorded contract, disposable DB) | UNKNOWN | needs a search of the suite and its markers | Decides whether integration is unprotected or just mislabeled here |
| Whether this test, or any real integration test, is selected and executed in CI, and on which revision | UNKNOWN | needs workflow files (declared) and provider runs with head SHA matching `git rev-parse HEAD` | A green CI badge cannot be tied to integration assurance without it |
| Whether the test currently passes | UNKNOWN | no run observed | Separate from the fidelity question; a pass would not change the conclusion above |

Along the exists → selected → executed → outcome → proven chain: a test targeting payment integration **exists** (declared). Selection, execution and outcome are **unknown**. "Proven", for the integration claim, is **not achievable by this test whatever its outcome**, because its environment is not faithful to the boundary that matters.

## What green does and does not prove

- **Can prove (if its assertions are meaningful):** given the gateway double's responses, the service makes the expected calls and persists the expected data through the repository interface.
- **Cannot prove:** that the real gateway accepts the requests (payload shape, auth, currency/amount encoding). It also cannot prove that real declines, timeouts, network errors or duplicate submissions are handled, that webhooks/callbacks reconcile, that the real repository writes and commits the rows, that constraints and transactions behave (for example, rollback when payment fails after a write), or that the doubles' signatures and errors match reality.

## What I would do next (in order, within audit boundaries)

1. **Read the test and its doubles next to the real collaborators.** Check the patch seam (does it patch the import path the module under test actually resolves?), whether `spec`/autospec is used, and whether the double's responses and errors match the real gateway client and repository. Also check what the test asserts: outcome, persisted state, the call contract, or only "called once" / no exception.
2. **Search for any test that crosses either boundary for real.** That means a sandbox/test-mode gateway, Pact or recorded contract tests, VCR-style cassettes, or a disposable database. Report which exist and at what level.
3. **Check what CI selects.** Look at workflow files for markers/paths that include or exclude integration tests (DECLARED), then at provider runs tied to HEAD by SHA when access is available.
4. **Run the suite safely** with `assertiva audit <project> --execute` (disposable copy, if the engine is installed) to get per-test outcomes. Its `TEST_FIDELITY_MISMATCH` candidate for this test, if raised, gets a CONFIRMED / CONTEXTUAL / FALSE_POSITIVE disposition after step 1. If the engine is not installed, run the runner in a copy outside the project and keep the command and exit code.
5. **If the test's own assertions look strong, settle it with a negative control** in a disposable copy. For example, break how the real gateway client maps a decline, or how the repository persists the payment status, and show that this test stays green. That turns the inferred false green into an observed one (a hand-made break, labeled as such, not engine mutation evidence).

## Recommendations (no changes to the project without approval)

- Rename or re-mark this test as a unit/orchestration test so it stops claiming integration. Keep it as a fast test.
- Add at least one test that crosses each boundary for real: the repository against a disposable local database (container or SQLite only if it matches the production engine's relevant semantics), and the gateway against its sandbox or a provider/consumer contract. Never point tests at shared, staging or production systems, and never use credentials not provided.
- Tighten the doubles (`autospec`, errors modeled from the real client) and add negative paths: decline, timeout, a duplicate idempotency key, and a payment failure after the persistence step, asserting the state afterwards.
- Make sure CI selects the real integration tests and that skips (missing sandbox credentials, missing DB) are visible rather than silently green.
- Any strengthened test should go through `assertiva improve` with a negative control or `--mutate` showing that the baseline misses a break the candidate detects. Applying it needs the user's explicit approval of the named change ids.

## Remaining unknowns

Whether the test passes, what it actually asserts, whether its doubles match the real contracts, whether any real-boundary test exists, and what CI runs on which revision. Each is settled by the steps above. None of them can turn this test into integration evidence.

No engine run was performed in this context, so no Assurance Report was produced.
