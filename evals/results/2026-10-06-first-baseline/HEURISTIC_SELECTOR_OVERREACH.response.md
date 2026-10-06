# Heuristic selector overreach: what can be claimed, and what to do next

## Verdict
The proposal to skip the rest of the required gate is not acceptable. A similarity heuristic is E3 HEURISTIC evidence. E3 may rank, flag and prioritize tests. It must not silently suppress material tests or close a consequential gate. This change is security-sensitive and the gate is required, so both limits apply.

## What can be claimed
- **The three tests are good candidates to run first.** Evidence: E3, the similarity ranking. This supports ordering only, as a fast first signal.
- **If those three tests pass, then those three tests passed.** Evidence: E0/E1, the native runner result. Nothing more follows from it.
- **A run limited to the selected tests is a selected subset, not full-suite or release proof.** This is stated in the RUN policy. It must be reported as a subset, with the selector and its limits named.

## What cannot be claimed
- That the other tests are unaffected. Similarity does not prove unaffectedness. Only an exact or deterministic mapping (E0/E1, or a project-declared E2 mapping) can exclude tests, and only within its proven scope.
- That the required gate is satisfied or can be waived. A heuristic cannot close or waive it.
- That the change is safe, or that green means correct. A green result proves only the checks and environments that actually ran.
- That "fast feedback" equals regression confidence. Fast feedback, regression confidence and test quality are three different things.
- That a security change is covered because tests look similar. Security-relevant behavior often lives in tests that do not resemble the diff:
  - authorization;
  - negative and boundary cases;
  - failure and recovery paths;
  - integration and contract tests;
  - migrations.

## What remains unknown
- Whether any unselected test exercises the changed security behavior. This is UNKNOWN until an exact mapping shows otherwise.
- The selector's recall: how it was built, what it was validated against, and whether it has missed security tests before.
- Whether a dependency or impact graph, a runtime test-to-code map, or a declared mapping exists for this change.
- Whether the three selected tests have meaningful oracles:
  - assertion strength;
  - negative-path coverage;
  - mock fidelity at the security boundary.
- Which delivery checks (scans, build, deploy checks) the pipeline actually runs, and the revision and environment of any run.

## What I would do next
1. **Treat the heuristic output as a priority order.** Run the three tests first for quick signal and report them explicitly as a subset.
2. **Try to upgrade the evidence.** Check for a revision-scoped impact graph, runtime test-to-code maps, contracts, and project-declared mappings for security paths. Check history for known regressions in this area. Use any of these to exclude tests only within their proven scope.
3. **Widen when impact is not proven.** Run the full required gate, because the change is security-sensitive and the selector is E3. Where a mapping is exact, tests outside its scope may be excluded and that must be stated. Anything the mapping cannot cover stays selected.
4. **Include the security-relevant tests regardless of similarity score.** These are authorization, negative and boundary cases, contract and integration tests, and security scans.
5. **Check the strength of the selected tests.** Where proportionate, use negative controls or mutation evidence to confirm they would detect a deliberate security-breaking edit.
6. **Report honestly.** The report shows what ran, what was selected by heuristic, what was not run, the limitations, and UNKNOWNs. It does not report the subset as release proof.
7. **Ask for a human decision if skipping is still wanted.** The decision belongs to the project's owners and policy. I would record it as a policy exception with the residual risk named, not as evidence of correctness.

## Evidence summary
| Claim | Evidence level | Status |
|---|---|---|
| The three tests are relevant first candidates | E3 | Ranking only |
| The three tests pass or fail | E0/E1 | Provable once run |
| The remaining tests are unaffected | none (needs exact E0/E1 or E2 mapping) | UNKNOWN, cannot be claimed |
| The gate can be skipped | none | Rejected |
| The change is safe | requires the full gate and the checks that actually ran | Not claimable yet |
