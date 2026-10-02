# Assertiva Documentation

This is the human documentation portal for Assertiva. Stable policy belongs in `SKILL.md` and canonical owner documents; dated ecosystem facts belong in `research/`; executable state is tracked in `STATUS.md` and `ROADMAP.md`.

## Start here

- [Architecture](ARCHITECTURE.md) — layers, records, trust model and execution boundaries.
- [Quality Model](QUALITY_MODEL.md) — what makes test evidence meaningful.
- [Determinism and Evidence Tiers](DETERMINISM_AND_EVIDENCE_TIERS.md) — E0–E4 provenance/authority model.
- [Evidence Contract](EVIDENCE_CONTRACT.md) — compact evidence and claim discipline.
- [Refactor Safety](REFACTOR_SAFETY.md) — behavior protection and readiness.
- [Semantic UI and Browser Assurance](SEMANTIC_UI_AND_BROWSER_ASSURANCE.md) — semantic contracts, locators, accessibility tree, keyboard/focus, snapshots, structural mutation and browser flake evidence.
- [Derivanta Integration](DERIVANTA_INTEGRATION.md) — cross-project ownership and evidence handoff.
- [Verification Surface](VERIFICATION_SURFACE.md) — language/framework-neutral model for every check that contributes to or blocks delivery confidence.
- [Executable Assurance Core](EXECUTABLE_ASSURANCE_CORE.md) — implemented M0.2 TDD vertical slice and current claim boundaries.
- [Pipeline & Delivery Assurance](PIPELINE_AND_DELIVERY_ASSURANCE.md) — local/CI/build/package/deploy evidence and false-green prevention.
- [FTD/FTE Interoperability](FTD_FTE_INTEROPERABILITY.md) — optional Test Case authority and Azure handoffs.

## Test identity, selection and execution

- [Test Identity and Discovery](TEST_IDENTITY_AND_DISCOVERY.md)
- [Impact and Selection](IMPACT_AND_SELECTION.md)
- [Failure Localization](FAILURE_LOCALIZATION.md)
- [Test Harness and Fidelity](TEST_HARNESS_AND_FIDELITY.md)
- [Test Modalities](TEST_MODALITIES.md)
- [Coverage Model](COVERAGE_MODEL.md)

## Assertions, data and doubles

- [Assertions, Oracles, and Observation Surfaces](ASSERTIONS_ORACLES_AND_OBSERVATION_SURFACES.md)
- [Error Contracts](ERROR_CONTRACTS.md)
- [Parameterized, Property, and Fuzz](PARAMETERIZED_PROPERTY_AND_FUZZ.md)
- [Test Data, Fixtures, and Factories](TEST_DATA_FIXTURES_FACTORIES.md)
- [Test Doubles, Patching, and Virtualization](TEST_DOUBLES_PATCHING_AND_VIRTUALIZATION.md)

## Web / UI

- [Web, API, UI, and Browser Testing](WEB_API_UI_TESTING.md)
- [Semantic UI and Browser Assurance](SEMANTIC_UI_AND_BROWSER_ASSURANCE.md)

## Product architecture

- [Agent Skill, CLI, and MCP Architecture](AGENT_SKILL_MCP_ARCHITECTURE.md)

## Evidence, schemas and evals

- [Research Index](../research/README.md) — dated evidence, not permanent policy.
- [Eval Catalog](../evals/README.md)
- [Eval Case Contract](../evals/CASE_SPEC.md)
- `../schemas/` — normalized machine-readable records.
- `../examples/` — example normalized records.

## Authority rule

When documents overlap:
1. `SKILL.md` governs agent behavior and claim boundaries.
2. A dedicated owner document governs its topic.
3. `STATUS.md` governs implemented vs specified state.
4. `ROADMAP.md` governs planned work.
5. Research records are dated evidence and may become stale.
6. Eval cases test expected behavior; they do not create new product policy by themselves.
