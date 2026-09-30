# Architecture

Assertiva is a test-intelligence layer above existing runners and below agents/CI orchestration.

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
 normalized test/evidence model
          |
 runner/framework adapters
          |
pytest / Jest / Vitest / Playwright / JUnit / Gradle / .NET / ...
~~~

Assertiva does not replace test frameworks.

## Layers
1. SKILL.md owns agent behavior and claim boundaries.
2. scripts/ owns deterministic repetitive parsing/validation/summarization.
3. schemas/ owns normalized records.
4. future adapters translate runner-specific capabilities without redefining assurance semantics.
5. raw evidence may stay outside model context with retrievable references.
6. agent reasoning interprets oracle authority, uncertainty, and claim strength.

## Core records
- TestInventoryEntry — identity, level, framework, source, target/component, tags.
- TestRun — revision/environment/configuration, selection basis, status, timing.
- FailureEvidence — assertion/exception/location/cluster/diagnostic level/artifact refs.
- SelectionDecision — candidates, reasons, methods, limitations, expansion triggers.
- TestEvidenceEdge — requirement/behavior/component/code/test/assertion/evidence/run relation.
- SuiteFinding — weak-test/fidelity/redundancy/oracle gap with evidence.

## Trust model
No selector, graph, coverage map, LLM inference, or mutation score is authoritative by itself. Derived relationships should carry provenance, source/method, revision/time window, confidence and limitations.

When uncertainty is material, widen evidence.

## Security/privacy
Diagnostics can expose secrets through locals, env vars, HTTP headers, DB payloads, screenshots, URLs and traces. Adapters should redact common secret classes, avoid dumping all locals by default, protect raw artifacts, and record that redaction occurred.
