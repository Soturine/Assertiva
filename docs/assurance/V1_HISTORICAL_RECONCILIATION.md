# v1.0 historical reconciliation

Historical audits and intakes are kept as written. A line that says "not implemented" stays as it was; this index says
where the item was closed afterwards.

| Record | Said at the time | Closed by | Where |
|---|---|---|---|
| [VozNativa v0.5 intake](VOZNATIVA_V05_DOGFOOD_INTAKE.md) AXF-VN-01..05 | DOCUMENTED / NOT IMPLEMENTED (VN-01 later "fixed on this branch") | `485df1d`, `de10503`, `161d705`, `ab38227` on `integration/v1.0-foundation` | reconciliation index at the end of the intake; the `reconciliation` field in its JSON |
| [Randomizer v0.7.12 intake](intakes/BEAMNG_RANDOMIZER_0_7_12_DOGFOOD.md) AXR-01..14 | intake / remediation candidates | AXR-02 `e0ae1c8`; AXR-03/04/05/06/08 `2e4b437` + `517ce4b`; the others DEFERRED | [V1_REMEDIATION.md](V1_REMEDIATION.md) |
| Prescripta (two branches) | "fixed" on their branches, not released | corrected and merged: `4bd6840`, `163c67f` | [V1_REMEDIATION.md](V1_REMEDIATION.md) |
| 0.10.1 ledger AXF-08 | PARTIAL: the semantic evaluation was NOT_RUN | run 2026-11-13: PASS, with the deterministic marker gate passed | [V1_AGENT_EVALS.md](V1_AGENT_EVALS.md) |
| 0.10.1 ledger: mutation of `ci.py` | BLOCKED (over the 300-run budget) | unchanged: ACCEPTED_LIMITATION | none |
| DrawLab M10 branch, TCC (PR #1) branch | historical branches that diverged from `main` | already in `main` by content (compared file by file); not merged again | [V1_INTEGRATION_MATRIX.md](V1_INTEGRATION_MATRIX.md) |
| Derivanta M1/M2/M3 intakes | "documented, not implemented" | fixed in 0.10.1 (PR #5) | [REMEDIATION_0_10_1.md](REMEDIATION_0_10_1.md) |
