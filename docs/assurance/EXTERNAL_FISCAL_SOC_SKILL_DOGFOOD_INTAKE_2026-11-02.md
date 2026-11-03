# Cross-repository dogfood intake — fiscal agents, RLS and detection effects (2026-11-02)

**Status: source-grounded evaluation proposal; runtime and agent executions NOT_RUN.** Baseline Assertiva v0.10.1, `main` `2618d95caa662e27de443b099d39dcd912a1b875`. No upstream code was modified or run, and no evidence of financial loss/security breach was established.

## Context
The [Elias2031 fiscal project wave](https://github.com/Elias2031) and user-supplied LinkedIn comments explicitly distinguish deterministic tax calculators from agents that adapt to changed portals, explain results and route exceptions. One commenter questioned 2027 CBS/IBS legal applicability and human accountability. The [DANTE SOC project](https://github.com/sg0luc/dante) describes rule cloning, homologation stages, tenant folders, long-lived exceptions and synthetic Loki logs. Earlier wave includes [Vizi PDV](https://github.com/nhatilla-integration/vizi-pdv), [Baixador Morpho](https://github.com/Elias2031/baixador-morpho) and [NFS-e simulator](https://github.com/nhatilla-integration/nfse-simulador). These are read-only comparative sources, not ready-made test fixtures or proof of production performance.

## Test-quality opportunities and correct owners

| ID | Candidate false green or test limitation | What test must observe | Overlap guard |
|---|---|---|---|
| AX-W26-01 | Test of fiscal recovery asserts a generated number but expected amount repeats the same buggy rule or uses a future rate | Independent accountant-approved period/UF/regime oracle, script/hash/inputs, rounding/edge examples; human sign-off for actual filing | Existing `HIGH_COVERAGE_WEAK_ORACLE`, `INDIRECT_ORACLE_CONTRACTS`; new semantic case tests temporal legal validity |
| AX-W26-02 | RLS test asserts error/denial or zero rows but not absence of side effects; no positive role flow | Before/after DB state, audit records, allowed owner/role behavior, cross-tenant negative | Existing `HTTP_STATUS_ONLY_FALSE_GREEN` and `TRANSACTION_HARNESS_MASKS_COMMIT_BEHAVIOR`; no universal rule declaring 2xx weak |
| AX-W26-03 | Grafana provisioning test checks HTTP 200 on rule clone, not active contact point or notification when silence matches | Independent query of effective stage/UID/paused state/silence and authorized synthetic event-to-alert path | Existing `STALE_RUN_VERDICT`; no assertion that live SOC is misconfigured |
| AX-W26-04 | Retry test only checks that Celery requeues work, not that external Onvio-like operation is idempotent after lost ACK | Receiver-side keyed effect and reconciliation after forced crash, bounded retries, stuck PROCESSANDO recovery | Existing `RETRY_TIMEOUT_FALSE_REPAIR`, `MOCK_AWAY_INTEGRATION_BOUNDARY` |
| AX-W26-05 | Simulated NFS-e test depends on `Math.random()` and only covers happy path, while two stores can partially fail | Injectable RNG/time and deterministic status branches; targeted fault at cross-store boundary | Existing `FIXTURE_STATE_LEAK_ORDER_DEPENDENCY`, `MUTATION_SURVIVOR` |
| AX-W26-06 | Agent Skill test passes by repeating instructions without activating Skill or using tools correctly | Real client routing trace, authorized runner evidence, negative no-activation case | Existing `ENGINE_UNAVAILABLE_SEMANTIC_ONLY`; agent eval separate from engine tests |

## Changes admitted to Assertiva
- Add three narrow **semantic cases**, not new automatic static findings: fiscal temporal oracle, denied-action/unchanged-state oracle and detection rule effective alert.
- Preserve candidate/UNKNOWN distinction; no assurance that source projects exhibit exploitable bugs.
- Use these to evaluate Assertiva's *agent reasoning* in an isolated fixture with hidden rubric. Do not claim the runtime can automatically validate tax law, Grafana notifications, Supabase permissions or paid APIs.
- Reuse Assertiva engine and adapter owners rather than adding fiscal calculators, SOC scanners, agent orchestration runtime or framework-specific code.

## Source-provenance and safety boundaries
- Read-only external source code / documentation and user-provided screenshots; no runtime, finance-client data, certificates, third-party access tokens or live permission probes.
- Official legislation and effective dates must be rechecked at time of a real fiscal test. Test only synthetic or authorized datasets.
- The [Framework intake PR #11](https://github.com/Soturine/Derivanta/pull/11) and [Engine M4 protocol PR #2](https://github.com/Soturine/Derivanta-Engine/pull/2) are cross-project proposals, not merged requirements or measured improvement.

## Follow-up gates
1. Semantic eval: independent evaluator and hidden criteria; record answer, provenance, negative control and allowed tools.
2. Runtime assessment: only if a distinct deterministic heuristic is justified by real labeled cases with false-positive calibration.
3. Run safe/reproducible fixtures before claiming any enhancement to detection, precision/recall, CI behavior or test reliability.
4. Reconcile this intake with earlier dogfood matrices; do not overwrite or renumber historical findings.
