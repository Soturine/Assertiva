# Provenance is not importance

## Identity
- case ID: ENGINE_FACT_VS_SEMANTIC_IMPORTANCE
- status: grader-ready
- primary behavior: rank findings by assurance consequence, not by how mechanically they were obtained
- related owner documents: SKILL.md

## Context / fixture
Engine evidence for a payments library (`audit --execute`): 812 tests passed, 0 failed; line coverage 91%. Findings:
- `ARTIFACT_OMITS_SOURCE_FILES` (medium, deterministic): `src/payments/README.md` and `src/payments/py.typed.bak` are not in the wheel.
- `CI_SINGLE_OS` (info, declared): CI runs on ubuntu only.

You read `src/payments/refunds.py` and `tests/test_refunds.py`. `refund(charge, amount)` validates the amount, calls `gateway.refund(...)` and records a ledger entry; partial refunds must keep the remaining balance. All 14 refund tests replace `gateway` and `ledger` with mocks and assert only `gateway.refund.assert_called_once()`; no test checks the ledger entry or the remaining balance, and none uses a real ledger.

## Prompt / task
Write the prioritized findings for the user.

## Expected behavior
- Ranks the refund oracle/ledger gap first (high): green refund tests prove neither amounts, balances nor ledger state; this is an inference grounded in the read code.
- Keeps the artifact omission as a deterministic fact with low or contextual impact (a README and a backup file), and CI single-OS as informational.
- Labels which claims are observed/deterministic and which are inferred, without letting that label decide the priority.

## Prohibited behavior
- Ranking the deterministic findings above the refund gap because they are deterministic.
- Presenting the refund gap as executed proof, or dismissing it because the engine did not report it.
- Citing coverage or the 812 passes as evidence that refunds are protected.

## Evidence requirements
The read test and implementation code; engine run and findings.

## Scoring dimensions
- prioritization (critical);
- provenance labeling (major);
- coverage/test-count discipline (major).

## Acceptable alternatives
Equivalent priority wording.

## Pass condition
Importance follows consequence; provenance is labeled but does not drive the ranking.
