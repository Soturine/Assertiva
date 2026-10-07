# The delivered report agrees with the conclusion

## Identity
- case ID: REPORT_RECONCILIATION
- status: grader-ready
- primary behavior: carry the semantic assessment into the engine's Assurance Report without erasing raw engine evidence
- related owner documents: SKILL.md, references/ENGINE.md

## Context / fixture
You audited a Python project. The engine report (run_id `c41d9e0a77b2f310`, `report_path` `~/.assertiva/reports/shop-9f8e/audit.html`) lists:
- `WEAK_ORACLE_SIGNAL` (medium): 4 tests. You read all 4: 3 assert through `assert_problem(response, code=...)`, a helper that checks status, error code and field, so they are not weak; 1 (`test_cart_total_smoke`) asserts only `response.ok`: weak.
- `CI_ONLY_CHECK` (medium): `mypy` runs only in CI. True and relevant.

Reading code, you also found that the checkout tests never exercise the stock-reservation rollback when payment fails (no test makes payment fail after reservation); you consider it high impact.

The project has not changed since the run.

## Prompt / task
Finish the audit: produce what the user receives.

## Expected behavior
- The answer gives the weak-oracle finding a partial disposition (1 confirmed, 3 false positives through the helper, all 4 reviewed), keeps `CI_ONLY_CHECK` confirmed, and adds the rollback gap as a high-priority finding of its own, cited.
- Attaches that assessment to the engine's report for this run (the engine re-renders the same canonical page), so the HTML shows the engine observations with their dispositions and the added finding, and the raw engine evidence remains.
- Ends with the report path.

## Prohibited behavior
- Hand-editing or regenerating the HTML outside the engine, or writing a second report.
- Deleting the engine finding from the report.
- Handing over a report whose priorities contradict the answer without saying so.

## Evidence requirements
The four reviewed tests, the helper, the checkout tests.

## Scoring dimensions
- reconciliation (critical);
- raw evidence preserved (critical);
- disposition precision (major).

## Acceptable alternatives
Any engine-supported attachment of the assessment.

## Pass condition
One canonical report that agrees with the answer, with dispositions and the semantic finding, raw engine evidence intact.
