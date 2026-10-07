# Audit: notify Test Suite

## Summary

The test suite provides strong execution coverage and proves the happy path through both the service and gateway layers. However, there is a **critical semantic gap at the service-gateway boundary**: the test suite mocks away the actual error code transformation that happens in the real gateway, creating a false green for rate-limiting scenarios. In production, rate-limited requests (HTTP 429) would be treated as permanent failures instead of being retried, despite tests claiming to cover this behavior.

**Confidence**: HIGH. This is a deterministic mismatch between what the tests assert and what the real code does.

## What the Tests Prove

**OBSERVED** (via `assertiva audit --execute`):
- All 4 tests execute and pass in an isolated copy
- The suite runs against the installed wheel artifact (artifact qualification: PASS)
- Line coverage: 91.67% (99/108 lines)
- Branch coverage: 64.29% (9/14 branches)
- No collection errors, no assertion failures, no flaky behavior observed

**Proven behaviors** (from test inspection and execution):
- Each customer in the input list receives one SMS message attempt
- The gateway.send method is called with the correct phone number and formatted message body
- Successful responses extract and return the message ID correctly
- The outcome object correctly aggregates sent messages

## Critical Finding: Semantic Integration Gap

### The Problem

The service module and gateway module have a **semantic contract mismatch** that the test suite does not catch:

**gateway.py line 27** (OBSERVED):
```python
except HTTPError as exc:
    raise GatewayError(f"HTTP {exc.code}") from exc
```
When the SMS provider returns HTTP 429 (rate limit), this creates a GatewayError with code="HTTP 429" (as a string, since exc.code is an integer).

**service.py line 22** (OBSERVED):
```python
if exc.code == "RATE_LIMITED":
```
This checks for the exact string "RATE_LIMITED", which will never match "HTTP 429".

**Result**: When a rate-limited response arrives, the service will classify it as a permanent failure and add the customer to `outcome.failed` instead of `outcome.retry_later`, violating the contract stated in the README ("rate-limited sends are retried by the next scheduler pass").

### Why Tests Don't Catch This

**test_service.py line 21** (OBSERVED):
```python
gateway.send.side_effect = [GatewayError("RATE_LIMITED"), "m-2"]
```

The test creates a GatewayError directly with code="RATE_LIMITED", **bypassing the actual gateway error transformation**. This is a classic test-double seam placement issue:
- The mock is placed at the wrong seam: at the function boundary, not at the HTTP boundary
- The mock encodes the service's assumption about what the error code will be
- No test exercises the real gateway → service → outcome chain

**Verification** (OBSERVED from code inspection):
- Grep search: `grep -r "429"` returns nothing in the codebase
- Grep search: `grep -r "RATE_LIMITED"` returns only test_service.py and service.py
- No mapping, conversion, or HTTP status code interpretation logic exists

### Evidence

| Evidence | How I Know |
| --- | --- |
| gateway.py raises `GatewayError(f"HTTP {exc.code}")` where exc.code is an int | OBSERVED: read gateway.py:27 |
| service.py checks `exc.code == "RATE_LIMITED"` | OBSERVED: read service.py:22 |
| The strings "HTTP 429" and "RATE_LIMITED" will never match | INFERRED: string equality rules |
| test_service.py mocks with `GatewayError("RATE_LIMITED")` directly | OBSERVED: read test_service.py:21 |
| No HTTP 429 → RATE_LIMITED mapping exists in the codebase | OBSERVED: grep -r "429" returns nothing |
| The test does not use the real SmsGateway class in the rate-limit scenario | INFERRED: test uses MagicMock(spec=SmsGateway), not real gateway |

### Consequence for Assurance

A real invocation of the service with a rate-limited SMS provider would:
1. Raise HTTPError with code=429
2. gateway.send() raises GatewayError("HTTP 429")
3. service.notify_overdue() catches it
4. Checks if "HTTP 429" == "RATE_LIMITED" → FALSE
5. Adds customer to outcome.failed (wrong bucket)
6. Never retries the customer, contradicting the documented behavior

The green test suite provides **false assurance** that rate limiting is handled correctly. This is a regression risk for any code depending on the retry_later behavior (e.g., scheduler logic, downstream alerting on failed customers).

## Other Observations

### Uncovered Branches (64.29%)

The 5 uncovered branches are in gateway.py and include:
- The successful return path (no exception, response.read() succeeds)
- Potentially error branches in JSON parsing or URL construction

These are not exercised because test_gateway.py mocks urlopen, testing the mock behavior rather than the actual urlopen → json.loads flow. No integration test verifies the real HTTP request → JSON parsing chain.

### Coverage Does Not Prove Completeness

High line coverage (91.67%) is misleading here:
- A high-coverage test suite can have low oracle strength
- Coverage metrics count execution, not correctness
- The missing 9% of branches likely include error recovery paths

### No Integration Test

There is no test that:
- Creates a real SmsGateway instance
- Calls notify_overdue with a real gateway (or a more realistic test double)
- Verifies the service-gateway boundary semantics

The suite is entirely composed of unit tests with mocks at the function boundary.

### CI and Runtime Coverage

**CI (OBSERVED from .github/workflows/ci.yml**):
- Python 3.12 only (pyproject.toml declares >=3.11, so 3.11 is untested) — MATRIX_GAP finding
- Ubuntu Linux only (no Windows/macOS coverage) — CI_SINGLE_OS finding
- The CI runs the same suite that was just verified locally

**Delivered artifact (OBSERVED from audit wheel check)**:
- The wheel builds, installs, and passes tests in isolation
- No deployment, health, or startup checks are run
- The artifact is never deployed (NOT_DECLARED)

## Assessment of Engine Findings

The Assertiva engine correctly identified:
1. **MATRIX_GAP** (CONFIRMED): Python 3.11 is declared but not tested. Recommendation applies.
2. **CI_SINGLE_OS** (CONFIRMED): Only Linux is tested. Recommendation applies.

The engine did not report the semantic integration gap because:
- It uses static oracle signals (assertion pattern heuristics), which cannot reason about error code string matching
- Mocks and direct error creation bypass the semantic check
- The heuristics look for weak assertions, not for semantic contract mismatches between layers

## What Remains Unknown

- Whether the declared CI workflow actually runs on commits (GitHub provider access required)
- Whether mutation testing would expose this gap (the error-code path is executed, but with wrong semantics)
- How the service is actually invoked in production (rate-limit handling only matters if the gateway is ever rate-limited in practice)
- Whether there are other error codes the service should recognize (only RATE_LIMITED is handled specially)

## Recommendations

1. **High priority**: Add an integration test that exercises the real SmsGateway → notify_overdue → outcome chain, or refactor the error handling to make the semantic contract explicit. Example:
   - Create a test that fakes HTTP 429 responses and asserts `outcome.retry_later` contains the customer
   - Or: add a method to GatewayError to query the HTTP status code independently, and update the service to check for HTTP status 429

2. **Medium priority**: Fix the MATRIX_GAP finding. Test on Python 3.11 (the minimum declared version) in addition to 3.12.

3. **Low priority**: Test on additional operating systems (Windows, macOS) if those are part of the deployment target. If Linux-only, update pyproject.toml or CI to clarify.

4. **Verify**: Check production logs or telemetry to confirm whether rate-limiting is a scenario the service actually encounters. If it never happens, the gap may be theoretical.

## Evidence Log

### Files Read
- C:\Users\RAFAEL~1\AppData\Local\Temp\claude\c--Users-rafaelryan-Desktop-github-Assertiva\e77d3565-51c0-4283-92ea-3b9d860d6a63\scratchpad\evals-after\SEMANTIC_FINDING_NOT_SEEDED_BY_ENGINE\workspace\README.md
- C:\Users\RAFAEL~1\AppData\Local\Temp\claude\c--Users-rafaelryan-Desktop-github-Assertiva\e77d3565-51c0-4283-92ea-3b9d860d6a63\scratchpad\evals-after\SEMANTIC_FINDING_NOT_SEEDED_BY_ENGINE\workspace\pyproject.toml
- C:\Users\RAFAEL~1\AppData\Local\Temp\claude\c--Users-rafaelryan-Desktop-github-Assertiva\e77d3565-51c0-4283-92ea-3b9d860d6a63\scratchpad\evals-after\SEMANTIC_FINDING_NOT_SEEDED_BY_ENGINE\workspace\notify\__init__.py
- C:\Users\RAFAEL~1\AppData\Local\Temp\claude\c--Users-rafaelryan-Desktop-github-Assertiva\e77d3565-51c0-4283-92ea-3b9d860d6a63\scratchpad\evals-after\SEMANTIC_FINDING_NOT_SEEDED_BY_ENGINE\workspace\notify\service.py
- C:\Users\RAFAEL~1\AppData\Local\Temp\claude\c--Users-rafaelryan-Desktop-github-Assertiva\e77d3565-51c0-4283-92ea-3b9d860d6a63\scratchpad\evals-after\SEMANTIC_FINDING_NOT_SEEDED_BY_ENGINE\workspace\notify\gateway.py
- C:\Users\RAFAEL~1\AppData\Local\Temp\claude\c--Users-rafaelryan-Desktop-github-Assertiva\e77d3565-51c0-4283-92ea-3b9d860d6a63\scratchpad\evals-after\SEMANTIC_FINDING_NOT_SEEDED_BY_ENGINE\workspace\tests\test_service.py
- C:\Users\RAFAEL~1\AppData\Local\Temp\claude\c--Users-rafaelryan-Desktop-github-Assertiva\e77d3565-51c0-4283-92ea-3b9d860d6a63\scratchpad\evals-after\SEMANTIC_FINDING_NOT_SEEDED_BY_ENGINE\workspace\tests\test_gateway.py
- C:\Users\RAFAEL~1\AppData\Local\Temp\claude\c--Users-rafaelryan-Desktop-github-Assertiva\e77d3565-51c0-4283-92ea-3b9d860d6a63\scratchpad\evals-after\SEMANTIC_FINDING_NOT_SEEDED_BY_ENGINE\workspace\.github\workflows\ci.yml

### Commands Run
1. `ls -la` in workspace (listed directory structure)
2. `find . -type f -name "*.py"` (found 5 Python files)
3. `grep -r "RATE_LIMITED" --include="*.py"` (found 2 matches: service.py and test_service.py)
4. `grep -r "429" --include="*.py"` (found no matches)
5. `assertiva audit <workspace> --output json --execute` (produced 64bde62991e54dcc run, JSON parsed from stdout)

### Engine Output Reviewed
- Run ID: 64bde62991e54dcc
- Report path: C:\Users\rafaelryan\.assertiva\reports\workspace-4ba6d0ab5681aa56\audit.html
- Findings: MATRIX_GAP (CONFIRMED), CI_SINGLE_OS (CONFIRMED)
- Metrics: 4/4 tests pass, 91.67% line coverage, 64.29% branch coverage
- Artifact qualification: PASS (wheel builds, installs, imports, tests pass)
