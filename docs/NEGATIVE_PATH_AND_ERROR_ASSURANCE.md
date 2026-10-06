# Negative-Path, Validation, and Error Assurance

A test that intentionally provokes an error is not a failed test when the required product behavior is to reject, abort, roll back, degrade, retry or report that condition.

Negative-path evidence is first-class assurance.

## Core question

Do not ask only whether an error happened.

Ask whether the correct failure behavior happened at the correct boundary, with the required externally relevant effects and without forbidden side effects.

## Portable outcomes

Expected failure can appear as:
- exception;
- typed error/result value;
- protocol status/code;
- validation object;
- warning;
- process exit;
- UI error state;
- event/message;
- fail-fast startup/config rejection.

Adapters map native framework mechanisms into this model.

## Strong evidence

Where the contract requires it, verify:
- specific error category/type;
- stable machine code;
- field/path/location;
- protocol status;
- structured context;
- nested/multiple errors;
- precedence between validators;
- serialization across boundaries;
- no sensitive-data leakage;
- no unintended partial write/event/external call;
- rollback or compensation;
- retryability/non-retryability;
- idempotency after failure;
- recovery/degraded behavior;
- actual async observation/awaiting.

## False-green patterns

Examples:
- any exception is accepted;
- only 4xx/5xx is asserted while body/code/state matters;
- a human message is checked while machine fields drift;
- a promise/task/coroutine failure is never observed;
- rejection is asserted but state was partially persisted;
- mocks remove the real failure boundary;
- one invalid example is generalized to broad validation coverage.

## Expected versus unexpected failure

Preserve runner-native semantics:
- expected product rejection can produce PASS;
- assertion mismatch produces FAIL;
- unexpected product exception produces FAIL/ERROR according to the runner;
- infrastructure/environment failure is ERROR/BLOCKED by default;
- skip/abort/assumption/xfail is not PASS.

## Executable signals

Adapters report which parts of a failure contract a test observes, as portable dimensions: `ERROR_TYPE`, `MESSAGE`, `MACHINE_CODE`, `FIELD_OR_PATH`, `STRUCTURED_CONTEXT`, `PROTOCOL_STATUS`, `STATE_AFTER_REJECTION`, `ASYNC_OBSERVED`. Static dimensions are E3 signals: an assertion after a rejection is a state signal, not proof of rollback.

Findings must be supported by the suite itself, not by a universal rule: a type-only check is flagged when other tests show that error carries a code or field; a missing post-rejection check is flagged when other tests practice it.

## Validation classes

When relevant, include missing, null/empty, malformed, type mismatch, min/max boundaries, just-inside/exactly-at/just-outside boundaries, conflicting fields, duplicates/idempotency, unauthorized/forbidden, invalid state transition, stale/version conflict, dependency unavailable/timeout, malformed external payload and partial/concurrent failure.

Generative/property/fuzz testing can expand this space, but seeds/counterexamples must remain reproducible.
