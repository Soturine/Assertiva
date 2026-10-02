# Semantic UI and Browser Assurance

**Authority:** canonical Assertiva owner for semantic UI/browser test assurance.  
**Purpose:** define how Assertiva reasons about human-facing UI contracts, locators, accessibility semantics, keyboard/focus behavior, snapshots, browser state, selector robustness, and UI-specific false-green risks without becoming Playwright- or web-only.

This document complements [Web, API, UI, and Browser Testing](WEB_API_UI_TESTING.md), [Assertions, Oracles, and Observation Surfaces](ASSERTIONS_ORACLES_AND_OBSERVATION_SURFACES.md), [Test Harness and Fidelity](TEST_HARNESS_AND_FIDELITY.md), and [Refactor Safety](REFACTOR_SAFETY.md).

## Core principle

A UI test should be explicit about **which observable contract it proves**.

```text
pixels
!= DOM structure
!= semantic/accessibility tree
!= keyboard/focus behavior
!= pointer interaction
!= application state
!= persistence/network effect
```

These surfaces can corroborate one another, but none automatically substitutes for the others.

A user-facing interface may expose several contracts at once:

```text
Requirement
  -> user-visible behavior
     -> semantic identity
        -> input behavior
           -> state transition
              -> visual result
                 -> persistence/network effect
                    -> evidence
```

Assertiva should preserve those distinctions so a green test cannot silently overclaim more than it observed.

## Semantic interface contract

A **semantic interface contract** is the stable meaning a user or platform can rely on independently of incidental implementation structure.

Examples include:
- a button whose purpose is "Save";
- a textbox associated with "Email";
- a tab whose selected state changes;
- a dialog with a meaningful accessible name;
- a switch exposing on/off state;
- a mobile Compose node with role/state/action semantics;
- a desktop/native control exposed through the platform accessibility tree;
- an explicit test identity when user-facing semantics are insufficient or intentionally unstable.

The contract is not automatically the same as:
- a CSS class;
- a wrapper hierarchy;
- a generated DOM path;
- an `nth-child` position;
- a screenshot region;
- a framework component name;
- a test ID.

Any of those can still be legitimate contract surfaces when the product or test explicitly owns them.

## Native semantics before synthetic semantics

Prefer native platform behavior where it already represents the intended control.

For web:
- semantic HTML usually provides role, behavior, keyboard integration and accessibility mapping more reliably than recreating the same control with generic elements;
- ARIA can expose or refine semantics for custom/composite widgets, but a role is a behavioral promise rather than a styling annotation;
- ARIA must not be added solely because a test locator is inconvenient.

For Jetpack Compose:
- semantics are shared infrastructure for accessibility services, autofill and UI testing;
- Material/Foundation components already expose substantial semantics;
- custom semantics should describe the actual component contract, not fabricate a test-only meaning.

For other native platforms, use the platform accessibility/automation semantics and keep the same policy boundary: product semantics are product behavior; test-only identity is a different contract.

## Locator strategy

Locator quality is contextual. Assertiva should not assign a universal numeric score merely from syntax.

When the target exposes a stable user-observable identity, a useful preference order is:

1. semantic role + accessible name, associated label, or equivalent native semantic query;
2. stable visible/domain identity that is materially part of the user contract;
3. explicit test contract such as `data-testid`, Compose `testTag`, or platform-equivalent identifier when semantic identity is insufficient, ambiguous, intentionally localized, or not the contract being tested;
4. stable domain attributes intentionally exposed for automation/integration;
5. CSS/XPath/positional structure tied to the current implementation.

This order is guidance, not a ban.

### Legitimate exceptions

A structural locator/assertion can be correct when:
- layout/DOM structure is itself the behavior under test;
- a design-system class or state class is a public contract;
- identical repeated elements can only be distinguished by order and order is itself meaningful;
- a test is intentionally characterizing current implementation before refactor;
- a browser/framework does not expose a better stable identity.

A test ID can be preferable when:
- visible copy is localized or frequently edited;
- several controls have identical semantics but distinct domain identities;
- virtualized/recycled content makes visible structure unstable;
- the automation contract is intentionally independent from presentation wording.

The finding should explain **why** a selector is coupled, not merely label a locator family as bad.

## Accessible role, name, description, and state

Treat semantic properties as separately observable facts when they matter:

- role/type;
- accessible name;
- accessible description;
- checked/toggle state;
- selected state;
- expanded/collapsed state;
- pressed state;
- disabled/read-only state;
- invalid/error state;
- busy/loading state;
- heading level;
- live/status announcements;
- relationships such as controls/described-by/labelled-by where relevant.

An element existing in the DOM does not prove these semantics are correct.

A semantic locator succeeding also does not prove the complete user journey. It may establish identity while persistence, authorization, rendering, or network effects still require independent assertions.

## Keyboard and focus are first-class evidence

Pointer success and keyboard success are different observations.

For components where keyboard operation is material, inspect the applicable subset of:
- reachability;
- activation keys;
- navigation keys;
- focus order;
- focus visibility;
- focus entry into overlays/dialogs;
- focus containment where required;
- Escape/dismissal behavior;
- focus restoration to the triggering context;
- roving tabindex/active-descendant behavior for composite widgets;
- keyboard alternatives for drag/precise pointer interaction.

Do not "fix" a keyboard defect by adding only a role or label.

## Visual evidence

Visual regression evidence is valid for appearance claims:
- geometry/layout;
- spacing;
- typography;
- colors;
- clipping/overflow;
- icon/image rendering;
- responsive breakpoints;
- theme/high-contrast/reduced-motion states where captured.

It does not prove:
- accessible naming;
- keyboard support;
- DOM semantics;
- persistence;
- authorization;
- network/server effects.

The reverse is also true: a semantically correct accessibility tree can coexist with a visual regression.

## Accessibility scanners and conformance claims

Automated scanners such as axe-style rule engines are useful deterministic detectors for the rules, page state, configuration and scope they actually evaluate.

Preserve:
- engine/tool version;
- ruleset/tags;
- included/excluded regions;
- page state;
- browser/runtime;
- suppressions/exceptions;
- violations and incomplete/manual-review items.

Do not infer:
- full WCAG conformance from zero automated violations;
- successful screen-reader use from accessibility-tree assertions alone;
- successful usability from standards checks alone.

When a conformance claim matters, bind it to the relevant standard/version/level and the evidence required by that claim.

## ARIA/accessibility snapshots

Semantic snapshots can efficiently detect changes to role/name/state/hierarchy.

They are useful when:
- a stable semantic subtree is the intended contract;
- individual assertions would be repetitive;
- review diffs remain small and understandable.

They are risky when:
- the snapshot is huge;
- unrelated content churn dominates the diff;
- localization/dynamic data creates noisy baselines;
- an agent can auto-accept the entire baseline without understanding the change.

Treat a semantic snapshot like any other snapshot: a change is evidence to inspect, not a self-authorizing new oracle.

## Snapshot and golden authority

Every snapshot/golden baseline should have an answer to:

1. What contract does this baseline represent?
2. Why is the old baseline authoritative?
3. Why is the proposed new baseline intended?
4. Which unrelated differences are excluded or separately reviewed?
5. What action/tool generated the update?
6. What independent evidence supports the change when consequence warrants it?

A command such as an update-snapshots mode changes the oracle. It does not prove the new oracle is correct.

## Structural mutation / refactor-resilience challenge

Assertiva may challenge a browser/UI test by applying or simulating a **non-behavioral structural mutation**.

Candidate mutations:
- insert harmless wrapper elements;
- rename internal classes not owned as public contracts;
- alter equivalent container composition;
- change incidental DOM nesting;
- reorder implementation-only wrappers;
- replace internal component boundaries while preserving user behavior.

A robust behavior-contract test should usually survive those changes.

If it fails, classify:
- likely implementation coupling;
- legitimate structural-contract test;
- ambiguous / more evidence required.

### Guardrail

A structural mutation challenge is not allowed to redefine the product behavior it is supposed to preserve.

Before interpreting a failure, verify that the mutation retained the relevant:
- semantic identity;
- visible/domain identity;
- interaction;
- state transition;
- persistence/network effect;
- required appearance contract.

## Retry, timeout, waiting, and flake

Retries are evidence about repeated attempts, not an eraser.

Preserve:
- attempt number;
- first failure;
- later outcomes;
- timing;
- revision/environment;
- trace/artifact references;
- retry policy;
- locator/wait condition;
- backend/network state where relevant.

A timeout increase can be legitimate when:
- a documented latency envelope changed;
- a slow environment has an explicit policy;
- a long-running operation is intentionally within the new bound.

It is not, by itself, evidence that the root cause of:
- a race;
- missing synchronization;
- async completion ambiguity;
- slow regression;
- overloaded dependency;
- environment instability
has been fixed.

Prefer waiting on authoritative state/conditions over arbitrary sleeps.

## Browser state and side effects

UI tests can observe more than rendered controls.

Applicable evidence may include:
- URL/history/navigation;
- cookies/session;
- local/session storage;
- IndexedDB/cache;
- request/response and headers;
- emitted events/messages;
- server persistence/readback;
- authorization/no-op effects;
- telemetry when the claim depends on it.

Do not let a successful click stand in for an unobserved backend effect.

## Cross-platform semantic mapping

Assertiva core uses portable concepts. Adapters translate them.

| Portable concept | Web/browser example | Android Compose example | Other native platforms |
| --- | --- | --- | --- |
| semantic role | HTML/ARIA role | `Role` semantics | platform accessibility role/trait |
| semantic name | label/text/accessible name | text/content description/semantics | platform accessibility label/name |
| semantic state | checked/expanded/selected/etc. | toggleable/stateDescription/selected/etc. | platform accessibility state/value |
| test-only identity | `data-testid` | `testTag` | automation/accessibility identifier where appropriate |
| interaction | click/type/keyboard | performClick/input/semantics actions | platform UI automation action |
| focus/navigation | browser focus + keyboard | focus semantics/input | platform focus/navigation APIs |
| semantic tree | accessibility tree / ARIA snapshot | Compose semantics tree | platform accessibility hierarchy |

Adapter-specific names are examples, not core policy.

## Structured evidence

The canonical locator-analysis record is [`ui-locator-evidence.schema.json`](../schemas/ui-locator-evidence.schema.json).

An observation may use [`assertion-observation.schema.json`](../schemas/assertion-observation.schema.json) with:
- a broad `surface`;
- optional `subsurface`;
- platform/framework identity;
- expected vs actual observation;
- evidence references.

Example:

```json
{
  "observation_id": "obs-delete-name",
  "surface": "accessibility",
  "subsurface": "accessible_name",
  "platform": "web",
  "framework": "playwright",
  "expected": "Excluir projeto",
  "actual": null
}
```

## Adapter expectations

A UI/browser adapter should expose capabilities rather than pretending every framework supports the same features.

Possible capabilities:
- semantic/role locator discovery;
- test-ID locator discovery;
- accessibility-tree extraction;
- semantic snapshot extraction;
- keyboard/focus observation;
- screenshot/visual artifact capture;
- trace/video capture;
- browser storage inspection;
- network inspection;
- retry/attempt identity;
- snapshot update provenance;
- source-locator extraction.

Unsupported capabilities remain `UNSUPPORTED` or `UNKNOWN`; they must not be fabricated.

## Finding classes

Useful findings include:
- `implementation_coupled_locator`;
- `missing_semantic_identity`;
- `semantic_state_not_asserted`;
- `pointer_keyboard_divergence`;
- `focus_contract_regression`;
- `visual_semantic_divergence`;
- `snapshot_oracle_auto_accepted`;
- `accessibility_scan_overclaim`;
- `retry_masks_first_failure`;
- `timeout_inflation_without_contract`;
- `ui_effect_unobserved`;
- `test_id_legitimate_explicit_contract`.

Findings should include evidence and limitations; the presence of a pattern does not automatically mean a defect.

## False-green examples

### Visual green, semantic red

```text
Screenshot: PASS
Click with mouse: PASS
Accessible name: missing
Keyboard activation: FAIL
```

The appearance evidence remains valid. The UI claim is still incomplete.

### Semantic green, persistence red

```text
getByRole("button", {name:"Save"}): PASS
click: PASS
toast "Saved": PASS
server readback: old value
```

Semantic identity and interaction passed; persistence did not.

### Retry green, root cause unknown

```text
attempt 1: timeout
attempt 2: pass
suite exit: green
```

The run is green under retry policy, but nondeterminism remains evidence requiring classification.

## Claim boundaries

Do not claim:
- "accessible" from ARIA presence alone;
- "WCAG compliant" from one scanner;
- "robust selector" from locator syntax alone;
- "fixed" because a snapshot was updated;
- "flake fixed" because retries pass;
- "user journey correct" because a semantic locator found an element;
- "cross-browser compatible" from one engine/environment.

Report exactly what was observed.

## Relationships

- [Web, API, UI, and Browser Testing](WEB_API_UI_TESTING.md)
- [Assertions, Oracles, and Observation Surfaces](ASSERTIONS_ORACLES_AND_OBSERVATION_SURFACES.md)
- [Test Harness and Fidelity](TEST_HARNESS_AND_FIDELITY.md)
- [Refactor Safety](REFACTOR_SAFETY.md)
- [Determinism and Evidence Tiers](DETERMINISM_AND_EVIDENCE_TIERS.md)
- [Derivanta Integration](DERIVANTA_INTEGRATION.md)
- [Research: Semantic UI and Browser Test Assurance](../research/2026-10-02-semantic-ui-browser-assurance.md)
- [Eval Contract](../evals/CASE_SPEC.md)

## Maturity

The semantic model, schemas and eval expectations are specified and usable for agent-guided audits. First-party Playwright extraction, accessibility-snapshot normalization, structural mutation execution, cross-run flake intelligence and native-platform adapters remain roadmap work unless STATUS.md says otherwise.
