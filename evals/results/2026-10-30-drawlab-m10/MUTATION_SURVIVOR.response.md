# Surviving `>=` → `>` boundary mutant under high coverage

## Answer

The surviving mutant shows that **the tests that ran did not distinguish `>=` from `>` at this site**. Most likely no test feeds the exact boundary value and checks the result. High coverage does not contradict this. Coverage says the line executed, not that the boundary was checked. So this is a strong lead for a boundary-value gap. It is not yet a proven defect in protection: first you state the witness and rule out an equivalent or unreachable mutant.

What this answer rests on: only the task description. I did not see the mutation report, the mutated line, the code around it, the tests or the coverage report, and I ran nothing.

## What can be claimed, and how it is known

| Claim | Basis | Evidence | Notes |
| --- | --- | --- | --- |
| A mutant changing `>=` to `>` survived | OBSERVED as reported in the context. It is ENGINE_EXECUTED only if it came from `assertiva audit --execute --mutate`; EXTERNAL_UNVERIFIED if it is an ingested report | the mutation report / `survivor_sites` entry (not seen by me) | It applies only to the source revision and tests the run used. Whether that matches the current tree is unknown |
| Coverage of the affected code is high | OBSERVED as reported (metric kind, scope and exclusions unknown) | the coverage report (not seen) | Line coverage says the line ran. It does not say the `==` case was exercised, or that any assertion depends on that comparison |
| No executed test observed a difference between the original and the mutant | INFERRED from the survival | the mutation run | This holds for the tests that run selected, and only on that revision |
| The boundary case (input exactly at the threshold) is untested or unasserted | INFERRED, the most likely explanation, not confirmed | needs the tests read against the mutated line | Other explanations listed below |
| The survivor is a real protection gap | UNKNOWN until a witness is stated | see next steps | It could be an equivalent or immaterial mutant |
| Whether behavior at the boundary is *specified* (should exactly-at-threshold be included?) | UNKNOWN | requirement, spec, docstring, domain rule | Without a contract, a test that pins `>=` is a characterization test, not a contract test |

## Why it might not be a gap (to rule out before calling it one)

- **Equivalent mutant:** the equality case can't occur (for example, the value is always odd/even, already clamped, or an earlier branch handles `==`), or both branches produce the same observable result at equality.
- **Unreachable or immaterial:** the `==` input is not constructible through the public interface, or the difference has no consequence the contract cares about.
- **Run limitations:** the detecting test was not selected, was skipped, or the run did not complete. A partial or errored run never counts as evidence of protection or of its absence.

## What I would do next

1. **Read the mutated line and its context** (from `survivor_sites` or the report) and determine the witness. That means an input exactly at the threshold, what the original returns (`>=` → true branch), what the mutant returns (`>` → false branch), and whether the difference is observable at a public surface (return value, state, error, event).
2. **Read the tests that cover that line.** Do any use the boundary value? If they do, do they assert the outcome, or only that something did not raise? The common pattern is tests at `threshold - 1` and `threshold + 1`, or only far-from-boundary values, plus weak oracles.
3. **Find the contract for the boundary**: a requirement, spec, API doc or domain rule saying whether the threshold value is included. If none exists, the expected value is undetermined. Say so, and treat any new test as characterization (it pins current behavior, bugs included).
4. **Confirm the evidence's identity.** Check that the mutation run and the coverage report correspond to the audited revision and tests. If the report was external, rerun it through the engine (`assertiva audit <p> --execute --mutate <file>`) on the current state so the survivor is engine-executed and tied to this revision.
5. **If the survivor is real, strengthen through `assertiva improve`.** Add a test at the exact boundary (plus `±1` neighbors), with the expected value from the contract. Then run `--mutate <file>` on baseline and candidate: the evidence is that the baseline lets this mutant survive and the candidate kills it, not that the new test passes or raises coverage. Applying the change needs the user's explicit approval of the named change ids.

## What green and coverage prove here

- **Protected (likely):** behavior away from the threshold on both sides, to the extent the existing tests assert outcomes. This is not verified without reading them.
- **Not protected (likely):** the decision exactly at the threshold. An off-by-one at this boundary would pass the whole suite while high coverage stays unchanged.
- Coverage percentage and mutation score are diagnostics here, not quality scores.

## Remaining unknowns

The witness and whether the mutant is equivalent; the intended contract at the boundary; whether the mutation and coverage evidence match the current revision; the coverage metric kind and scope; and whether other mutants on the same line or function also survived. Steps 1–4 settle these. The engine's targeted mutation run needs the project's mutation tool to be installed, otherwise it is reported BLOCKED, never passed.

No engine run was performed in this context, so no Assurance Report was produced.
