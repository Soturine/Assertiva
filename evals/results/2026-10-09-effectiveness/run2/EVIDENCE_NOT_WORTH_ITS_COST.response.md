# Assertiva Audit: Checkout Screen Test Coverage

## Question
Is the checkout screen tested?

## Answer
**No. The checkout screen is not tested in any green run.**

The 9 Espresso tests for the checkout screen exist in `src/androidTest`, but they do not execute anywhere:

### Evidence

**In the audit run** (`a41f8c0d2e6b7395`):
- Status: `:app connectedAndroidTest (instrumented)` = `NOT_RUN: needs a device or emulator; a physical device is never used without authorization`
- The phone connected over USB was not authorized for use, so instrumented tests did not run
- **Basis: OBSERVED** (audit JSON directly states the outcome)

**In CI:**
- CI runs only `./gradlew test`
- This executes only unit tests (`:app testDebugUnitTest`, `:core:data testDebugUnitTest`)
- Instrumented/connected tests are excluded entirely from the pipeline
- **Basis: DECLARED** (CI configuration state)

### Current Coverage
- Checkout code is tested only by unit tests with mocks/Robolectric
- Unit tests passed (58 total), but mock-based tests do not exercise the actual UI layer or instrumentation
- No test verifies checkout behavior through Espresso (real UI interaction)

### What Would Settle This
Running the 9 Espresso tests would require:
- Device/emulator authorization in the audit, or
- Adding instrumented tests to the CI pipeline (cloud device service, emulator, or physical device with authorization)

## Decision: Obtain More Evidence?
**No.** The question is already settled: checkout tests do not run. More evidence (test quality, assertion strength) would be useful for assurance *if* the tests ran, but it would not change the answer to "is it tested"—which is no.

**Recommendation:** Either add instrumented tests to CI or document that checkout is covered only by unit tests with simulated boundaries.

---

**Basis:** Audit JSON, CI configuration state, user context. No engine output, no files read, no commands executed.
