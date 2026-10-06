# User Experience and Reporting

Assertiva exposes two user-facing workflows:

```text
assertiva audit
assertiva improve
```

Everything else is internal orchestration, adapter behavior, or an advanced implementation detail.

## Audit

`audit` inspects the project, executes only permitted verification work, measures evidence and reports gaps. It never changes project files.

It may inspect tests, coverage, hooks, CI/CD, build/package checks, validation/error paths, test composition, fixtures, mocks, browser evidence, security/static checks and other verification sources discovered through adapters.

The result contains:
- current test and verification inventory;
- observed execution/results;
- coverage and other available metrics;
- weak or shallow evidence;
- missing behaviors and verification gaps;
- CI/local/deployment parity gaps;
- recommended changes;
- explicit unknowns and limitations.

Recommendations are proposals, not changes already present in the project.

## Improve

`improve` performs the audit first, creates candidate changes in an isolated workspace, verifies the candidate, compares it with the baseline, and presents the result before touching the original project.

The user sees one simple flow. Candidate qualification includes **test-the-tests**: the candidate suite is challenged with available mutation/negative-control evidence, original regression evidence, coverage/oracle analysis, pipeline-equivalent checks and, when explicitly authorized and safe, an ephemeral non-production preview deployment.

The user sees one simple flow:

```text
audit current state
        ↓
build candidate outside the project
        ↓
verify candidate
        ↓
show before vs candidate
        ↓
ask for approval
        ↓
apply only when approved
        ↓
verify applied result
```

The isolation mechanism is intentionally hidden from ordinary UX. It may use a temporary workspace or Git worktree internally, but users should not need to learn a separate "sandbox mode".

Candidate removals are conservative. Assertiva may recommend retirement or consolidation and may evaluate that change only inside the isolated candidate, but the original project test remains active until explicit human approval. Original tests are not commented out in active source files by default; baseline revision/fingerprint plus side-by-side diff preserves them more safely.

Candidate qualification is defined in [Candidate Qualification and Test-the-Tests](CANDIDATE_QUALIFICATION_AND_TEST_THE_TESTS.md).

Before applying, Assertiva must detect stale source changes and refuse unsafe blind overwrite. Application should be patch/change-set based rather than replacing newer user work.

## Internal write policy

The runtime, not only the prompt, enforces write boundaries.

- `audit`: project files are read-only.
- `improve`: candidate writes are isolated from the original project.
- approved application: only the approved candidate change set may modify the project.

Read-only analysis artifacts and reports should default to Assertiva-owned storage outside the audited repository so an audit does not dirty the working tree.

Project boundaries are part of the write policy: links are entries identified by their target and never followed, content outside the project root is never copied in as project material, and an approved change is refused if its path traverses outside the project, passes through a linked directory, introduces a link leaving the project, or collides with an existing path by case only.

## Assurance Report

Assertiva produces one responsive HTML report. The same report model adapts to the workflow.

For audit:

```text
CURRENT
+ FINDINGS
+ RECOMMENDATIONS
+ REMAINING UNKNOWNS
```

For improve:

```text
BASELINE
vs
CANDIDATE
+ CHANGE SET
+ EVIDENCE DELTA
+ REMAINING GAPS
```

After approval/application:

```text
BASELINE
vs
CANDIDATE
vs
APPLIED
+ POST-APPLY VERIFICATION
```

Never describe candidate results as already present in the project.

## Visual design

The HTML report should be polished, calm, responsive and understandable without reading raw logs.

Use:
- a concise project/revision header;
- clear status chips for observed, inferred, unknown and blocked evidence;
- summary cards for the most important metrics;
- before/candidate/applied comparisons;
- accessible charts with accompanying text/table equivalents;
- filters for severity, evidence type, runner, verification kind and status;
- expandable findings with evidence, provenance and limitations;
- a change-set view for added/modified/removal-candidate tests;
- a verification-surface view for local/hooks/CI/build/deploy checks;
- an "What does green prove?" section;
- an "Evidence Delta" section;
- links/references to raw artifacts without flooding the main page;
- light and dark theme support;
- keyboard navigation and semantic HTML.

Avoid visual noise, vanity dashboards and invented composite quality scores.

## Recommended report sections

1. Executive summary
2. Current / Candidate / Applied comparison
3. Test inventory
4. Outcomes and stability
5. Coverage
6. Assertion and oracle quality
7. Negative-path and validation evidence
8. Test composition/materialization
9. Fidelity and integration evidence
10. Verification surface
11. CI/CD and delivery parity
12. Mutation / negative-control evidence when available
13. Performance and runtime cost
14. Findings and priorities
15. Proposed/applied change set
16. Evidence Delta
17. What green proves now
18. Remaining gaps and unknowns
19. Environment, revision, adapters and provenance
20. Raw artifact references

## Metric discipline

The report distinguishes measured, candidate-measured, inferred and unknown values.

Good:

```text
Branch coverage
Baseline: 67.4% observed
Candidate: 78.8% observed in isolated verification
```

Bad:

```text
Projected quality score: 92/100
```

Counts should distinguish test declarations, materializations, invocations and attempts when those dimensions are available.

A decrease in test count is not automatically negative; an increase is not automatically positive. The report emphasizes evidence gained, lost or still missing.

## Evidence Delta

Instead of one magic score, summarize:

- improved evidence;
- unchanged evidence;
- regressed evidence;
- still unknown evidence.

This makes the effect of proposed changes understandable without pretending heterogeneous signals are one number.

## What does green prove?

Every report should end with a bounded claim such as:

```text
Observed
- selected unit and integration evidence passed
- package installed and startup check passed

Not evidenced
- production-like database behavior
- two configured browser targets
- rollback under concurrent writes
```

The purpose is not to make green look stronger. It is to make its meaning explicit.
