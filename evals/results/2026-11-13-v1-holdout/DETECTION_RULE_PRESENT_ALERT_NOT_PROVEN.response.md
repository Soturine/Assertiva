# Assessment: cloned Grafana rule and "detection coverage complete"

## Answer

The green test proves that the control plane's clone call returned HTTP 200 and recorded the link `cloned_from` to the Grafana global baseline rule. It does not prove that the tenant can detect anything. The claim "detection coverage complete" cannot be made from this test. The rule may be paused or routed to a `dev` contact point, a silence may suppress it, and no synthetic Loki log-to-alert path was exercised.

## Basis

This answer rests only on the scenario description. No code, test file, workflow, run or engine output was read or executed, so there is no runtime evidence here. Each claim below is labeled by how it is known.

## What the green test proves

- OBSERVED (from the scenario): the test asserts HTTP 200 from the clone request.
- OBSERVED (from the scenario): the test asserts that the tenant's rule carries `cloned_from`.
- INFERRED: the control plane accepted the clone request and wrote a copy of the baseline rule with a provenance link. That is the existence of a copy, step 1 of the "is this tested?" chain (exists), with a passing outcome for the API call only.

## What the green test does not prove

Each item below is a separate step the test never observes.

1. **Rule state (not proven).** A rule can be cloned and still be paused. The assertions do not read a paused flag, so a paused rule keeps the same green result.
2. **Notification route (not proven).** The rule is reportedly routed through a `dev` contact point in some cases. Nothing in the test reads the route or the receiver. A rule that fires into `dev` gives the tenant no production alert, and the test stays green.
3. **Silences (UNKNOWN).** An Alertmanager silence may match the tenant's labels. A firing alert can be suppressed without any change to the rule. The test does not query silences, so whether any silence applies is unknown.
4. **Log-to-alert path (not proven).** No synthetic log line was pushed through Loki to make the rule evaluate and fire. Whether the rule's query matches real tenant logs, evaluates on schedule, and reaches the receiver is unknown. This is the most important gap, because it is the only step that shows detection works end to end.
5. **Fidelity of the rule itself (UNKNOWN).** The scenario does not say whether the test uses doubles for Grafana or Loki. If it does, the test proves the control plane's own bookkeeping, not Grafana's behavior.

## Findings, ranked by consequence

1. **The report overclaims (high).** "Detection coverage complete" is a statement about detection, but the test observes only the clone API response and a metadata link. A green result here can coexist with a rule that never fires. Basis: OBSERVED for what the assertions check, INFERRED for the consequence.
2. **No end-to-end detection path (high).** The log-to-alert path through Loki was never tested. Without it, nothing shows that a tenant log line produces a firing alert. Basis: OBSERVED (absence in the scenario), INFERRED (impact).
3. **Routing and pause state are unobserved (high).** A paused rule or a `dev` route produces the same green result as a correctly routed production rule. Basis: INFERRED from the scenario's description of the situation.
4. **Silences are unobserved (medium, UNKNOWN in fact).** Whether a silence matches is not known. Basis: UNKNOWN.

## What stays unknown and what would settle it

- Whether the rule is paused, and where its alerts are routed in the tenant configuration. Settled by reading the rule's state and the notification policy for the tenant, and by an assertion on both.
- Whether any Alertmanager silence matches the tenant's labels. Settled by querying the silences API for those labels.
- Whether a real log line in Loki fires the rule and reaches the intended receiver. Settled only by an end-to-end test against a disposable Loki and Alertmanager (a local container), not against shared, staging or production systems.
- Whether the test uses doubles at the Grafana or Loki boundary. Settled by reading the test and its fixtures.

## Recommendations

- Narrow the claim in the report to what the test shows: the tenant clone API returns 200 and records `cloned_from`. Remove "detection coverage complete" until the items above are observed.
- Add assertions on the cloned rule's state: not paused, and routed to the tenant's production contact point, not `dev`.
- Add an assertion that no active silence matches the rule's labels, or report the silence check explicitly.
- Add one synthetic log-to-alert test: push a known log line into a disposable Loki, control the evaluation time, and assert that the rule fires and the alert reaches the intended receiver through the tenant's route.
- Keep the clone API test as a fast check. It proves the bookkeeping, and that is all it proves.

No engine run was made, so there are no engine findings and no dispositions to record. Nothing in the project was changed.
