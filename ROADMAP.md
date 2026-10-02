# Roadmap

## M0 — Skill foundation
- [x] provider-neutral SKILL.md
- [x] quality model
- [x] adaptive execution protocol
- [x] diagnostics D0–D4
- [x] E2E decomposition
- [x] Test Evidence Graph semantics
- [x] schemas/examples
- [x] benchmark research
- [x] eval catalog
- [x] JUnit summarizer
- [x] validator + CI

## M0.1 — Deterministic semantic foundation
- [x] evidence tiers E0–E4
- [x] test definition vs invocation identity
- [x] multi-metric coverage model
- [x] parameterized/data-driven semantics
- [x] property/fuzz/metamorphic reproducibility semantics
- [x] structured error/validation contract model
- [x] capability-driven adapter contract
- [x] refactor readiness / whole-project safety model
- [x] harness/fidelity model independent from test labels
- [x] assertion/oracle/observation-surface model
- [x] fixture/factory/test-data lifecycle model
- [x] test-double/patch/service-virtualization model
- [x] web/API/UI/browser evidence model
- [x] canonical semantic UI/browser assurance owner
- [x] UI locator evidence schema + example
- [x] semantic UI grader-ready eval contract/cases
- [x] cross-platform semantic mapping and Derivanta interoperability contract
- [x] Skill + CLI + optional MCP architecture benchmark
- [x] adversarial evals for parameter collapse, line-coverage overclaim, structured error drift, heuristic overreach and whole-project refactor safety
- [ ] deterministic coverage report parsers
- [ ] normalized schema validation in CI

## M1 — Deterministic adapters
- [ ] pytest adapter
- [ ] Jest/Vitest adapter
- [ ] Playwright adapter
- [ ] Playwright semantic-locator/accessibility-tree extraction
- [ ] ARIA/accessibility snapshot normalization
- [ ] locator robustness and implementation-coupling analysis
- [ ] keyboard/focus evidence extraction
- [ ] JUnit/Gradle/Maven adapter
- [ ] .NET adapter
- [ ] normalized discovery/result records
- [ ] portable JUnit XML / TAP ingestion
- [ ] LCOV / Cobertura / JaCoCo-style coverage ingestion
- [ ] parameterized/dynamic invocation preservation
- [ ] structured error normalization
- [ ] property/fuzz seed/counterexample normalization
- [ ] capability discovery instead of hardcoded verbosity
- [ ] secret/redaction tests

## M2 — Impact intelligence
- [ ] Git diff + symbol extraction
- [ ] import/dependency graph
- [ ] runtime coverage/test-to-code ingestion
- [ ] selector confidence/limitations
- [ ] conservative widening
- [ ] monorepo affected-set support
- [ ] Test Evidence Graph builder

## M3 — Suite quality intelligence
- [ ] deterministic weak/no-op patterns where provable
- [ ] advisory semantic weak-assertion analysis with provenance
- [ ] mock-away heuristics
- [ ] duplicate/redundancy analysis
- [ ] fidelity/level classification
- [ ] mutation ingestion/orchestration
- [ ] test-smell adapters
- [ ] UI selector structural-mutation challenge harness
- [ ] snapshot baseline provenance analysis
- [ ] retry/timeout/first-failure flake analysis
- [ ] defect-to-test history

## M4 — Failure intelligence
- [ ] failure fingerprinting/clustering
- [ ] E2E stage mapping
- [ ] smallest-reproducer suggestions
- [ ] flake/history tracking
- [ ] duration/cost model
- [ ] diagnostic escalation automation

## M4.1 — Harness and runtime intelligence
- [ ] automatic harness/fidelity classification with provenance
- [ ] fixture lifecycle/shared-state detection
- [ ] patch/mock seam tracing and unused setup detection
- [ ] HTTP/UI observation-surface extraction
- [ ] environment/browser/device matrix preservation
- [ ] transaction-semantics capability detection

## M5 — Productization
- [ ] CLI
- [ ] CLI-first local agent interface
- [ ] optional MCP server with atomic paginated tools/resources
- [ ] long-analysis job/task lifecycle and cancellation
- [ ] revision-aware local evidence/history store
- [ ] CI integration
- [ ] provider adapters
- [ ] persistent history
- [ ] project policy/config

## M6 — Empirical validation
- [ ] paired baseline vs Assertiva trials
- [ ] Python/pytest benchmark
- [ ] JS/Jest/Vitest benchmark
- [ ] Playwright benchmark
- [ ] Android/Gradle/JUnit benchmark
- [ ] Java benchmark
- [ ] .NET benchmark
- [ ] Django benchmark
- [ ] monorepo benchmark
- [ ] measure tokens, runtime, reruns, CI work, defect recall, false positives
- [ ] adversarial selector-blind-spot fixtures
- [ ] prospective real-project dogfood

Milestones may reopen when new evidence exposes reusable gaps.
