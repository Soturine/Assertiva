# Test quality: what a passing test can and cannot prove

## Contents
- Oracles and observation surfaces
- Test doubles and seams
- Harness fidelity
- Data, fixtures and order
- Negative paths and error contracts
- Coverage
- Mutation and negative controls
- Parameterized, property and fuzz tests
- UI and browser tests
- Weak-test signals

Each section is a set of questions that lead to evidence. Use the ones the question needs.

## Oracles and observation surfaces

A test is as strong as what it observes. Ask, for each important behavior: what would have to break for this test to fail?

- Map assertions to behavior claims. Status, returned value, persisted state, emitted event, call on a collaborator, rendered output, accessibility tree and visual output are different surfaces; one does not prove another.
- Truthiness, `is not None`, "no exception", a 200 status or "called once" usually let wrong values pass. A helper or custom matcher may be strong even when the test body looks empty — read it before judging.
- Judge the contract, not the count of asserts. "Must not raise" or "must not touch X" can be the whole contract, and a double whose side effect fails the test on a forbidden call is a real oracle; a test with ten `is not None` checks can still prove nothing. A negative test that checks the error but not the state afterwards misses partial writes. When the contract cannot be read from the test, its name and the code under test, the item is unresolved, not weak.
- An oracle derived from the code under test (same formula, same fixture generator, a snapshot accepted without review) shares its bugs.
- Authority: where does the expected value come from — a requirement, a contract, a hand-computed example, or the current output?

## Test doubles and seams

- Is the double placed at the seam the code really uses (the import path the module under test resolves, the injected instance)? A patch at the wrong seam passes without exercising anything.
- Does the double behave like the real collaborator: same signature, errors, edge values, ordering, timing? Doubles written to satisfy the caller encode the caller's assumptions; compare them with the real implementation or its contract.
- A test named or marked as integration that replaces the dependency it claims to integrate proves the unit, not the integration. Check whether any test crosses that boundary for real.
- `spec`/autospec, contract tests, recorded fixtures and virtual services narrow the gap; say which exist.

## Harness fidelity

Never infer strength from a class name, file suffix, marker or folder. Record what actually runs: process, transport (in-process client vs real HTTP), persistence (in-memory vs real engine, transaction rolled back vs committed), dependency versions, UI runtime, OS/browser/runtime matrix and isolation. A transaction-per-test harness never proves commit, constraint-deferral or concurrency behavior.

## Data, fixtures and order

- Shared or session-scoped fixtures, module globals, seeded databases and caches can leak state; a test that passes only after another test is order-dependent.
- Generated data (Faker, factories) without a fixed seed makes failures irreproducible; generated data that never hits boundaries proves only the happy middle.
- Fixtures that silently skip (missing service, missing env var) turn whole areas into non-evidence: check what was skipped, locally and in CI.

## Negative paths and error contracts

Invalid input, rejection, failure and recovery are part of the contract.

- Does the test assert the specific error (type, code, field/path, structured context, protocol status) or only that something failed? `pytest.raises(Exception)` and a bare 4xx are weak.
- After a rejection, is the state checked (no partial write, no forbidden side effect, rollback)? An assertion after rejection is not rollback proof by itself.
- Async: are created tasks awaited so their failures can fail the test?
- Prefer stable structured fields over message text, unless the wording itself is the contract.

## Coverage

Coverage says what executed, not what was checked. Keep metric kind (line, branch, condition, function), numerator, denominator, scope and exclusions; a percentage over a changed denominator is not comparable. High coverage with weak oracles is a classic false green. Uncovered branches are leads: are they error handling, recovery, a state nobody tests?

## Mutation and negative controls

Mutation testing (or a deliberate negative control: a hand-made behavior-breaking edit in a disposable copy) asks whether tests detect a real defect. Useful on boundaries, conditionals, arithmetic, critical rules and code with high coverage but doubtful oracles. A surviving mutant may be equivalent, unreachable or immaterial: interpret it, do not optimize the score. Targeted mutation is often enough. Mutation reports apply only to the source revision they were produced from.

## Parameterized, property and fuzz tests

- Do not collapse a parameterized definition into one result: each case is its own evidence (definition → materialization → invocation → attempt).
- Do the cases cover boundaries and invalid inputs, or variations of one happy path?
- Property-based and fuzz evidence needs its seed or replay token, run budget and minimized counterexample; randomized success without replay data is weak diagnostic evidence.

## UI and browser tests

- Prefer locators and assertions tied to the user contract: role, accessible name, label, state. Native semantics first; ARIA supplements them and is not added for test convenience. Explicit test ids are legitimate when user-facing semantics are ambiguous.
- Positional selectors, deep CSS chains and absolute XPath couple tests to incidental structure, unless that structure is the contract.
- Role/name/state, keyboard/focus, pointer interaction, visual output, storage/network state and backend effects are separate surfaces; a keyboard path can break while the pointer path passes.
- Semantic and visual snapshots catch different regressions; neither replaces the other. Snapshot updates need intent and provenance.
- An automated accessibility scan with zero violations is partial evidence, not accessibility.
- Retries keep the first failure; a raised timeout is not a root-cause fix unless the latency contract changed.

## Effectiveness across languages

Judge a test by what it can fail for, the same way in every language: `status == 400` in pytest, `expect(res.status).toBe(400)` and `assertEquals(400, response.status)` are the same weak oracle when the contract also fixes the error body. Questions that settle the engine's candidates:
- **False green** — can this test fail when the behavior breaks? Read the condition, the caught exception or the unawaited promise; when it is unclear and the behavior matters, break the behavior in a copy (a negative control) and see.
- **Fidelity** — a test named or placed as integration/E2E whose every boundary is a double proves the code against the doubles. Keep it as a fast test and say so; the integration claim needs one check that crosses the real boundary (a disposable service, a real browser, a device).
- **Redundancy** — two tests with the same body at the same level and component are a review lead; other platforms, configurations or matrices can still make them distinct. Only per-test detection evidence (killing tests in a mutation report, a negative control) shows overlap without loss; never consolidate or retire on similarity.
- **Intentionally simple tests** — a smoke check whose contract is "does not raise" or "the page renders" is not weak; say so in the disposition.

## Weak-test signals

Signals to investigate, not verdicts: no effective assertion; assertion roulette; one test asserting everything; mystery guest (hidden file, network, clock); oversized fixtures; sleeps without a condition; excessive mocking; assertions on implementation details; giant snapshots; semantic duplicates; quarantined or ignored failures; retry dependence; expected values computed by the code under test. Connect each to a concrete risk before recommending a change.
