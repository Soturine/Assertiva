# Assertiva Audit: notify

Assertiva mode: engine-backed

---

## Summary

**Project:** notify (0.9.2) — SMS notification service for overdue-invoice reminders.  
**Test Suite:** 3 test functions across 2 test modules (pytest).  
**Execution:** Static analysis only; 0 tests executed.

---

## DETERMINISTIC FACTS (Engine Output)

**E0/E1 Verification Surface:** One declared CI test gate.
- **Command:** `coverage run -m pytest -q && coverage report --fail-under=90`
- **Matrix:** ubuntu-latest, Python 3.12
- **Gate Status:** UNKNOWN (not executed)
- **Coverage Threshold:** 90% (declared)

**E2 Declared Facts:**
- Project requires Python >=3.11 (pyproject.toml)
- CI runs on ubuntu-latest, Python 3.12 only
- Pytest configured; testpaths: ["tests"]

**E3 Heuristic Signals (Static Oracle):**
- 3 test function definitions discovered
- 2 test modules (test_gateway.py, test_service.py)
- 0 weak-oracle test signals detected in static inventory
- 0 broad/general error-expectation tests
- 0 negative-path tests with explicit state verification after rejection

**Key Findings from Engine:**
- MATRIX_GAP: Declared Python 3.11 not tested; only 3.12 in CI
- CI_SINGLE_OS: No Windows/macOS coverage

---

## SEMANTIC AUDIT FINDINGS

### 1. Test-Doubles and Isolation Strategy (Fidelity Assessment)

**test_gateway.py:**
- Uses `unittest.mock.patch` to replace `urllib.request.urlopen` at module level
- Mock returns a BytesIO object simulating HTTP response structure
- **Oracle:** Assertion on return value (`message_id == "msg-42"`) and request construction
- **Concern - Implementation Coupling:** The test couples to internal request object structure (`request.full_url`, `request.data`) and JSON parsing logic, not the public contract of `SmsGateway.send()`
- **Concern - Mock Fidelity:** The mock does not simulate HTTP failure modes (timeouts, connection errors, partial reads). The production `urlopen` uses a 10-second timeout; the mock never exercises timeout behavior.
- **Verdict:** Mock isolation is tight but fidelity to real HTTP client behavior is incomplete. Test proves JSON request construction, not actual HTTP semantics.

**test_service.py:**
- Uses `MagicMock(spec=SmsGateway)` to isolate `notify_overdue` from the gateway
- Side effects configured to return message IDs or raise `GatewayError`
- **Assertion Strength:** Verifies outcome dictionary structure and call counts
- **Concern - Incomplete Error Matrix:** Test for rate-limit (HTTP 429) and one other error type ("INVALID_NUMBER"), but does not test HTTP 4xx/5xx codes mapped by gateway, timeouts, or partial failures (e.g., one customer sent, one fails mid-loop)
- **Verdict:** Tests confirm unhappy paths for two error codes. Loop termination and partial-failure state are not validated.

**Integration Risk:** No integration test verifies `notify_overdue` → `SmsGateway` → actual HTTP sequence, error propagation, or retry scheduling.

---

### 2. Oracle Strength and Observation Surfaces

**Positive Path (test_each_overdue_customer_gets_one_message):**
- Observable: message IDs returned in outcome.sent mapping
- Observable: call count matches customer count
- Observable: request method, URL, payload structure (request introspection)
- **Gap:** Does not verify HTTP status code (assumed 200). Production behavior if provider returns 201 or 202 is untested.

**Error Paths (test_rate_limited_customers_are_retried_later, test_other_provider_errors_fail_permanently):**
- Observable: outcome categorization (retry_later vs. failed vs. sent)
- Observable: customer ID assignment to outcome lists
- **Gap:** No assertion on the order of processing (is retry_later checked before failed, or vice versa?). Loop order is not validated.
- **Gap:** No test for mixed errors in one batch (e.g., first customer rate-limited, second succeeds).
- **Gap:** No verification of message content (body template). The `notify_overdue` function constructs message body; test mocks away `gateway.send` so message construction is never validated against real expectations.

**Verdict on Oracles:** Tests verify data-structure outcomes but not domain semantics (message quality, order, scheduling implication of retry_later).

---

### 3. Boundary and Failure Cases

**Tested:**
- Empty/single/multiple customer lists (implicit via side_effect length)
- Rate-limit error
- Other provider errors

**Not Tested:**
- Empty customer list (what does `notify_overdue([])` return?)
- Customer with missing fields (missing "phone", "invoice", "amount")
- Message body construction with special characters/encoding
- Concurrent calls to `notify_overdue` (no state shared, but not validated)
- Very large customer list (no resource/timeout risk assessed)
- `GatewayError` with code=None or empty string
- HTTP error 502/503 (temporary vs. permanent failure classification)

**Verdict:** Boundary coverage is narrow.

---

### 4. Coverage and Test-Execution Evidence

**Static Analysis Only:**
- No line, branch, or statement coverage data collected
- CI declares `coverage report --fail-under=90` but report was not executed to verify claim
- Cannot confirm whether all production paths are covered

**Unknowns:**
- Does the test suite achieve 90% coverage? UNKNOWN (--execute not run)
- Are there unreachable code branches? UNKNOWN
- Do tests exercise the timeout behavior in `SmsGateway.send`? NO (mock bypasses timeout)

**Verdict:** Coverage is declared but not evidenced.

---

### 5. Test Data and Fixtures

**Approach:** Inline customer dictionaries (ANA, BIA) with realistic Brazilian phone numbers and invoice IDs.
- **Positive:** Uses test data close to production format
- **Concern:** Hard-coded test data couples tests to specific phone format, invoice naming, currency format (R$ prefix)
- **Concern:** No parameterization; if test data format changes, tests must be manually updated
- **Concern:** No factories or parametrization; difficult to add new test cases quickly

---

### 6. Flaky/Retry Behavior

- No retry or flaky-recovery logic in tests or production code observed
- Tests do not assert order-independence or idempotence

---

### 7. Test Count and Redundancy

- 3 tests for 2 modules with ~40 LOC of production code: ratio is reasonable
- `test_each_overdue_customer_gets_one_message` tests positive path (happy path)
- `test_rate_limited_customers_are_retried_later` tests one error mode (HTTP 429)
- `test_other_provider_errors_fail_permanently` tests another error mode
- No semantic duplication detected; each test covers a distinct outcome

---

### 8. Verification Surface Completeness

**What is Verified:**
- Request construction (method, URL, headers, payload)
- Outcome mapping (sent, retry_later, failed)
- Error classification (RATE_LIMITED → retry_later, others → failed)

**What is Not Evidenced:**
- Actual HTTP client behavior (timeouts, connection failures, redirects)
- Message-body semantics and correctness
- Partial-failure resilience (batch with mixed outcomes)
- Deployment/startup behavior
- No load/performance testing
- No contractual/schema validation on response JSON

**Declared Gate Not Executed:**
- CI step `coverage run -m pytest -q && coverage report --fail-under=90` exists in `.github/workflows/ci.yml` but has not run on this revision

---

## REMAINING UNKNOWNS

1. **Do tests actually execute and pass?** Currently UNKNOWN (static analysis only).
2. **Does coverage meet 90% threshold?** Currently UNKNOWN (CI not executed).
3. **Does the test suite detect message-body defects?** NO — business logic (message template) is not validated.
4. **Are there latency/timeout contracts?** NO — timeout is declared (10s) but not tested.
5. **What happens on partial failure within a batch?** Not tested; behavior may be undefined.
6. **Does the service handle concurrent calls or concurrent retries?** No concurrency tests exist.
7. **Is the `Outcome` dataclass contract enforced?** No validation on mutation or misuse.
8. **Matrix coverage:** Python 3.11 (declared) is not tested; only 3.12 in CI.

---

## RECOMMENDATIONS

**Priority: HIGH**
1. Execute the full test suite (`--execute`) to confirm tests pass and coverage meets 90%.
2. Add integration test: `notify_overdue` → real (or test-double of real) HTTP client behavior.
3. Test message-body construction explicitly; add assertion on message format/content.
4. Add test case for partial-failure scenario: first customer rate-limited, second succeeds; verify outcome is correct and loop continues.

**Priority: MEDIUM**
1. Expand error-code matrix: test HTTP 502/503, timeout, connection error, JSON parse error.
2. Add parameterized test for multiple customer list sizes (empty, 1, 100, 1000).
3. Verify timeout contract: test that `SmsGateway.send` respects 10-second timeout.
4. Add Python 3.11 to CI matrix to align with declared support.

**Priority: LOW**
1. Refactor test data into factories or fixtures to reduce coupling to format.
2. Document expected message-body format in README and validate against it.
3. Consider property-based tests for message construction (e.g., no injection vectors).

---

## Evidence Log

**Files Read:**
- C:\Users\RAFAEL~1\AppData\Local\Temp\claude\c--Users-rafaelryan-Desktop-github-Assertiva\e77d3565-51c0-4283-92ea-3b9d860d6a63\scratchpad\evals-before\SEMANTIC_FINDING_NOT_SEEDED_BY_ENGINE\workspace\README.md
- C:\Users\RAFAEL~1\AppData\Local\Temp\claude\c--Users-rafaelryan-Desktop-github-Assertiva\e77d3565-51c0-4283-92ea-3b9d860d6a63\scratchpad\evals-before\SEMANTIC_FINDING_NOT_SEEDED_BY_ENGINE\workspace\pyproject.toml
- C:\Users\RAFAEL~1\AppData\Local\Temp\claude\c--Users-rafaelryan-Desktop-github-Assertiva\e77d3565-51c0-4283-92ea-3b9d860d6a63\scratchpad\evals-before\SEMANTIC_FINDING_NOT_SEEDED_BY_ENGINE\workspace\notify\gateway.py
- C:\Users\RAFAEL~1\AppData\Local\Temp\claude\c--Users-rafaelryan-Desktop-github-Assertiva\e77d3565-51c0-4283-92ea-3b9d860d6a63\scratchpad\evals-before\SEMANTIC_FINDING_NOT_SEEDED_BY_ENGINE\workspace\notify\service.py
- C:\Users\RAFAEL~1\AppData\Local\Temp\claude\c--Users-rafaelryan-Desktop-github-Assertiva\e77d3565-51c0-4283-92ea-3b9d860d6a63\scratchpad\evals-before\SEMANTIC_FINDING_NOT_SEEDED_BY_ENGINE\workspace\tests\test_gateway.py
- C:\Users\RAFAEL~1\AppData\Local\Temp\claude\c--Users-rafaelryan-Desktop-github-Assertiva\e77d3565-51c0-4283-92ea-3b9d860d6a63\scratchpad\evals-before\SEMANTIC_FINDING_NOT_SEEDED_BY_ENGINE\workspace\tests\test_service.py
- C:\Users\RAFAEL~1\AppData\Local\Temp\claude\c--Users-rafaelryan-Desktop-github-Assertiva\e77d3565-51c0-4283-92ea-3b9d860d6a63\scratchpad\evals-before\SEMANTIC_FINDING_NOT_SEEDED_BY_ENGINE\workspace\.github\workflows\ci.yml
- C:\Users\rafaelryan\.assertiva\reports\workspace-3895ef8bcdfca4c4\audit.html (engine output)

**Commands Executed:**
- `assertiva --version` → 0.5.8 available
- `assertiva audit . --output json` → static analysis; no execution; report saved to audit.html

**Assurance Report:**
- Path: C:\Users\rafaelryan\.assertiva\reports\workspace-3895ef8bcdfca4c4\audit.html
- Status: FINDINGS (2 medium/info findings; no tests executed)
- Run ID: 69749a929b404cd5
