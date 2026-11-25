# Evidence Contract

Agent context should receive enough information to choose the next action without loading every raw artifact.

Preserve when material:
- exact revision/commit and dirty state;
- environment/platform;
- configuration/profile/feature flags;
- data/DB/schema version;
- selected, executed, passed, failed, skipped, not-run, retried;
- runner/version;
- selector method and limitations;
- diagnostic level;
- fidelity;
- raw artifact references;
- redaction state;
- timing/seed;
- residual unknowns.

## Raw artifacts
Compression is not deletion. Raw stdout/stderr, traces, screenshots, videos, coverage reports, profiler output, and structured reports should remain retrievable when practical.

## Secret handling
Never blindly expose all locals or environment values to a coding agent. Prefer relevant/allowlisted values and redaction.

## Oracle quality, source completeness and independent challenge

These are semantic audit obligations when material, not new automatic gates. The agent investigates; native runners, mutation tools and deterministic engine measurements constrain the claims.

- Trace a meaningful assertion to the behavior it claims to protect. Keep approved contract, observed implementation, organizational policy, risk hypothesis and exploratory observation distinct. A current implementation may justify characterization, not a new requirement. Confidence, repeated model agreement and a valid reference do not establish authority.
- For imported or reused tests, establish original identity/revision and target context; revalidate assumptions, actors, configuration, fixtures and oracle against the destination. Preserve historic runs and comments. A duplicate or stale test is a proposal for review, not deletion authorization.
- Distinguish inventoried, actually read, partially studied, missing and superseded sources. Prefer host-native reading of selected original documents and visual evidence; extraction is optional verification/fallback with losses recorded. Do not add parsers merely to simulate reading.
- Distinguish a native runner green from a functional verdict. An empty step, tautological assertion, wrong resource, over-mocked boundary or changed oracle can pass. Use the actual tool evidence and, when useful, a negative control/mutant that should fail; independently review the assertion and the approved expected behavior. A hash establishes consistency, not authenticity or semantic correctness.
- Preserve selected/executed/outcome/proven denominators, attempt history, observed versus claimed findings, and scope limits. Report risk coverage separately from nominal coverage; do not manufacture precision or demand maximum case count. If support changes, mark dependent conclusions stale pending revalidation.

Qualification candidates (not executed here): equivalent paraphrases with different oracle quality; empty green test; a meaningful assertion that catches a seeded defect; cloned test with changed permission; inaccessible diagram; stale source; report with fabricated PASS; legitimate characterization. Evaluate against independent gold and measure false greens, false alarms, review independence and time/cost when available. No keyword classifier or new provider/runtime required.

Adapted from [QE Oracle Policy](https://github.com/Soturine/qe-engineering-skill/blob/main/docs/ORACLE_POLICY.md), [Trust Model](https://github.com/Soturine/qe-engineering-skill/blob/main/docs/TRUST_MODEL.md), [Existing Asset Audit](https://github.com/Soturine/qe-engineering-skill/blob/main/docs/EXISTING_ASSET_AUDIT_POLICY.md) and [Quality Metrics](https://github.com/Soturine/qe-engineering-skill/blob/main/docs/QUALITY_METRICS.md). External reference: [Agent Skills specification](https://agentskills.io/specification) and [OpenAI evaluation best practices](https://developers.openai.com/api/docs/guides/evaluation-best-practices). No copied runtime, new dependency or claimed execution.
