# Assessment: Redundancy Finding — PickerApi24Test and PickerApi34Test

## Summary

The two tests have identical test bodies but **are not redundant**. They exercise different implementation branches: `PickerApi24Test` (@Config(sdk = [24])) runs the legacy intent path, while `PickerApi34Test` (@Config(sdk = [34])) runs the photo picker path. Deleting one would leave a code path untested.

## Finding Disposition

**Finding:** `REDUNDANCY_CANDIDATE` (2 tests with identical body)  
**Disposition:** `FALSE_POSITIVE`  
**Priority:** info  
**Rationale:** Same test body + different SDK configs = different execution paths. The engine's static analysis cannot see the runtime branching on `Build.VERSION.SDK_INT >= 33` in the implementation. Retiring either test would remove the only detector of defects in one of the two MediaPicker implementations.

**Evidence:**
- `src/test/kotlin/media/PickerApi24Test.kt::returnsSelectedUris` (@Config(sdk = [24])) → legacy intent path
- `src/test/kotlin/media/PickerApi34Test.kt::returnsSelectedUris` (@Config(sdk = [34])) → photo picker path
- `MediaPicker` branches on SDK >= 33; test body is identical but implementation differs

**Scope:** Both tests reviewed; both confirmed necessary.

## What Not to Do in Improve

Do not delete either test. Similarity alone is not evidence of redundancy. The Assertiva engine correctly flagged this as a candidate, but:

1. **Static analysis cannot see runtime branching** — The engine reads the test body identically; it does not execute with different SDK levels to observe which code paths activate.
2. **Per-test detection is unknown without mutation or negative controls** — A mutation report or targeted negative control (deliberately breaking the photo picker path, then the legacy path) would confirm each test detects what the other misses.
3. **The speed gain is negligible** — 0.8 seconds of 41 seconds (~2%) does not justify losing coverage of an entire code path.

## Recommendation

**Keep both tests.** This is an example of intentional matrix coverage: the test case is the same, but the environment varies to prove the code works across the supported range. This is not a weakness; it is verification surface that matters.

If speed is the concern, consider:
- Running the legacy and modern paths in a single parameterized test (@Parameterized, @ParameterizedTest with SDK levels as parameters).
- Profiling other tests for slowness; 41 seconds is reasonable for a library suite.

Do not use `assertiva improve` on this finding. There is nothing to improve; the test structure is correct.
