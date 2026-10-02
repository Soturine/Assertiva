# Error and Validation Contracts

Invalid input and failure behavior are part of the product contract. A deliberately provoked error can be a successful test outcome when rejection is the required behavior.

## Portable error model

Where observable, normalize:
- category/domain;
- concrete type/class;
- stable machine code;
- path/location/field;
- HTTP/RPC/protocol status;
- context/constraint parameters;
- sanitized offending input or input class;
- message policy;
- nested/multiple errors;
- cause/chain when material;
- outcome kind: exception, error value/object, protocol status, warning, process exit, event, UI error state or other;
- state-effect policy: no side effect, rollback, allowed partial effect, compensation, not asserted or unknown;
- recovery policy: retryable, non-retryable, compensated, degraded, fail-fast, not asserted or unknown;
- sensitive-data policy;
- async observation status.

## Assertion guidance

Prefer stable semantic fields over brittle message-only equality unless exact wording/localization is itself required.

Test:
- correct error for each invalid class;
- boundary vs invalid distinction;
- nested field/path attribution;
- multiple simultaneous violations when supported;
- precedence when several validators could fail;
- strict/coercion behavior;
- serialization/API mapping;
- no sensitive-data leakage;
- rollback/no-partial-write/compensation behavior when material;
- retry/idempotency/recovery semantics when material;
- async error observation rather than unobserved task/promise failures.

"Some exception happened" is weaker than a specific contract. Likewise, an error status alone may be insufficient if clients depend on code/path/body/state.

## Expected failure is positive evidence

Expected exceptions, rejected tasks/promises, typed error values, protocol failures, UI validation states and equivalent mechanisms are valid assertion evidence when the product contract requires rejection.

Do not classify such tests as "no assertion" merely because the framework expresses the oracle through an expected-error helper instead of a plain boolean assert.

Distinguish:
- expected product rejection: the test may PASS;
- assertion mismatch: FAIL;
- unexpected product exception: FAIL/ERROR according to runner semantics;
- environment/infrastructure problem: ERROR/BLOCKED rather than a product defect by default;
- skip/abort/assumption/xfail: preserve native runner meaning and do not collapse to PASS.

## Negative-path depth

A negative-path test can be shallow even when it is correct.

Examples of weak evidence:
- accepting any exception type;
- checking only a 4xx/5xx status while code/body/path matters;
- checking rejection but not verifying forbidden side effects;
- checking a message while machine-readable error fields drift;
- checking one invalid example while claiming broad validation coverage.

Where the claim requires it, verify both the rejection and the resulting system state.

## Framework neutrality

Frameworks expose different mechanisms for expected exceptions, rejected promises/tasks, error values and protocol failures. Adapters translate those mechanisms into the portable error model; core policy must not depend on a specific framework or validation library.

## Error changes during refactor

Changing error class, code, path, status, serialization, rollback behavior, retryability or sensitive-data exposure can be a breaking behavioral change even when success-path output is identical.
