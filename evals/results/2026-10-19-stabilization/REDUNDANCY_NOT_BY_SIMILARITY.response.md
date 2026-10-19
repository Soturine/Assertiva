# Redundant tests: do not delete the pair

## Answer

Do not use `improve` to delete `PickerApi24Test::returnsSelectedUris` or `PickerApi34Test::returnsSelectedUris`. The audit's REDUNDANCY_CANDIDATE is a lexical match (same body, basis INFERRED). The two tests run under different SDK configurations (`@Config(sdk = [24])` and `@Config(sdk = [34])`), and `MediaPicker` branches on `Build.VERSION.SDK_INT >= 33`. So they likely exercise different code paths (legacy intent at 24, photo picker at 34). Deleting either one could remove the only check of one branch. Deleting them would also not make the suite meaningfully faster: together they take 0.8 s of 41 s, about 2%.

## What this rests on

- Only the audit excerpt, the two class declarations and the description of the `SDK_INT >= 33` branch. I did not read the test bodies, the `MediaPicker` source or the Gradle configuration.
- No run was made here. No mutation report exists, so no per-test kill data is available.
- No Assurance Report was produced in this context, so there is no assessment file to attach.

## Findings

1. **The redundancy claim does not hold as stated (INFERRED).** The engine compares bodies and boundaries, but it does not read `@Config`. Under Robolectric the SDK level is part of the test's configuration, so identical bodies can still prove different behavior. Disposition for the pair: `FALSE_POSITIVE` for the redundancy claim, or `UNRESOLVED` until a negative control or per-test kill data settles it. I would not record `CONFIRMED`.
2. **Retirement is not supported by the evidence.** Similarity alone proves nothing. The engine's own guidance is to show that each test detects something the other misses, and `mutation_sensitivity` is unknown without a mutation report. Retiring either test now would be a guess.
3. **The speed goal is not served by this candidate.** Even removing both tests saves at most about 0.8 s of 41 s. Where the 40 s goes is unknown from this context. A plausible hypothesis, to check and not a finding, is that per-SDK Robolectric setup dominates.

## Decision on `improve`

- No `improve` run that deletes or retires these tests. The engine would also need a mutation report or negative control to qualify such a retirement, and none exists.
- If the user wants to test the duplicate claim, the cheap check is a negative control in a disposable copy: break the legacy (pre-33) path and see whether `PickerApi24Test` fails while `PickerApi34Test` stays green. The reverse check covers the photo-picker path. Both tests should be kept if each one fails for its own branch.
- If the user wants a faster suite, first measure. Run `assertiva audit <project> --execute` in a disposable copy, then read per-test durations (JUnit XML or the Gradle test report). Note that the Android SDK cannot be provisioned by the engine, so that run may be BLOCKED on this machine. That would be reported as a limitation, not a failure.

## Unknown

- Whether the two test bodies are identical beyond what the excerpt says.
- Whether other tests in the suite are redundant. Only this one candidate was read.
- Where the 41 s is spent, and whether CI runs this suite on HEAD.
- The mutation sensitivity of both tests.

## Recommendation to the user

Keep both tests. Do not run `improve` to delete duplicates on this evidence. Ask for a negative control on each SDK branch, or a mutation report, before any retirement is considered. For speed, get per-test timings first; the two tests are not the place to look.
