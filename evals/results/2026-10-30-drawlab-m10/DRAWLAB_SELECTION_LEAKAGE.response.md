# Selection leakage: what can be claimed about the agent and the test

**About the agent:** nothing prospective. The score on contests 2800–3000 is in-sample twice over:
- the search ran on contests 1–3000, which include 2800–3000;
- the best agent was *chosen* by its score on 2800–3000.

So that score is a selection statistic, biased upward by construction (winner's curse), not evidence of future performance. Truly prospective evidence would need contest 3001 or later, and contest 3001 has not been drawn. Whether the agent has any real predictive edge is **UNKNOWN**. No evidence for it exists yet.

**About the test:** it is green and it asserts the mislabel. `report.label == "PROSPECTIVE_EVIDENCE"` pins the incorrect claim in place. The green proves that the report *says* "prospective"; it does not prove that the evidence is. A fix that corrected the label would turn the suite red.

What this rests on: only the context I was given. I have the search range, the selection range, the label, the test assertion, the green suite and the fact that 3001 is undrawn. I read no code and ran nothing.

## Findings, ranked by consequence

### 1. The "prospective" label is false (high, INFERRED from the stated design)
- "Prospective" requires the evaluation data to be unseen by every decision that produced the agent. Here, contests 2800–3000 were seen by:
  - the search, since they fall inside 1–3000;
  - the selection, which picked the agent by its score on exactly that range.
- Picking the best of many candidates on a range guarantees a high score on that range even when no candidate has any skill. For draws that are presumably random (a fair lottery), that is the expected outcome.
- The right label for this number is something like in-sample / selection score / retrospective. It should carry no claim of generalization.

### 2. The test protects the false claim (high, OBSERVED from the assertion + INFERRED meaning)
- The oracle is the label string, not a property of the evaluation. For example, it does not check that the evaluation contests are disjoint from the search and selection contests, or that they postdate the agent's freeze time.
- So the test cannot fail when leakage happens. It fails only when someone corrects the label.
- This is a false green with an inverted oracle: it encodes the defect as the expected behavior.

### 3. The green suite says nothing about the agent's quality (medium, OBSERVED + INFERRED)
- The suite being green proves that code paths run and that the label matches. It does not prove that the agent beats chance on unseen draws.
- No test or report in the context provides an out-of-sample measurement, or compares the agent with a null baseline of best-of-N on random data.

## What can honestly be claimed now

| Claim | Status |
| --- | --- |
| The agent scored X on 2800–3000 | OBSERVED (in-sample, post-selection) |
| That score estimates future performance | not supported; biased upward by selection |
| The agent has predictive skill on future draws | UNKNOWN: no out-of-sample data exists (3001 undrawn) |
| The report labels its evidence correctly | no, by the definition of prospective (INFERRED) |
| The test verifies evidence provenance | no: it checks a string |

## Evidence that would settle it

1. **Real prospective evaluation.**
   - Freeze the agent now: a code and parameter hash, and a timestamp recorded before contest 3001 is drawn.
   - Evaluate it only on contests drawn after the freeze.
   - Only those results may be labelled prospective. With a few draws they will be weak evidence, so state the number of draws and the uncertainty.
2. **Selection-aware baseline.** Run the same search and selection procedure on shuffled or simulated random draws, many times. This gives the null distribution of the "best agent's score". Compare the real score with it. If the real score is typical of the null, the selection alone explains it.
3. **Honest retrospective split, if one is wanted before 3001.**
   - Search on 1–2599, select on 2600–2799, and evaluate once on 2800–3000, which neither step touched.
   - Label the result "held-out retrospective", not prospective.
4. **A test that checks the property, not the string.**
   - Assert that the evaluation contest set is disjoint from the search and selection sets.
   - Assert that a `PROSPECTIVE_EVIDENCE` label requires every evaluation contest to have been drawn after the agent's freeze time.
   - As a negative control, build a report whose evaluation range overlaps selection and require that it is *not* labelled prospective. The current code and test would fail that control.

I would recommend changing the label and the test together. The current expectation of `PROSPECTIVE_EVIDENCE` documents the defect, so it should not be kept as a regression baseline.
