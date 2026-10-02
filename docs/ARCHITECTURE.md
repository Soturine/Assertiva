# Architecture

Assertiva is a verification-intelligence and test-assurance layer above existing tools/runners and below agents/CI/CD orchestration. Tests are a major evidence source, not the only one.

~~~text
Coding Agent / CI / Human
          |
       Assertiva
          |
  +-------+--------+----------------+
  |       |        |                |
Audit   Select   Diagnose          Verify
  |       |        |                |
  +-------+--------+----------------+
          |
 normalized verification/evidence model
          |
 capability-driven adapters
          |
tests / lint / typecheck / build / package / schema / migration /
security / hooks / CI/CD / startup / health / deploy / custom checks
~~~

Assertiva does not replace test frameworks, linters, build systems, CI/CD platforms, deployment systems or other validators. It normalizes and reasons over the evidence they produce.

## Layers
1. SKILL.md owns agent behavior and claim boundaries.
2. scripts/ owns deterministic repetitive parsing/validation/summarization.
3. schemas/ owns normalized records.
4. future adapters translate runner-specific capabilities without redefining assurance semantics.
5. raw evidence may stay outside model context with retrievable references.
6. agent reasoning interprets oracle authority, uncertainty, and claim strength.

## Deterministic core and advisory intelligence

```text
RAW ARTIFACTS
   ↓
DETERMINISTIC PARSERS / NORMALIZERS
   ↓
NORMALIZED EVIDENCE
   ├─ deterministic selection / exact mappings
   ├─ project-declared mappings/policy
   └─ advisory heuristic/LLM analysis
                    ↓
             decision / expansion
```

Heuristic or LLM output must not silently become deterministic fact. Derived graph edges, findings and selection reasons carry evidence class and provenance.

## Core records
- VerificationCheck — one discovered validation/gate/check with kind, command/tool, origin, scope, blocking semantics, evidence class and limitations.
- VerificationSurface — the revision-scoped inventory of checks observed across local workflows, hooks, CI/CD, packaging and deployment.
- TestInventoryEntry — definition identity, runner/framework, source, level/fidelity, dynamic/parameterized characteristics and tags.
- TestInvocation — concrete parameter/data/dynamic invocation identity plus attempt/retry.
- TestRun — revision/environment/configuration, selection basis, status, timing.
- FailureEvidence — assertion/exception/location/cluster/diagnostic level/artifact refs.
- SelectionDecision — candidates, reasons, methods, limitations, expansion triggers.
- TestEvidenceEdge — requirement/behavior/component/code/test/assertion/evidence/run relation with evidence class/provenance.
- CoverageRecord — metric kind, totals, scope, exclusions, tool/version and artifact provenance.
- ErrorExpectation — structured expected failure category/type/code/path/context/message policy.
- TestHarness — actual process/transport/persistence/transaction/dependency/UI/isolation fidelity dimensions.
- AssertionObservation — claim-facing observation surface and oracle source.
- UILocatorEvidence — locator strategy, observed semantic/test contract, coupling classification, candidate alternatives, structural-mutation result and provenance.
- SemanticUIObservation — represented through AssertionObservation subsurface/platform/framework fields rather than a separate duplicate record.
- TestDataFixture — data source, scope, reset, seed/version and shared-state semantics.
- TestDouble — dummy/stub/fake/spy/mock/patch/virtualizer/emulator target boundary and claim impact.
- AdapterCapabilities — versioned SUPPORTED/UNSUPPORTED/UNKNOWN capability map.
- SuiteFinding — weak-test/fidelity/redundancy/oracle gap with evidence.

## Trust model
No selector, graph, coverage map, LLM inference, or mutation score is authoritative by itself. Derived relationships should carry provenance, source/method, revision/time window, confidence and limitations.

When uncertainty is material, widen evidence.

## Security/privacy
Diagnostics can expose secrets through locals, env vars, HTTP headers, DB payloads, screenshots, URLs and traces. Adapters should redact common secret classes, avoid dumping all locals by default, protect raw artifacts, and record that redaction occurred.

## UI/browser assurance ownership

[Semantic UI and Browser Assurance](SEMANTIC_UI_AND_BROWSER_ASSURANCE.md) owns locator, accessibility-tree, keyboard/focus, semantic snapshot, visual/semantic divergence, structural-mutation and browser-flake semantics. Adapter-specific extraction maps into the normalized records rather than redefining those rules.

## Product interfaces

See [Agent Skill, CLI, and MCP Architecture](AGENT_SKILL_MCP_ARCHITECTURE.md) for the intended separation between skill policy, deterministic core, CLI, optional MCP, project state and raw evidence artifacts.


## Universality boundary

Assertiva's **core semantics are universal; adapter support is incremental**.

The core must never contain policy such as "if pytest then confidence is X" or "GitHub Actions means CI is covered". Adapters may know native syntax and capabilities of a tool, runner, language or provider, but they normalize into generic records.

When no dedicated adapter exists, Assertiva should preserve project-declared or observed commands as CUSTOM/UNKNOWN verification checks with provenance. Unknown support must widen uncertainty, not produce a fake pass.

This allows projects in different languages and stacks to participate without forcing them into one framework vocabulary.
