# Test fidelity and oracle calibration — source tree versus installed artifact

## Identity
- case ID: ASSERTIVA_SOURCE_TREE_AND_ORACLE_FALSE_GREEN
- status: grader-ready
- primary behavior: distinguish tests of the intended source from stale installed packages; adjudicate false-green and false-positive oracle signals
- related owner documents: SKILL.md, references/ENGINE.md, references/TEST_QUALITY.md, research/2026-10-29-derivanta-engine-cross-dogfood.md

## Context / fixture
A Python project uses `src/pkga/`, tests import `pkga`, and a previous, non-editable copy is installed in site-packages. The developer changes `src/pkga/logic.py` to introduce a regression; a targeted test suite remains green because Python imports the installed package. In a clean environment without installation, collection fails with `ModuleNotFoundError`. A corrected configuration puts `src/` on the test import path and the mutation is killed. Another project intentionally tests the installed wheel and should keep doing so — but that is a *separate verification surface*.

A controlled audit fixture contains `assert set() <= {1,2}`, a test patching the symbol under test, a test whose imported helper performs real assertions, a no-raise validation contract and `f(x) == f(x)` to check determinism. Assertiva 0.9.0 missed the empty subset and self-patching patterns, but nominated the imported helper and no-raise tests as weak.

## Prompt / task
"Explain what the green suite proves, whether the tested revision equals the target source tree, and which of the five oracle patterns are genuinely weak or require context. Recommend precise improvements and tests for Assertiva."

## Expected behavior
- Identify source/install mismatch as a concrete false-green risk; require observed import origins and recorded revision before claiming source-tree assurance.
- Separate source-tree testing from explicit installed-artifact qualification; neither replaces the other.
- Detect empty left subset as vacuous and self-patching of the subject as suspicious; use positive/negative controls before generalizing.
- Recognize imported helper assertions and contracted no-raise checks as potentially strong; distinguish repeated-call determinism from literal self-equality.
- Preserve legitimate warnings for other truly assertion-free or mocked-away tests.
- Report original runs, negative controls and mutation evidence according to who executed them.

## Prohibited behavior
- Conclude that any pytest PASS proves changed local source behavior.
- Pretend that an Assertiva result included the developer's manual mutation when it did not.
- Brand every no-assertion test, every mock, or every repeated function call as definitely defective.
- Auto-suppress all weak-oracle signals.
- Attribute the testing configuration defect to Assertiva's implementation rather than the missing guard/provenance signal.

## Evidence requirements
Import origins in both environments, exact source revision and installed package identity, failing/passing negative control, test source and helper implementation, documentation of no-raise contract and assessment dispositions.

## Scoring dimensions
- target artifact/revision fidelity (critical)
- accurate vacuous-oracle and self-patching identification (critical)
- contextual false-positive adjudication without blanket suppression (critical)
- correct instrument/provenance attribution and actionable test plan (major)

## Acceptable alternatives
Use controlled `PYTHONPATH`, editable source install with verified origin, `--import-mode`, explicit source paths or equivalent mechanisms; any implementation is acceptable if provenance and meaningful failure detection are demonstrated.

## Pass condition
All critical dimensions score 2 and the major dimension scores at least 1. Grader-ready case only; no runtime support or passing eval implied.
