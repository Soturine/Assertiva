# Is the "beats the matched null at the 99th percentile" claim supported?

**No.** The null is not matched:
- The real run searches **2000 agents × 30 generations** (about 60,000 agent-generations).
- Each null world searches **200 agents × 3 generations** (about 600), roughly **100× less search**.

The best of a larger search is higher by selection alone, even on pure noise. So the null distribution of "champion scores" sits too low, and the real champion's percentile against it is inflated. The 99th-percentile figure tells us at least as much about the budget gap as about the champion. Whether the champion beats a *budget-matched* null is **UNKNOWN**.

**The test** proves only that the report contains a number between 0 and 1. It would pass:
- for a percentile of 0.01 or 0.99;
- for a null with any budget;
- for a percentile computed against the wrong distribution.

It does not check the claim, and it does not check what "matched" means.

What this rests on: only the context I was given. I have the run and null budgets and the test's single assertion. I read no code and ran nothing.

## Findings, ranked by consequence

### 1. The null's search budget does not match the run's (high, INFERRED from the stated configuration)
- A selection null must reproduce the selection procedure: same population, same generations, same operators, same scoring. Only the signal (real versus null worlds) should differ.
- With 10× fewer agents and 10× fewer generations, the null champion is drawn from a much smaller search. Its expected maximum score is lower.
- The direction of the bias is known: it makes the real champion look better than it is. Its size is unknown without a matched run.
- The report calls this null "matched". That is a mislabel, and readers will take it as the controlling comparison.

### 2. The test checks the shape of the output, not the claim (high, OBSERVED from the assertion)
- `0 ≤ percentile ≤ 1` is a type and range check. It cannot fail because of a budget mismatch, a wrong comparison direction, too few null worlds, or a percentile computed against the wrong sample.
- It is acceptable as a smoke check. It is not evidence for the 99th-percentile statement.

### 3. Percentile resolution is unknown (medium, UNKNOWN)
- The context does not say how many null worlds were run. A 99th-percentile claim needs enough null samples to resolve the tail: with fewer than about 100 worlds, "99th" cannot even be distinguished from "best of the sample".
- It also needs an uncertainty interval. The number of worlds, and any seeds, should be reported.

## What is supported
- The champion scored above most of the cheap null champions. That is OBSERVED as reported, and only against a 600-agent-generation null.
- It is not a controlled claim of skill.

## Evidence that would settle it

1. **Rerun the null at the real budget**: 2000 agents × 30 generations per null world, with the same algorithm, hyperparameters and scoring as the run.
   - Use enough worlds to resolve the 99th percentile: at least a few hundred.
   - Report the percentile with a confidence interval and the seeds.
   - If that is too expensive, at minimum measure how the null champion's score grows with budget (for example at 600, 6,000 and 60,000) and state the extrapolation as an inference, not as a matched result.
2. **A test of the matching property.**
   - Assert that the null configuration equals the run's configuration on every search dimension: population, generations, operators, evaluation set.
   - Fail, or forbid the "matched" label, otherwise.
3. **A negative control.** Feed the reporting code a run whose champion was found on noise, with a budget-matched null. The percentile should come out near uniform, not near 0.99. Then show that the current mismatched null inflates it. This demonstrates the bias the test misses.
4. **A content oracle for the percentile.** On a small, hand-built set of null scores and a known champion score, assert the exact percentile, including ties and the comparison direction.

Until step 1 is done, report the result as: "beats a 100×-smaller-budget null at the 99th percentile; performance against a matched null is unknown".
