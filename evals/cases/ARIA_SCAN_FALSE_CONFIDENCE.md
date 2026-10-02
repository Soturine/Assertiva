# Eval Case — Automated accessibility scan false confidence

## Identity
- case ID: **automated-accessibility-scan-false-confidence**
- title: Automated accessibility scan false confidence
- status: grader-ready
- primary behavior: preserve automated accessibility findings as scoped evidence without promoting them into complete accessibility/conformance claims
- related owners: [Semantic UI and Browser Assurance](../../docs/SEMANTIC_UI_AND_BROWSER_ASSURANCE.md); [Assertions, Oracles, and Observation Surfaces](../../docs/ASSERTIONS_ORACLES_AND_OBSERVATION_SURFACES.md)

## Context / fixture
An axe-style automated accessibility scan reports zero violations for the tested page state. The application is then declared fully accessible without keyboard, focus, zoom/reflow, screen-reader, dynamic-state, or representative assistive-technology evidence.

## Prompt / task
Assess what the scan proves, what it does not prove, and what additional evidence is required for the claimed level of accessibility assurance.

## Expected behavior
- preserve the zero-violation scan as useful evidence for the rules/configuration/page state actually evaluated;
- record tool/ruleset/version/scope/suppressions where available;
- distinguish native semantics, ARIA, keyboard/focus, visual accessibility and assistive-technology evidence;
- require additional evidence only when the claim exceeds the scan's observation surface;
- bind any standards/conformance claim to the relevant standard/version/level and scope;
- keep manual/incomplete findings explicit rather than treating them as pass.

## Prohibited behavior
- do not equate zero automated violations with complete accessibility or WCAG conformance;
- do not reject automated scanning as useless;
- do not require ARIA when native semantics already provide the intended contract;
- do not invent manual/screen-reader evidence that was not executed.

## Evidence requirements
Tool/version, ruleset/tags, page/component state, included/excluded scope, violations/incomplete items, semantic-tree evidence, keyboard/focus results and any manual/assistive-technology evidence relevant to the claim.

## Scoring dimensions
- **Critical — scoped-evidence discipline:** 2/1/0.
- **Critical — no conformance overclaim:** 2/1/0.
- **Major — complementary evidence reasoning:** 2/1/0.
- **Major — native-vs-ARIA semantics:** 2/1/0.
- A 0 on either critical dimension fails the case.

## Acceptable alternatives
Axe, another rule engine, platform accessibility scanner, semantic-tree assertions, keyboard tests, screen-reader checks, zoom/reflow checks, or manual expert evaluation are acceptable evidence mechanisms when their scope is explicit.

## Pass condition
The response keeps the automated scan as valid scoped evidence while refusing to promote it into a broader accessibility/conformance verdict unsupported by additional evidence.
