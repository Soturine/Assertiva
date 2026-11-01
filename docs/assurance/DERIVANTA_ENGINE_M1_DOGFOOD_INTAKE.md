# Post-release intake — Derivanta Engine M0.1 + M1 dogfood (Assertiva 0.10.0)

**Status: DOCUMENTED / NOT IMPLEMENTED.** Evidence date: **2026-10-31**. This intake is based on the **published Derivanta Engine audit** (Engine commit [`2922bdb`](https://github.com/Soturine/Derivanta-Engine/blob/2922bdb68990f7d5e8dfcb02c1082fb0810b71f2)), performed using released Assertiva **0.10.0** ([`2e34542`](https://github.com/Soturine/Assertiva/tree/2e34542b4d04f2553618875498cd0e71842b9196)). It is not an independent rerun of the audit or a repair PR. Do not retroactively change the 0.10.0 release's historical [post-dogfood gap matrix](POST_DOGFOOD_GAP_MATRIX.md).

The full machine-readable intake lives in [DERIVANTA_ENGINE_M1_FEEDBACK.json](DERIVANTA_ENGINE_M1_FEEDBACK.json). Source outputs remain in the Engine repository (below); large audit HTML/JSON and mutation results are **linked, not copied** into Assertiva. Original reports are tied to their own historical SHAs; the Engine's publishing commit is only the evidence index.

## Primary outputs (immutable links)

| Output | Purpose |
| --- | --- |
| [Cross-dogfood index](https://github.com/Soturine/Derivanta-Engine/blob/2922bdb68990f7d5e8dfcb02c1082fb0810b71f2/docs/audits/assertiva/m1/README.md) | Scope A (Engine), B (Framework), C (Assertiva), source revisions, execution limitations |
| [Finding reconciliation](https://github.com/Soturine/Derivanta-Engine/blob/2922bdb68990f7d5e8dfcb02c1082fb0810b71f2/docs/audits/assertiva/m1/FINDINGS.md) | Agent vs engine: confirmed, contextual, false positives, corrections and unresolved |
| [Assertiva 0.10.0 evaluation](https://github.com/Soturine/Derivanta-Engine/blob/2922bdb68990f7d5e8dfcb02c1082fb0810b71f2/docs/audits/assertiva/m1/ASSERTIVA_EVALUATION.md) | Eight AXF IDs, reproduced defects and functions that worked |
| [Run manifest](https://github.com/Soturine/Derivanta-Engine/blob/2922bdb68990f7d5e8dfcb02c1082fb0810b71f2/docs/audits/assertiva/m1/RUN_MANIFEST.json) | Run IDs, code identity, local changes, outcomes and mutation status |
| [Mutation before/after reports](https://github.com/Soturine/Derivanta-Engine/blob/2922bdb68990f7d5e8dfcb02c1082fb0810b71f2/docs/audits/assertiva/m1/engine) | Cosmic Ray in manifests and pointer; blocked grader mutation |
| [Controlled fixture builder](https://github.com/Soturine/Derivanta-Engine/blob/2922bdb68990f7d5e8dfcb02c1082fb0810b71f2/docs/audits/assertiva/m1/assertiva-self/fixtures/audit_c_fixtures.py) | Synthetic C1–C4 counterfactual probes; no private Framework code embedded |
| [Semantic responses and judge verdicts](https://github.com/Soturine/Derivanta-Engine/blob/2922bdb68990f7d5e8dfcb02c1082fb0810b71f2/docs/audits/assertiva/m1/assertiva-self/semantic) | Three Skill evals, 2 PASS and 1 REVIEW |
| [Portfolio feedback export](https://github.com/Soturine/Derivanta-Engine/blob/2922bdb68990f7d5e8dfcb02c1082fb0810b71f2/docs/audits/assertiva/m1/feedback/portfolio-report.json) and [commands](https://github.com/Soturine/Derivanta-Engine/blob/2922bdb68990f7d5e8dfcb02c1082fb0810b71f2/docs/audits/assertiva/m1/feedback/feedback-commands.sh) | Original local-feedback records and replay commands |
| [Artifact hashes](https://github.com/Soturine/Derivanta-Engine/blob/2922bdb68990f7d5e8dfcb02c1082fb0810b71f2/docs/audits/assertiva/m1/artifact-hashes.json) | Original vs path-redacted published file digests |
| [Consolidated M0.1/M1 report](https://github.com/Soturine/Derivanta-Engine/blob/2922bdb68990f7d5e8dfcb02c1082fb0810b71f2/docs/milestones/M0_1_M1_REPORT.md) and [ideas/landscape](https://github.com/Soturine/Derivanta-Engine/blob/2922bdb68990f7d5e8dfcb02c1082fb0810b71f2/research/IDEAS_AND_LANDSCAPE.md) | Outcome, controls, benchmarks, risks, candidate future integrations |

**Provenance/limits.** Audits were agent-led with Assertiva as an instrument. Engine local Windows and WSL Linux verification is **not** remote CI. The Engine's four remote jobs for the closing revisions did not start because of billing (0 steps, no runner); this is external BLOCKED evidence, not a test failure and not a PASS. The Framework and Assertiva source trees were not modified in that audit. All proposed changes here still need tests and review in Assertiva. A disposable copy or venv is **not** an OS security sandbox.

## What the dogfood established

1. **Assertiva materially improved test sensitivity:** on `core/manifests.py`, targeted Cosmic Ray survivors dropped **35/117 → 7/117 → 4/117 → 3/117** after new discriminating tests; three final survivors have documented equivalence arguments, including CPython-specific caveats. `core/pointer.py` dropped **4/70 → 2/70** survivors, justified as equivalent. One mutant initially called equivalent by the agent was later killed; equivalence claims require review.
2. **Assertiva found test gaps**, while independent agent investigation found others: same-size in-place rewrite while reading, variable test inventory due to cache files, Django `tests.py`/manifest-free Django misses, control-character rendering, and a shell pipeline that masked a verifier's exit code. The Engine fixed these in its own implementation. Do **not** attribute all these discoveries to Assertiva's automatic detectors.
3. **Capabilities confirmed by controlled probes:** SOURCE_IDENTITY_MISMATCH detected a wrong installed package with an otherwise green run; package dependency-closure inspection did **not** execute an import-side-effect canary; timeout/provenance, targeted mutation selection, Portfolio and assessment guards worked in the exercised scope.
4. **Eight follow-ups** arose: seven tool/adapter/report defects (**AXF-01..07**) and one Skill semantic-safety REVIEW (**AXF-08**). Six unique entries exist in the exported Portfolio registry, not seven: **AXF-07 was not registered**. AXF-08 was recorded in prose only. There was a deliberate duplicate sighting for AXF-02 (dedup worked). The source document's phrase “seven tool defects are in the registry” is overbroad.
5. **Semantic Skill evals:** 2 PASS / 1 REVIEW, selected from 71 cases. Agent and judge used separate contexts but the same model family; this is not independent validation and does not establish general Skill safety.

## AXF backlog — priority, impact, reproducer, acceptance gate

The canonical details, evidence notes, and fields are in the [JSON matrix](DERIVANTA_ENGINE_M1_FEEDBACK.json). IDs are stable, independent of any later Assertiva Portfolio `AFB-*` ID.

| ID | Priority | Problem | Required demonstration before closure |
| --- | --- | --- | --- |
| **AXF-02** | **P1** | Multiline GitHub Actions `unittest discover` scopes: false HIGH CI gap | Both suites counted; omitted suite still detected; command order does not alter result |
| **AXF-04** | **P1** | 35 raw mutation survivors → finding shows 20; “20/20 reviewed” accepted | Raw mutant vs grouped-site accounting transparent; incomplete assessment is visibly partial |
| **AXF-05** | **P1** | Framework CI invokes 79 tests, native adapter discovers 0 at repo root | Reproduce declared `-s` suites or explicitly BLOCK; zero executions never pass |
| **AXF-08** | **P1** | Skill suggests code import in venv without authorization/sandbox caveat (REVIEW) | Skill wording + adversarial semantic eval with independent critic and non-executing option |
| **AXF-01** | **P1** | Relative `--python` crashes under `audit --dependencies` | Absolute and relative controls; graceful refusal for invalid interpreter; no traceback |
| **AXF-03** | P2 | Assigned determinism misclassified as false-green tautology | Classify repeatability semantically, without treating it as full behavioral correctness |
| **AXF-06** | P2 | Typed `try/except` guards shown as NO_ASSERTION | Negative-control KeyError fails; recognize limited exception contract, not everything |
| **AXF-07** | P2 | Tests for different imported validators called redundant by identical-body heuristic | Consider subject and expected contract; don't remove valid structural duplicate signal |

**Cross-cutting rule:** A reproducible false positive, a missed test, and a report contract error must be fixed according to their own evidence; never weaken tests to make metrics green. Separate syntax signals from semantic agent judgment. No arbitrary aggregate quality score.

## Proposed implementation order (next work, not part of this PR)

- **Gate A — evidence & trust (AXF-04, AXF-08):** source identity/review scope/safety statements must be honest before further automation. For AXF-04, check `survivors_total`, aggregation, full denominator and assessment validity under variants with >20 distinct mutants; for AXF-08, prefer static closure and require authorization before running foreign imports. Preserve [EXECUTION_SECURITY.md](../EXECUTION_SECURITY.md) limits.
- **Gate B — CI and execution fidelity (AXF-02, AXF-05, AXF-01):** first execute the C1 controlled fixtures, then multi-root unittest with native per-root counts and status, then relative-interpreter canonicalization; protect existing working-directory behavior (TCC-A01) with negative controls.
- **Gate C — oracle calibration (AXF-03, AXF-06, AXF-07):** development fixtures plus frozen independent confirmation cases; measure TP/FP/FN **per behavior**, including previously correct negatives. Preserve DETERMINISM semantics and distinguish structural identity from equivalent protective value.
- **Gate D — dogfood/evals/release decision:** re-audit the pinned Engine and Framework and a distinct stack; separate agent-only/tool-only/overlap/false positives; rerun targeted mutations, failed regressions and safety Skill evals; make explicit what remains NOT_RUN/UNKNOWN. No automatic release or 1.0 readiness claim.

**Release proposal, not a version commitment:** these are primarily reproducible post-0.10.0 defects; a **0.10.1 hardening candidate** would be a reasonable scope if the owner chooses a patch release. The existing [ROADMAP](../../ROADMAP.md) targets 1.0 competitive maturity; **do not silently add an approved 0.11 or move 1.0 gates**. Merge of this documentation PR is not approval to implement, change contracts, or publish.

## Further suggestions, independently triaged (not AXF defects)

| Idea | Benefit | Boundary / decision |
| --- | --- | --- |
| Report reviewer coverage at **per-mutant and per-site** granularity (AXF-04 consumer) | Prevent false “fully reviewed” conclusions; meaningful for manual and imported mutations | Candidate for same patch; avoid redefining `survivors_total` silently |
| Export feedback as a portable, evidence-bound intake manifest | Allows deterministic import from Engine/DrawLab/TCC dogfood PRs and protects dedup/provenance across workspaces | Future candidate; current JSON + links are sufficient; do not build an unneeded service |
| `explain` provenance for operator-run manual mutants | Show protection measured by the project's own mutation smoke | Candidate only after a real consumer; currently its omission is documented, not a false test verdict |
| Explicit observed/declared/unknown CI scope by start directory | Multi-root/monorepo tests avoid fabricated gap/selections | Pair with AXF-02 and AXF-05; cannot infer that remote CI actually ran |
| Semantic eval expansion with independent holdouts | 3/71 cases and same-family judge are insufficient to qualify the Skill | New adversarial cases on unsafe imports and no-sandbox framing, then independent judging |
| Mutation-budget experiments on large Python modules | The Engine's conformance grader planned 305 mutants against a 300 budget; record **BLOCKED**, never “covered” | Bounded target/selection strategy should not distort what is claimed measured |
| Dependency readiness: manifest/lock/installed/used separation | Engine inspection and Assertiva dependency reporting have complementary evidence | No installed-version/security-claim inference from a declared dependency |
| Multi-stack correctness benchmarks and Agent vs Tool attribution | Measure false highs, false greens and fixes on real repos without self-graded superiority | Match revisions, tools, environments, budgets and an independent label set |
| Untrusted agent-instruction files in repository intake | `AGENTS.md`/`CLAUDE.md` etc. are prompt-injection surfaces, not higher authority | Primarily Derivanta Engine candidate I-04; Assertiva should not execute or obey them blindly |
| Golden repository sets / attestations / Scorecard, SARIF, OSV | Potential evidence interoperability | Research-only; separate integration decisions, don't duplicate analyzers already mature |

## Acceptance criteria for follow-up code PR(s)

- `AXF` ID on each implementation commit, before/after fixture and independent negative control; no incidental modification of Engine/Framework.
- Engine evidence source fixed at the recorded SHA or intentionally revised and labelled; latest floating main never replaces historical evidence silently.
- Regression test must fail before the corresponding fix and pass after, where technically feasible. Prefer smallest change that resolves the proven failure, not scanner overfitting.
- Findings provide evidence, scope, runnable commands and limitations. Re-evaluate on actual installed Assertiva wheel, not just editable checkout; keep Source Identity checks.
- Test audits must stay agent-led: tool results are candidates; the agent reviews code, requirement and negative controls, including **things Assertiva never detected**.
- Security: user authorization, secret boundaries and untrusted import behavior are verified separately from filesystem read-only guarantees.
- Run appropriate local Windows/Linux checks. CI failures or missing CI are recorded with truthfully bounded provenance; no forced green, no release until independently approved.
- No premature 1.0 contract promises, no unapproved write operations, no AI co-author trailers.

## Follow-up action ownership and portfolio gap

The six exported Portfolio records map to AXF-01..06, including a second **sighting** of AXF-02. `AXF-07` has a reproducible description but is **missing from that export and replay shell script**; when implementing, register it without fabricating an AFB ID, using a synthetic reproducer and existing dedup semantics. `AXF-08` is a Skill semantic case and remains separate until the owner chooses an appropriate feedback route. The [historical export](https://github.com/Soturine/Derivanta-Engine/blob/2922bdb68990f7d5e8dfcb02c1082fb0810b71f2/docs/audits/assertiva/m1/feedback/portfolio-report.json) must not be rewritten to make its counts appear different.

Framework-only findings (three checkers failing, vacuous retrieval scorer, weak negative validator tests) are **upstream Framework proposals**, not fixes this Assertiva PR should silently make. The Engine's policy-excluded tracked files, mutation budget and platform/CI limits are evidence for future testing, not proof of an Assertiva product bug.

## PR boundaries

- Documentation-only intake: **no Assertiva code, tests, release version, or historical 0.10.0 gap statuses changed.**
- Raw reports remain at their provenance links. No local usernames, machine paths, credentials or large HTML reports copied.
- Before implementing new rules, compare this intake with the old matrix for overlap and root causes (TCC-A01, AX-E05 and AG-05) instead of counting duplicates as new discoveries.
