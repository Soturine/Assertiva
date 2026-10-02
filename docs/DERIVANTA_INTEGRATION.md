# Derivanta Integration

Assertiva is independent from Derivanta, but the two projects have complementary responsibilities.

```text
Derivanta
  -> derives project context, requirements, risk and assurance needs
  -> identifies what must be demonstrated
  -> may activate Assertiva when test evidence is material

Assertiva
  -> discovers/classifies test capability
  -> audits/selects/runs/diagnoses/verifies test evidence
  -> returns normalized evidence, findings, limitations and unknowns

Derivanta
  -> composes that evidence with architecture, security, safety, release,
     UX, operational and other project-wide evidence
  -> decides whether the broader claim is supported
```

## Ownership boundary

### Derivanta owns
- broad engineering/project context;
- cross-domain audit and gap discovery;
- requirement/risk/assurance interpretation;
- deciding what claim needs evidence;
- composing test evidence with non-test evidence;
- project-wide recommendation and assurance-case reasoning.

### Assertiva owns
- test-suite quality analysis;
- adaptive/impact-aware test selection;
- test invocation/run identity;
- harness/fidelity classification;
- assertion/oracle/observation-surface analysis;
- semantic UI/browser test assurance;
- failure localization and flake evidence;
- mutation/negative-control/test-the-safety-net evidence;
- Test Evidence Graph semantics;
- compact test evidence records and limitations.

Neither project silently inherits authority from the other.

## Contract

A useful integration follows:

```text
Claim / gap
   ↓
Evidence requirement
   ↓
Capability request
   ↓
Test selection / execution / analysis
   ↓
Normalized evidence
   ↓
Finding + limitation + residual unknown
   ↓
Broader assurance decision
```

### Example

Derivanta finding:

```text
Claim:
"Settings modal is keyboard-operable."

Evidence needed:
- dialog has a meaningful semantic identity;
- keyboard can reach required controls;
- focus is contained while modal is active where the interaction model requires it;
- Escape closes;
- focus returns to trigger;
- pointer and keyboard paths produce equivalent required effects.
```

Assertiva may return:

```json
{
  "claim": "settings-modal-keyboard-operable",
  "evidence": [
    "role/name observation",
    "keyboard activation trace",
    "focus transition record"
  ],
  "result": "partially_supported",
  "limitations": [
    "screen-reader journey not executed"
  ]
}
```

Derivanta can then compose that with the project's actual accessibility requirement and other evidence. Assertiva does not independently declare the entire product accessible.

## Activation boundary

Derivanta may activate Assertiva when:
- tests exist and adequacy matters;
- a change needs affected-test selection;
- a failing E2E needs localization;
- refactor safety depends on the test safety net;
- flaky/retry-dependent behavior affects confidence;
- UI/browser evidence must distinguish visual, semantic, interaction or persistence claims;
- release/qualification claims depend materially on test execution.

Derivanta should not require Assertiva for every repository question. If test evidence is not material, broad project analysis remains a Derivanta concern.

## Evidence handoff

Handoff records should preserve:
- target revision;
- environment/configuration;
- test definition and invocation identity;
- selection basis;
- executed/not-run/skipped scope;
- assertion/observation surfaces;
- fidelity/harness;
- evidence class/provenance;
- artifact references;
- retries/attempts;
- limitations/unknowns.

A Derivanta consumer must not upgrade:
- heuristic finding -> deterministic fact;
- selected subset -> full regression evidence;
- automated accessibility scan -> full accessibility conformance;
- snapshot pass -> full UI correctness;
- simulated/in-process integration -> real target integration.

## Semantic UI handoff

For UI/browser findings, Assertiva may return:
- locator evidence;
- semantic role/name/state observations;
- keyboard/focus observations;
- visual evidence;
- browser state/network evidence;
- structural-mutation challenge results;
- snapshot update provenance;
- retry/flake attempt evidence.

Derivanta decides whether those observations satisfy the project's actual UX/accessibility/functional/release claim.

## Failure and abstention states

Assertiva may return:
- supported;
- partially supported;
- contradicted;
- blocked;
- unknown;
- unsupported capability.

Derivanta should preserve these distinctions rather than coercing all results into pass/fail.

If required adapter capability is missing, the correct handoff may be:

```text
UNKNOWN / evidence unavailable
```

not a guessed result.

## Independence

Assertiva must:
- work without Derivanta;
- retain its own canonical test-assurance owners/schemas/evals;
- avoid importing Derivanta's entire policy graph;
- expose stable evidence contracts that another orchestrator could consume.

Derivanta must:
- remain useful if Assertiva is unavailable;
- avoid making Assertiva the owner of non-test project policy;
- be able to consume another evidence provider when needed.

## Relationship

- [Assertiva Semantic UI and Browser Assurance](SEMANTIC_UI_AND_BROWSER_ASSURANCE.md)
- [Assertiva Architecture](ARCHITECTURE.md)
- [Assertiva Evidence Contract](EVIDENCE_CONTRACT.md)
- [Assertiva Status](../STATUS.md)
- Derivanta canonical test-assurance owner: `assurance/ADAPTIVE_TEST_ASSURANCE.md`
