# Test Doubles, Patching, and Service Virtualization

Mocks are neither inherently good nor bad. They trade fidelity for control, speed, isolation and observability.

## Vocabulary

- dummy: satisfies an interface but is not used meaningfully;
- stub: controls indirect input/return behavior;
- fake: working lightweight implementation with simplified semantics;
- spy: records interactions;
- mock: verifies expected interactions;
- patch/monkeypatch: temporarily replaces the name/dependency resolved by the SUT;
- service virtualizer/mock server: emulates an external protocol/service;
- emulator/simulator: reproduces a platform/service/device environment;
- disposable real dependency: real engine/service started for the test, often via containers.

Record the actual role instead of inferring from library names.

## Seam correctness

A patch must intercept the dependency where the SUT actually resolves/looks it up. Python unittest.mock's 'where to patch' rule is one language-specific example of a universal issue: patching the definition site instead of the consumed binding can make a test ineffective or accidentally exercise the real dependency.

Prefer verifying/typed/spec-constrained doubles when the ecosystem supports them, because unrestricted mocks can accept APIs that production dependencies do not.

## Mock-away rule

Ask what the test claims to prove.

Examples:
- patching a page-size constant to make pagination deterministic can be appropriate;
- replacing a payment gateway is appropriate for a domain unit test;
- replacing the database repository invalidates a claim of real repository/database integration;
- replacing the HTTP client may invalidate a claim about request serialization, TLS, headers or retries;
- mocking an internal value object/domain entity often couples tests to implementation and adds little value.

## Interaction assertions

Verify calls when the interaction itself is contractual: event emission, security audit, one-time charge, idempotency, protocol call, or collaboration boundary.

Do not over-specify private call order/count when the externally visible behavior can safely remain unchanged after refactor.

## Unused and unreachable setups

Trace configured doubles through the production path for the test input:
- used;
- unreachable because an earlier guard/exception returns first;
- unused by the target behavior;
- redundant/duplicated setup;
- intentionally shared default.

Unused setups can hide what a test actually depends on.

## Service virtualization vs real infrastructure

Virtualizers such as mock HTTP servers can preserve real client serialization/protocol behavior while controlling responses, latency and faults. They still cannot prove compatibility with every real provider behavior.

Disposable real infrastructure, including Testcontainers-style dependencies, increases engine/protocol fidelity but costs startup time, resources and operational complexity.

A practical strategy often combines:
- fast fake/mock tests for domain branching;
- contract/virtualized tests for protocol shape and failures;
- focused disposable-real-infrastructure tests for engine semantics;
- a small number of live/sandbox/E2E flows where that boundary is the risk.

## Record/replay

Record/replay can quickly build realistic fixtures but may ossify stale provider behavior, leak secrets and make tests pass against old recordings. Track source/date/version and refresh policy.
