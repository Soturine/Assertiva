# Is the checkout screen tested?

## Answer

The checkout screen has dedicated tests (9 Espresso tests in src/androidTest) that exist in the source tree but are excluded from CI and were not executed during the audit run.

## Evidence breakdown (the five steps)

1. **exists** — YES. The context states "src/androidTest holds 9 Espresso tests for the checkout screen."

2. **selected** — DECLARED but NOT_RUN. The tests are in the source code but not included in the test execution plan.

3. **executed** — NO, at two levels:
   - Local audit run: The audit output shows `:app connectedAndroidTest (instrumented): NOT_RUN: needs a device or emulator; a physical device is never used without authorization`. The engine did not run them without explicit authorization, despite a USB-connected phone being available.
   - CI: The workflow runs only `./gradlew test` (unit tests), not the instrumented tests (`connectedAndroidTest`).

4. **outcome** — UNKNOWN. Tests did not execute, so no outcomes were observed.

5. **proven** — UNKNOWN. Cannot assess what the Espresso tests would prove about checkout behavior without observing their execution and assertions.

## Key findings

**Delivery gap:** The checkout screen has dedicated Espresso tests in source, but:
- CI runs only unit tests (`./gradlew test`), excluding instrumented tests
- The audit could not run them without authorization for device use
- Green unit-test results (58 passing) do not prove the actual checkout UI works; they only prove unit-level logic, likely with mocked or simulated device boundaries

The 21 Robolectric tests among the 58 passing simulate the device, but whether any of them test checkout screen behavior is unknown from this context.

## Should more evidence be obtained?

**Given you are in a hurry: No.** You have enough to identify the gap: checkout tests exist but are outside the CI/audit boundary.

To answer whether checkout is actually safe to ship, you would need to:
- Add the 9 Espresso tests to your CI pipeline, OR
- Authorize a local `assertiva audit --execute` run with device use enabled and observe whether the Espresso tests pass

The decision is yours based on how critical checkout is to your release and your risk tolerance.
