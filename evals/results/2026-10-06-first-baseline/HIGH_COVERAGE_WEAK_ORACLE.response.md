# High coverage, weak oracle: what can be claimed and next steps

## Situation
The suite reports 98% line coverage. The API tests assert only HTTP 200. Persistence and business invariants can fail silently. This is an AUDIT situation: inspect and measure, and do not modify the project.

## What CAN be claimed
| Claim | Evidence | Level |
|---|---|---|
| The suite executes about 98% of lines, under the tool's scope and exclusions. | The coverage report, which is a native tool artifact. | E0, or E1 if parsed. |
| The API endpoints return HTTP 200 for the inputs the tests use. | The test results and the 200 assertions. | E0. |
| The status-code observation surface is covered. | The assertions themselves. | E0. |
| The tests are weak against persistence and invariant regressions. This is a finding, not a proof of a bug. | The assertion inspection (only 200 is checked) is deterministic. The conclusion that the oracle is weak is a heuristic (E3) until it is confirmed with negative controls. | E3, confirmable to E0. |

Coverage and test count are diagnostics, not proof. Line coverage shows that code ran. It does not show that anything was checked.

## What CANNOT be claimed
- Correctness, regression safety, or "refactor ready". A green suite plus 98% line coverage does not make a refactor safe.
- That persistence works, that business invariants hold, or that errors, rollback and authorization behave correctly. No observation surface checks these: there are no database state, response body, side-effect or call assertions.
- That branch, condition or function coverage is high. Line coverage does not imply them.
- That 98% means 98% of behavior is protected. Behavior-slice protection is unknown or weak, so the readiness is NOT_READY or UNKNOWN for consequential refactoring.
- That a green pipeline proves more than what ran. It proves only the checks and environments that actually executed.
- That the tests detect defects. That is unproven without mutation or negative-control evidence.

## Unknowns (reported as UNKNOWN, not guessed)
- The coverage metric kind, denominator, exclusions and tool version, and whether it is aggregate or per-test.
- The harness fidelity: whether the API tests hit a real persistence layer or a mock or fake, and whether the persistence boundary is mocked away.
- Whether any other tests (unit, integration, contract) assert the invariants elsewhere.
- Whether there are negative, boundary, failure, concurrency or authorization tests.
- What CI actually runs, compared with the checks that exist, including skips, retries, filters and matrix.
- Flakiness, retry-masking, and the exact revision and environment of the coverage run.
- Whether production defects have already slipped through. Git history and known regressions are available as evidence.

## What I would do next
1. **Audit without writing.** Run `assertiva audit`. Read the coverage report and keep the metric kinds separate. Gather the test results, the CI config and the harness fidelity. Map each endpoint's behavior claim to its observation surface. Classify the assertions: status only, body, persistence, side effects. Record the persistence seam (real DB, transaction, doubles).
2. **Test the safety net with deterministic evidence.** Use deliberate negative controls. Examples: skip the DB write, drop a field, break an invariant, return 200 with a wrong body. Run each in a disposable copy and check whether the tests claiming that behavior fail. If a mutation tool exists, ingest its report, since Assertiva ingests rather than mutates. Surviving mutants and negative controls that stay green are the strongest evidence of a weak oracle (E0/E1).
3. **Rank the gaps.** For each behavior, mark it protected, weakly protected, or unprotected. Prioritize the persistence and business invariants and the failure paths. Findings from heuristics (E3/E4) rank and propose but do not close gates.
4. **IMPROVE, only if the human wants it.** Build candidate tests outside the project. They would assert response bodies and structured error contracts, and check persisted state through an independent read. They would also cover negative, boundary, rollback and authorization paths. Keep the originals as immutable baseline. Qualify the candidate with the negative controls and coverage deltas. Do not trust new tests just because they pass, and do not treat a higher test count as an improvement. Report BASELINE vs CANDIDATE as improved, unchanged, regressed or unknown, without a single score. Never pass `--approve` myself. Approval belongs to the human, and the stale-source guard applies.
5. **Before any refactor.** Build a safety matrix and classify readiness. Do not weaken expectations to make things pass.

## What green proves
It proves that the executed code paths ran without crashing and that the endpoints answered 200 in the tested scenarios. It does not prove that data was persisted correctly, that invariants hold, or that wrong behavior would be detected.
