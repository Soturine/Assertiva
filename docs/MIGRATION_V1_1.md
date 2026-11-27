# Migration to 1.1

1.1 is additive. Existing commands, exit codes, `--fail-on` conditions, report fields and Portfolio registries keep working; no option was removed. What changes for a reader of the outputs:

| Area | 1.0.x | 1.1 | Action |
| --- | --- | --- | --- |
| Report directory | `audit.html`, `audit.json` | also `audit.dogfood.json`, `audit.dogfood.md`, `dogfood/DF-<id>.json`, and `assessments/` after a re-attach | tools that expect exactly two files: list `*.html` / `*.json` explicitly; `ASSERTIVA_DOGFOOD=off` disables the dogfood files |
| Report JSON top level | — | optional `context`, `external_executions`, `reviews`, `dogfood`, `previous_traceability` (declared in `schemas/assurance-report.schema.json`) | schema consumers update the schema file |
| Assessment | dispositions, findings, unknowns | optional `sources`, `behaviors`, `external_executions`, `reviews`, `dogfood`, each validated | a 1.0.x engine silently ignores these sections: attach a 1.1 assessment with a 1.1 engine |
| Portfolio re-sighting of fixed feedback | always REGRESSION | REGRESSION only from an engine newer than the fix; older or equal versions are recorded as `before_fix` | none; registries are read as they are (schema 1, additive keys `imports`, `fixed_after_version`, `component`, `observation_kind`) |
| `portfolio move … VERIFIED_AT_SHA` | a SHA-like string in the evidence was enough | needs `--repo PATH` where the commit resolves and `--retest-results FILE` with every test passing; fixed states record `verification` and `proof` | pass `--repo` and the retest results |
| Imported sightings of fixed feedback | — | mark `regression_suspected`; only a local sighting moves the state to REGRESSION | none |
| Protection evidence for `PROVEN_IN_SCOPE` | — | only an engine-verified break (a specific engine mutant, or a negative control bound through `improve_report`); otherwise capped at `OBSERVED_PASS` with the claim kept | cite the improve report, or accept the cap |
| Cited artifacts (receipts, improve reports) | — | read only under `ASSERTIVA_HOME` or `ASSERTIVA_EVIDENCE_ROOTS` | write tool output there, or list its directory in `ASSERTIVA_EVIDENCE_ROOTS` |
| Mutation report from another root | `MUTATION_REPORT_SOURCE_MISMATCH` | tied by trailing path and identical content; the re-rooting is a limitation | none |
| `PIP_NO_BUILD_ISOLATION=1` | recorded as an isolation override | not an override (pip keeps isolation) | none |

Nothing is migrated in place: old reports and registries are read as they are, and no feedback id changes (`AFB-` ids are still derived from kind, rule and signature).
