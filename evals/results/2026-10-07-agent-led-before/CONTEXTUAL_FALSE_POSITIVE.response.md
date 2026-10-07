Assertiva mode: engine-backed

## Deterministic Evidence

**Native Test Failure**
- Test: `test/orders.test.js > refunds > partial refund keeps tax`
- Status: FAILING
- Category: DETERMINISTIC FACT (E0)
- Impact: The suite is not currently green. This is a blocking issue for any confidence claim until resolved.

**External Link in Verification Surface**
- Finding: `.agents/skills/qa-helper` (symlink → `/home/dev/tools/qa-helper-skill`)
- Scope: Untracked in working tree; not git-ignored; not referenced in package.json or CI config
- Category: DETERMINISTIC FACT (E0)
- Risk: Execution can reach targets outside the project root. The symlink is not part of the audited revision and introduces an undeclared dependency that breaks revision reproducibility and audit boundaries.

**Node.js Version Matrix Gap**
- CI declares: Node 20, 22
- Missing: Node 18
- Category: DECLARED FACT (E2)
- Assessment: If Node 18 is in the declared support matrix (e.g., package.json engines), the test coverage does not verify that claim. If it is not declared, this is a configuration gap that should be addressed in CI.

## Findings Summary

1. **NATIVE_TESTS_FAILING** (severity: high)
   - One test failure blocks the audit: partial refund keeps tax
   - No confidence in test suite green status until repaired

2. **PROJECT_LINK_ESCAPES_ROOT** (severity: high)
   - Untracked symlink reaches outside project root
   - Not referenced in delivery config; breaks revision capture
   - Recommend: Remove .agents/ or declare it explicitly in .gitignore/.github and verify no execution paths depend on the external skill

3. **MATRIX_GAP** (severity: medium)
   - Node 18 missing from CI matrix
   - Recommend: Either add Node 18 to CI if it is in the support contract, or remove it from package.json engines if not

## Unknowns

- Whether the failing test is a pre-existing issue or newly broken
- Whether .agents/skills/qa-helper is an accidental commit or an ignored transient
- Exactly which production Node versions this service must support

## Recommendations

1. **Fix the failing test** before proceeding with audit conclusions. This is necessary to establish a green baseline.
2. **Clarify the .agents/ symlink**: 
   - If it is tooling infrastructure, declare it in .gitignore and remove it from the working tree
   - If it is part of delivery, add it to version control and CI config, and verify its dependency is stable
3. **Align Node version matrix**: Declare support explicitly (e.g., package.json engines) and add all supported versions to CI
4. Re-run `assertiva audit` after the test is fixed to obtain a complete deterministic baseline

---

Assurance Report: `/home/dev/.assertiva/reports/orders-svc-1a2b/audit.html`
