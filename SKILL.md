# Assertiva — Adaptive Test Intelligence & Assurance

Use Assertiva when the task involves test-suite quality, verification-surface discovery, affected-test/check selection, failure diagnosis, E2E localization, regression evidence, CI/CD execution, local-vs-pipeline parity, build/package/deploy verification gaps, test-output/context cost, flaky behavior, mutation/negative controls, or refactor safety.

## Goal

Produce the greatest reasonable evidence of correctness at the lowest reasonable execution, investigation, and agent-context cost without weakening the claim being made.

```text
FAST FEEDBACK
!= REGRESSION CONFIDENCE
!= TEST QUALITY
```

## Deterministic-first evidence policy

Prefer deterministic, machine-verifiable evidence whenever possible.

- **E0 RAW** — native runner/report/source artifact.
- **E1 DETERMINISTIC_DERIVED** — reproducible parsed/normalized result.
- **E2 DECLARED** — project-authored mapping/policy/metadata.
- **E3 HEURISTIC** — fallible static/ranking/similarity/smell signal.
- **E4 INFERRED** — semantic/LLM inference requiring supporting evidence.

E3/E4 may rank, flag, cluster and propose. They must not silently suppress material tests or close consequential gates. When evidence is insufficient, widen execution or report UNKNOWN.

Label every claim with its category and never move it to another one silently:

- **DETERMINISTIC FACT** (E0/E1) — "run 123 succeeded for SHA abc", "coverage line 83/100 from coverage.xml".
- **DECLARED FACT** (E2) — "the GitHub Actions workflow declares Python 3.12": configuration, not execution.
- **HEURISTIC SIGNAL** (E3) — "605 functions start with `test_`", "~1446 `assert*` call occurrences": static counts, never executed tests, meaningful assertions or oracle strength without native discovery/runtime evidence.
- **SEMANTIC INFERENCE** (E4) — "this oracle appears weak", "the uncovered branch looks safety-critical": your reasoning, never presented as engine output.
- **UNKNOWN** — what no available evidence settles.

Revision provenance: a green CI run proves a revision only when its identity is confirmed (for example the run's head SHA equals `git rev-parse HEAD`, or an equally explicit link). Otherwise report "CI green observed; correspondence to HEAD UNKNOWN" and never raise it to E0 or proof for the current revision. A dirty working tree is never proven by any run.

## Execution mode and the engine

Before auditing a project, check whether the deterministic engine is available (`assertiva --version`).

- **engine-backed** — start with the cheapest call, `assertiva audit <project> --output json`, which is static and read-only. Use `--execute`, `--changed-since`, coverage, mutation, JUnit or other runs only when the new evidence would change a decision or close a material UNKNOWN: new execution must buy new evidence. Capture `report_path` (the HTML Assurance Report the engine wrote) from the output.
- **semantic-only** — the engine is missing or fails to start. Continue the audit with the Skill; do not abort, imply runtime evidence or promise an HTML report.

Open the answer with one line, no banner: `Assertiva mode: engine-backed` or `Assertiva mode: semantic-only — local engine unavailable; runtime evidence and Assurance HTML were not produced.` Then report deterministic evidence (engine or native artifacts), semantic findings, unknowns and recommendations as distinguishable parts. When the engine produced a report, end with `Assurance Report:` and the `report_path`. The Skill never renders HTML itself.

Normal use is an audit, not a grade: never present PASS/FAIL/REVIEW as the Skill's verdict. Those belong to the Skill evaluation in `evals/semantic.py`.

Recommendations must follow from the project's delivery/consumption model, not from a generic checklist. Example: for a library, tool or package, prefer declared compatible dependency ranges plus constrained, reproducible CI and minimum- and latest-supported dependency runs; a lockfile fits an application or development environment and is not an automatic recommendation.

## AUDIT

Determine whether existing tests actually provide meaningful evidence.

Inspect as applicable:
- authoritative requirement/invariant/oracle;
- assertion strength and observable effects;
- negative/boundary/failure/recovery/concurrency/authorization/migration cases;
- integration fidelity and suspicious mocks;
- flaky/retry-dependent behavior;
- duplicate/redundant tests;
- snapshots/goldens and update provenance;
- UI/browser locator strategy and incidental DOM coupling;
- semantic role/name/label/state and accessibility-tree evidence;
- keyboard/focus behavior distinct from pointer interaction;
- retry/timeout changes that may mask flakes or races;
- parameterized/table/data-driven definitions and material invocations;
- property-based/generative tests, seeds and minimized counterexamples;
- fuzz corpora/crash reproducers;
- structured validation/error contracts;
- line/statement vs branch/condition/function/instruction coverage;
- dynamic/generated tests;
- async/concurrency/race assumptions;
- mutation/negative-control/differential/independent evidence;
- exact revision/environment/configuration/run provenance.

Coverage and test count are diagnostics, not proof.

Also inspect the complete verification surface that turns repository state into delivery evidence:
- tests, linters, type/static checks, schema/generated-code checks, migrations, localization/i18n checks, security scans, build/package/container/startup/health/deploy checks, hooks and project-specific commands;
- which checks exist versus which checks local workflows, hooks and CI/CD actually execute;
- path/marker/filter/project exclusions, skips, retries and allowed-failure/advisory semantics;
- runtime/OS/browser/database/service matrix differences;
- source-tree validation versus built/installed/deployed artifact behavior.

Do not hardcode project names, one framework, one test runner or one CI provider into core policy. Tool-specific knowledge belongs in adapters. Unknown commands/checks remain explicit UNKNOWN/CUSTOM evidence until an adapter or declared project contract can classify them.

A repository containing a check does not prove the delivery path executed it. A green pipeline proves only the checks and environments that actually ran.

## User intent and write boundaries

Keep the user-facing interaction simple.

- **AUDIT** means inspect, measure, execute permitted verification, find gaps and recommend improvements. It must not modify project files.
- **IMPROVE** means audit first, then build candidate changes outside the original project, verify the candidate, present baseline-vs-candidate evidence, and request approval before applying anything.

Do not expose internal implementation details such as temporary workspaces, worktrees, patch staging or post-apply checks as separate everyday modes unless troubleshooting requires it.

Runtime enforcement is required:
- audit keeps the project read-only;
- improve writes only to isolated candidate state until approval;
- application is limited to the approved change set;
- stale source changes must block unsafe blind overwrite.

Reports/artifacts should default to Assertiva-owned storage outside the audited repository so read-only use does not dirty the working tree.

### Driving `assertiva improve`

1. `assertiva improve` measures the baseline and prints a candidate workspace. Write candidate changes **only there**.
2. `assertiva improve` again qualifies the candidate. Optionally pass:
   - `--negative-controls <file.json>`: a list of `{"control_id", "path", "find", "replace", "claim", "tests"?}` deliberate behavior-breaking edits that the tests claiming `claim` must detect (run only in disposable copies);
   - `--mutation-report baseline=<path>` / `candidate=<path>`: existing mutation-tool reports for each state (run the tool in the corresponding workspace; Assertiva ingests, it does not mutate);
   - `--run-check <CHECK_ID>`: only when the human authorizes running a specific discovered delivery check (migration, container, custom command). Never authorize deploy/publish checks; Assertiva will not run them anyway.
3. Show the report to the human. Never pass `--approve` on your own initiative: approval names specific change ids and belongs to the human.
4. `--discard` drops the candidate without touching the project.

## Reporting contract

Produce one Assurance Report model for both workflows.

For AUDIT, report CURRENT + FINDINGS + RECOMMENDATIONS + UNKNOWNS.

For IMPROVE, report BASELINE vs CANDIDATE, then APPLIED only after approval and post-apply verification.

Prefer evidence delta over a synthetic quality score:
- improved;
- unchanged;
- regressed;
- unknown.

The HTML surface should include accessible charts and textual/table equivalents, filters, expandable findings, provenance/limitations, verification-surface views, coverage/test-quality statistics, change-set summaries and a final "What does green prove?" section.

Candidate metrics are candidate evidence, not current-project evidence.

## Candidate qualification / test-the-tests

Inside IMPROVE, do not trust generated or modified tests merely because they pass. Qualify the candidate safety net using the strongest available evidence:
- candidate tests and the unchanged original regression suite;
- line/branch/condition/function coverage as available;
- assertion/oracle strength;
- negative-path/error/rollback/state-effect evidence;
- parameterized/boundary-case materialization;
- integration/E2E fidelity and matrix coverage;
- mutation testing or deliberate negative controls where proportionate;
- flake/retry/order-dependence signals;
- runtime/resource cost;
- pipeline-equivalent checks and build/package/startup evidence;
- optional non-production preview deployment only when supported, safe and explicitly authorized.

Never deploy to production merely to qualify candidate tests.

Original tests are immutable baseline evidence during IMPROVE. ADD/MODIFY/RETIRE proposals happen only in isolated candidate state until approval. A retirement candidate must keep the project original active until explicit human approval. Do not comment out originals in active files as a default preservation mechanism; preserve revision/fingerprint and show side-by-side diffs instead.

A higher test count is not automatically an improvement. Compare evidence deltas with explicit metric direction and report mixed/regressed/unknown dimensions without collapsing them into a single quality score.

Read docs/CANDIDATE_QUALIFICATION_AND_TEST_THE_TESTS.md when proposing or evaluating test changes.

## Optional integrations

Functional Test Designer is an optional source of authority-rich Test Cases. Preserve its oracle/provenance when present, but Assertiva must work normally on projects that only have pytest/Jest/Playwright/JUnit/etc. Functional Test Executor is also optional and applies when Azure Test Plans fetch/publication is part of the workflow. See docs/FTD_FTE_INTEROPERABILITY.md.

## SELECT

Choose candidate tests using the strongest available evidence from changed symbols, dependency graphs, runtime test-to-code maps, contracts, critical journeys, Git history, known regressions and project-declared mappings.

Always expose limitations. Exact/deterministic mappings can exclude tests only within their proven scope. Heuristic/inferred impact should prioritize, not prove unaffectedness.

## RUN

Run the smallest sufficient high-signal evidence first when policy permits. Do not report a selected subset as full-suite/release proof.

## DIAGNOSE

1. identify failing check and first divergent stage;
2. cluster likely shared failures;
3. find the smallest useful reproducer;
4. descend from E2E only when lower layers reproduce/isolate the same failure;
5. escalate diagnostics D0→D4 only as needed;
6. classify product defect, test/oracle defect, environment/infra defect, data problem, flake, or unresolved.

## VERIFY

After a fix/refactor:
1. rerun minimal reproducer;
2. rerun affected dependents;
3. run affected regression;
4. run relevant contract/integration/E2E;
5. run broader/full gates when risk, milestone/release policy, selector uncertainty, or project rules require them.

## Progressive diagnostics

- D0 Summary
- D1 Failure
- D2 Context
- D3 Trace
- D4 Forensic

Never assume `-v/-vv/-vvv` semantics are portable.

## Test identity

Do not collapse a parameterized/dynamic test definition into one boolean result when individual invocations are observable.

```text
suite → definition → invocation/data case → attempt/retry → result
```

Preserve stable IDs, sanitized parameter identity, matrix dimensions, attempt number and dynamic/partial-discovery status.

## Structured errors

Invalid-input behavior is part of the contract. Prefer stable structured fields such as category/type/code/path/location/context/status and sanitized input over brittle message-only assertions, unless exact wording is itself required.

Pydantic ValidationError is one adapter-specific form, not a core dependency.

## Coverage semantics

Never reduce coverage to one percentage. Preserve metric kind, denominator, scope, exclusions, tool/version and aggregate-vs-test-specific context. Line coverage does not imply branch/condition coverage, and none of them proves oracle adequacy.

## Property/fuzz/metamorphic evidence

Preserve seed/replay token, run budget, counterexample, minimized/shrunk counterexample and corpus where available. Randomized success without replay data is weaker diagnostic evidence.

## Failure-guided E2E decomposition

Do not repeatedly rerun an expensive E2E when a smaller safe reproducer can isolate the same stage. After repair, return to the original composition-level evidence when the claim depends on it.

## Refactor safety

Before consequential refactoring, establish authoritative behavior and build a safety matrix mapping important behaviors/contracts to unit/property/characterization, integration/contract, E2E/composition and non-functional evidence as applicable.

Classify readiness:
- READY
- READY_WITH_GAPS
- NOT_READY
- UNKNOWN

A green suite or 100% line coverage does not make a refactor safe by itself. The question is whether meaningful unintended behavioral changes in the refactored scope would be detected.

For whole-project refactors, inventory behavior slices as protected, weakly protected, characterization-only, integration-only, E2E-only, unprotected, or unknown before restructuring them.

Never weaken test expectations merely to make a refactor pass.

## Test-the-safety-net

Where proportionate, challenge the suite with mutation testing, deliberate negative controls, known historical regressions, boundary perturbations, contract violations, property/metamorphic tests, or intentionally broken candidate implementations in a sandbox.

## Harness, fidelity, observations, data and doubles

Never infer test strength from a framework class, file suffix, or label alone. When integration/UI/API/database fidelity matters, read docs/TEST_HARNESS_AND_FIDELITY.md and record the actual process, transport, persistence, transaction, dependency, UI runtime, matrix and isolation boundaries.

When auditing assertions, map them to behavior claims and observation surfaces using docs/ASSERTIONS_ORACLES_AND_OBSERVATION_SURFACES.md. Status/content/template/context/persistence/call/visual/accessibility observations prove different things.

When fixtures, factories, Faker/generated data, shared setup, database seeds or order-dependence matter, use docs/TEST_DATA_FIXTURES_FACTORIES.md.

When mocks, spies, fakes, patch/monkeypatch, virtual services or containers are involved, use docs/TEST_DOUBLES_PATCHING_AND_VIRTUALIZATION.md. Verify the seam actually used by the SUT and do not mock away the boundary a test claims to integrate.

For HTTP/API/browser/component/mobile/web flows, use docs/WEB_API_UI_TESTING.md and preserve request, auth, state, rendering, accessibility, visual and platform-matrix claims independently.

For implementation/productization of Assertiva itself, use docs/AGENT_SKILL_MCP_ARCHITECTURE.md: Skill owns policy, deterministic core owns reproducible processing, CLI is the default token-efficient agent surface, and MCP is optional for persistent state/graph/artifact/job workflows.

## Semantic UI / browser assurance

For browser/component UI tests, prefer assertions and locators tied to the intended user/product contract when such a contract exists. Native semantics come first; ARIA supplements semantics where needed and must not be added merely for test convenience.

Treat role/name/state, keyboard/focus, interaction, visual output, browser storage/network state and backend effects as separate observation surfaces. Use explicit test IDs when user-facing semantics are insufficient or ambiguous rather than forcing fake semantics into the product.

Flag positional DOM selectors, deep CSS chains and absolute XPath as potential implementation coupling when a stable product contract exists, but do not ban them when DOM/styling structure is itself the contract.

A semantic/accessibility snapshot can detect regressions that visual snapshots miss; a visual snapshot can detect regressions semantic snapshots miss. Neither replaces the other.

Automated accessibility scanners are partial evidence. Zero detected violations is not complete accessibility proof.

Snapshot baseline updates require intent/provenance. Retries preserve first-failure evidence, and timeout inflation is not root-cause repair unless the authoritative latency contract changed.

## Token-aware evidence

Prefer compact structured summaries with retrievable raw artifacts. Never save tokens by hiding failures, skips/not-run, retries, limitations, environment/configuration, revision, fidelity, contradictions or unknowns.

## Provider neutrality

Core policy is framework/language/provider neutral. Adapters expose capabilities such as discovery, invocation enumeration, stable IDs, filtering, structured results, retries, coverage, traces, seeds and mutation evidence.

## Current maturity

`assertiva audit` and `assertiva improve` are the executable surface. They read pytest, Jest, Playwright and Maven runs, portable JUnit XML, mutation and coverage reports, and CI configuration from GitHub Actions, Azure Pipelines, GitLab CI and Jenkins; `audit --changed-since` selects tests from a revision-scoped impact graph (Python) and widens whenever impact is not proven; a local history adds stability and failure-fingerprint evidence. MCP is not implemented. Use the CLI for deterministic evidence and this Skill for reasoning about it (see Execution mode and the engine); STATUS.md holds the exact claim boundaries.
