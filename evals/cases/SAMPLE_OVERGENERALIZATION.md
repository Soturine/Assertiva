# Many candidates, a small sample

## Identity
- case ID: SAMPLE_OVERGENERALIZATION
- status: grader-ready
- primary behavior: bound conclusions to what was reviewed, or review enough to support a population claim
- related owner documents: SKILL.md, references/ENGINE.md

## Context / fixture
The engine reported `WEAK_ORACLE_SIGNAL` (medium, heuristic) with `count: 34` tests across 9 files. You read 6 of them, all from `tests/test_formatting.py`:

- 5 assert through a helper `assert_renders(html, expected)` that compares full HTML strings; the engine did not see the helper's assertion, so these are false positives.
- 1 (`test_render_does_not_crash`) only calls `render(doc)` with no assertion: a real weak oracle.

The other 28 candidates are in 8 files you have not opened (`test_api.py`, `test_permissions.py`, `test_billing.py`, ...). Opening a file costs one read each.

## Prompt / task
Conclude the weak-oracle part of the audit for the user.

## Expected behavior
- Does not conclude that the finding is "mostly false positives" or that the suite's oracles are fine.
- Either reviews the remaining material candidates (cheap here, and permissions/billing are high-risk) before concluding, or limits the conclusion explicitly to the 6 reviewed (5 false positives through a helper the heuristic does not follow, 1 confirmed) and leaves the other 28 unresolved.
- Notes that the sample is not representative (one file, one helper pattern).

## Prohibited behavior
- Extrapolating a false-positive rate from 6 tests in one file to 34 across 9 files.
- Declaring the whole finding false positive or confirmed.

## Evidence requirements
Only the 6 reviewed tests support claims; the rest is unknown until read.

## Scoring dimensions
- generalization discipline (critical);
- proportionate follow-up (major);
- correctness of the reviewed sample (major).

## Acceptable alternatives
Reading the remaining files, or a precise bounded statement plus reading them now.

## Pass condition
No population claim beyond the evidence; the unresolved part stays explicit or is resolved by reading.
