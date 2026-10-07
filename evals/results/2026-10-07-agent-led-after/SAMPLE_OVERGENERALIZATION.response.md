# Weak Oracle Signal: Audit Conclusion

## Summary

The engine reported 34 tests across 9 files with `WEAK_ORACLE_SIGNAL`. Of the reviewed sample:

- **5 tests** (all in `tests/test_formatting.py`): false positives. These assert through `assert_renders(html, expected)`, which performs full HTML string comparison. The engine's static analysis did not detect the helper's assertion, yielding false positives.
- **1 test** (`test_render_does_not_crash`): confirmed weak oracle. Calls `render(doc)` with no assertion.
- **28 tests** across 8 remaining files: unknown without review.

## What we know

The sample of 6 reviewed tests shows that:
1. Weak-oracle heuristic signals have false positives when assertions are delegated to helpers the engine cannot see.
2. At least one real weak oracle exists: a test that exercises code but makes no verifiable claim about its behavior.

## What remains unknown

The remaining 28 candidates in `test_api.py`, `test_permissions.py`, `test_billing.py` and 5 other files have not been examined. They may fall into any of three categories:
- False positives (helpers, custom matchers, or assertion patterns the engine missed)
- Real weak oracles (tests with no meaningful assertion)
- Actual code-level issues beyond the heuristic's scope

## Recommendation

To conclude this finding:
1. Review the remaining 28 test candidates across the 8 files (one file per read, or batch where feasible) to classify them as false positives or confirmed weak oracles.
2. For each confirmed weak oracle, check whether the test's lack of assertion reflects a gap in behavior coverage or is intentional (e.g., a smoke test documenting that code does not crash).
3. Prioritize the confirmed weak oracle in `test_render_does_not_crash` if strengthening test assertions is the goal.

The heuristic alone cannot settle whether the full set poses a material risk to assurance; that depends on the tests that remain unreviewed.
