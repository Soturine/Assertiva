# Candidate Qualification and Test-the-Tests

`improve` should not merely generate more tests. It should **qualify the candidate test suite** and show whether the evidence actually became stronger.

This is an internal phase of `assertiva improve`, not a third user-facing mode.

## Flow

```text
immutable baseline
      ↓
candidate changes in isolated workspace
      ↓
run candidate tests
      ↓
rerun original regression evidence
      ↓
measure coverage / oracle / negative-path / fidelity changes
      ↓
challenge the tests
      ↓
run pipeline-equivalent checks
      ↓
build/package/startup
      ↓
optional non-production preview deployment
      ↓
compare baseline vs candidate
      ↓
human review
      ↓
apply approved change set
      ↓
post-apply verification
```

## Test the tests

Candidate tests should be challenged where proportionate, not trusted merely because they pass.

Useful evidence includes:
- mutation testing through ecosystem-native tools;
- deliberate negative controls / intentionally broken candidate implementations;
- historical regression replay;
- contract violations;
- property/metamorphic perturbations;
- structural UI changes that should not alter behavior;
- fault injection for timeout/dependency/recovery claims;
- assertion sensitivity checks where safe.

A candidate test that still passes after the behavior it claims to protect is deliberately broken is weak evidence.

Assertiva should normalize results from existing tools before inventing its own mutation engine.

## Baseline preservation

The original suite is an immutable reference during an improve session.

- **ADD**: candidate adds new tests without changing originals.
- **MODIFY**: edits happen only in the isolated candidate; the project keeps the original until approval.
- **RETIRE_CANDIDATE**: Assertiva may evaluate the effect of disabling/removing a test in the isolated candidate, but the project copy stays active until explicit human approval.

Do **not** comment out original tests in active source files by default. Commenting silently changes discovery, creates dead code, can upset linting and makes the source harder to understand.

The safer equivalent is:
- keep the project original untouched;
- store its revision/fingerprint;
- show old vs candidate side by side in the report;
- require explicit approval for replacement or retirement;
- rely on Git/change-set history for recovery after an approved application.

No automatic deletion of original tests.

## Qualification pillars

Five pillars, each aggregating its checks (FAIL > BLOCKED > UNKNOWN > PASS; a check that did not run never passes a pillar on its own and stays visible):

1. **Execution** — static/discovery (candidate files parse/collect, identities known) and candidate tests (generated/modified tests execute with their intended oracle).
2. **Behavioral assurance** — original regression (existing tests remain valid unless an approved contract change says otherwise), coverage and oracle evidence, negative paths.
3. **Fault sensitivity** — mutation or deliberate negative controls: does the suite detect meaningful injected defects?
4. **Delivery fidelity** — pipeline-equivalent checks when safely reproducible; build and artifact evidence.
5. **Stability and cost** — flake/retry/runtime/resource impact.

A non-production preview environment is not a pillar: until a safe adapter and explicit authorization exist it is reported as not evidenced. Production deployment is never a qualification mechanism.

## Before / after metrics

Compare evidence, not just counts.

Useful dimensions include:
- definitions / materializations / invocations / attempts;
- pass/fail/error/blocked/skip/xfail/xpass;
- line / branch / condition / function coverage;
- parameterized case coverage and boundary classes;
- expected-error and negative-path evidence;
- rollback/no-side-effect evidence;
- integration fidelity and mock-away risk;
- E2E journeys, stage coverage and browser/platform matrix;
- mutation score / survivors;
- flaky/retry/order-dependence signals;
- runtime and CI resource cost;
- local/CI/build/deploy verification parity;
- package/startup/health evidence;
- weak-oracle/smoke/redundancy/shared-oracle signals.

Test count is **contextual**. More tests are not automatically better, and fewer tests are not automatically worse.

## Delta semantics

Each metric has an explicit direction:
- higher-is-better where meaningful, such as branch coverage or mutation kill rate;
- lower-is-better where meaningful, such as weak-oracle count or runtime for equivalent evidence;
- contextual for counts such as number of tests;
- informational when no quality direction is defensible.

No magic aggregate quality score.

## Regression rule

A candidate should not be described as "better" just because one metric improved.

Examples:
- coverage +8% but mutation score falls -> mixed result;
- fewer tests and same evidence with lower runtime -> potentially better;
- more tests but same behavior/oracle surface -> mostly churn;
- stronger negative-path coverage but +4x runtime -> improvement with cost tradeoff.

The Assurance Report presents these tradeoffs explicitly.
