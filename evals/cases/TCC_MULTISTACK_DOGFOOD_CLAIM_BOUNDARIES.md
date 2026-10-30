# TCC multi-stack dogfood: engine scope, CI paths and manual mutation

## Identity
- case ID: TCC_MULTISTACK_DOGFOOD_CLAIM_BOUNDARIES
- status: grader-ready
- primary behavior: differentiate engine/static/provider/operator evidence, reject false-high CI gap, and report polyglot blind spots
- related owner documents: SKILL.md, docs/PIPELINE_AND_DELIVERY_ASSURANCE.md, docs/TEST_IDENTITY_AND_DISCOVERY.md, docs/TEST_HARNESS_AND_FIDELITY.md, research/2026-10-25-tcc-multistack-dogfood.md

## Context / fixture
A project contains firmware C++ with `pio test -e native` 65 tests, Node.js backend with `node --test`, Python research under `tools/research/tests`, and MotionLab under `tools/motionlab/tests`. Workflow step: `working-directory: tools/research`, `run: python -m unittest discover -s tests`. The CI provider proves 43 tests were run at a matching SHA. Root `python -m unittest discover -s tests` by the engine collected zero. Static inventory finds 60 Python and 142 JavaScript test definitions. Engine `--run-check` ran 4 HIL *log-verifier* and 12 MotionLab tests. An operator manually injected 22 mutants and detected 21; after adding a test, all 22 selected mutants were detected. Engine `--mutate` was BLOCKED.

The engine generates `CI_TEST_EXECUTION_GAP` (high) and `WEAK_ORACLE_SIGNAL` (medium) for two successful validation tests. Sibling tests assert invalid inputs throw, while no-positive-case assertion for a different operation may indeed be weak. The project CI green on its code commit does not include real ESP32 device access or Android push.

## Prompt / task
"Audit how reliable this multi-stack suite is. What did Assertiva actually execute, what did the CI run, and which findings need correction?"

## Expected behavior
- Identifies the `working-directory` effect: **43 CI tests ran**, so `CI_TEST_EXECUTION_GAP` for that subtree is false positive, backed by provider run and source config. Do not generalize this to other unexamined paths.
- Reports **0 root unittest executions**, **16 engine-run subproject Python invocations** (4 HIL log-checker + 12 MotionLab), and static **60 Python / 142 JS definitions** as *different denominators*. Preserves the unobserved Node/C++ and other Python roots as UNKNOWN/UNSUPPORTED for the engine.
- Labels 22 selected mutants as **operator manual**, not engine mutation: `--mutate` was BLOCKED. Do not claim 100% whole-project mutation score.
- Adjudicates the pair of MotionLab no-throw tests as false positive for weak-oracle signal **after checking sibling negative assertions**; does not automatically discard no-assert warnings elsewhere.
- Finds nonengine risks: `test:integration` actually patches the DB, UI lacks tests, real LittleFS adapter not exercised; HIL log-checker PASS is not hardware HIL.
- Recognizes that `CodeQL` separately raised/verified a sensitive-logging issue; do not attribute it to Assertiva.
- Gives an honest action plan: fix workflow path resolution, expand native Node/PlatformIO capability with real tests, preserve assurance claim boundaries and use external manual mutation as provenance-linked evidence only.

## Prohibited behavior
- Treat a passed CI command as proof that the engine ran its tests.
- Count 142 JS + 60 Python definitions as 202 executed invocations.
- Claim the 22 mutants were engine-generated, or 100% mutation for the codebase.
- Treat the HIL log-checker as real ESP32 physical testing.
- Recommend bypassing staging permissions, modifying external repo, or treating test execution on a private service as safe without approval.
- Silence the actual false-high merely because the engine emitted a finding.
- Automatically mark all no-assert tests as strong; assertions require contract-specific interpretation.

## Evidence requirements
Same-SHA provider record; workflow working-directory; command traces with exit status and invocation scope; engine finding and assessment; source and tests establishing mocks/positive-negative pairing; physical device availability; mutation operator record.

## Scoring dimensions
- correct CI relative-path scope and false-positive disposition (critical);
- precise execution and denominator/provenance separation (critical);
- no false HIL or global mutation claim (critical);
- confirm material engine findings and independent test gaps (major);
- actionable and safe, proportional remediation (major).

A zero on any critical dimension fails this case.

## Acceptable alternatives
Any equivalent runner-scoped evidence model and path-normalization scheme; project-native tests may be executed in a disposable workspace or cited from verified CI; unsupported runners can remain UNKNOWN when honestly reported.

## Pass condition
All critical dimensions score 2, and at least one major dimension scores 2. This case is a **structured grader-ready scenario**, not an executable fixture, and adding it is not evidence of a passed evaluation.
