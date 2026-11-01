# Derivanta Engine M2 — Assertiva 0.10.0 dogfood follow-up and engineering feedback

**Status:** DOCUMENTED / NOT IMPLEMENTED IN ASSERTIVA. **Observation date:** 2026-11-01.
**Subject:** Derivanta Engine M2 `0be2a3827991398e5a8b37c13281e3140b8e4c03`, with historical targeted mutation baselines at prior Engine revisions.
**Instrument:** released **Assertiva 0.10.0**, source `2e34542b4d04f2553618875498cd0e71842b9196`; read-only during Engine M2.
**Relationship:** this is the second round linked from PR #3. Its M0.1/M1 intake and eight AXF records remain authoritative for that round; **do not overwrite historical evidence or suggest they were repaired**.

**Provenance:** this report is a source-grounded intake from the immutable Engine M2 evidence, **not a new independent execution** of Assertiva. The same model family implemented, investigated and adjudicated M2; that is self-review plus tool evidence, not an independent qualification. All assertions in this intake are bounded by their cited source. No code changes, release or tag are made to Assertiva.

## 1. Primary source of truth (immutable M2 links)

| Source | What it establishes |
| --- | --- |
| [M2 milestone / exit criteria](https://github.com/Soturine/Derivanta-Engine/blob/0be2a3827991398e5a8b37c13281e3140b8e4c03/docs/milestones/M2.md) | Which Engine contracts/features were delivered and verified |
| [M2 report](https://github.com/Soturine/Derivanta-Engine/blob/0be2a3827991398e5a8b37c13281e3140b8e4c03/docs/milestones/M2_REPORT.md) | Summary of outputs, measures, lessons and remaining scope |
| [Canonical findings ledger](https://github.com/Soturine/Derivanta-Engine/blob/0be2a3827991398e5a8b37c13281e3140b8e4c03/docs/audits/m2/FINDINGS.md) | **63** entries across findings, corrections, discoveries, ideas, risks and agent mistakes; primary individual IDs |
| [Timeline and retests](https://github.com/Soturine/Derivanta-Engine/blob/0be2a3827991398e5a8b37c13281e3140b8e4c03/docs/audits/m2/CHANGES_AND_RETESTS.md) | Per-checkpoint actions, tests, provenance and unexpected discoveries |
| [Assertiva dogfood A/B/C](https://github.com/Soturine/Derivanta-Engine/blob/0be2a3827991398e5a8b37c13281e3140b8e4c03/docs/audits/m2/ASSERTIVA_DOGFOOD.md) | Targeted mutation, Framework alignment and tool-as-instrument assessment |
| [Assertiva feedback](https://github.com/Soturine/Derivanta-Engine/blob/0be2a3827991398e5a8b37c13281e3140b8e4c03/docs/audits/m2/ASSERTIVA_FEEDBACK.md) | AXF-01..08 rechecks, new AXF-M2-01, negative controls, candidate maintainer findings |
| [CP2 mutation summary](https://github.com/Soturine/Derivanta-Engine/blob/0be2a3827991398e5a8b37c13281e3140b8e4c03/docs/audits/m2/assertiva/cp2-assurance-mutation.json) | Before/after summary; reports are represented with hashes |
| [CP7 mutation summary](https://github.com/Soturine/Derivanta-Engine/blob/0be2a3827991398e5a8b37c13281e3140b8e4c03/docs/audits/m2/assertiva/cp7-mutation.json) | Per-module counts, evaluated denominators, module-selection scope and source SHA |
| [Six-repository dogfood](https://github.com/Soturine/Derivanta-Engine/blob/0be2a3827991398e5a8b37c13281e3140b8e4c03/docs/audits/m2/dogfood-cp7.json) | Repositories examined, completeness, source counts, candidates, SARIF schema validation, source unchanged |
| [Hostile-input probes](https://github.com/Soturine/Derivanta-Engine/blob/0be2a3827991398e5a8b37c13281e3140b8e4c03/docs/audits/m2/probes-cp7.json) | Input/CPU bounds observed in tested scenarios; not a security certification |
| [Run manifest](https://github.com/Soturine/Derivanta-Engine/blob/0be2a3827991398e5a8b37c13281e3140b8e4c03/docs/audits/m2/RUN_MANIFEST.json) | Recorded Windows/WSL execution, retests, CI identity and limitations |
| [M2 research landscape](https://github.com/Soturine/Derivanta-Engine/blob/0be2a3827991398e5a8b37c13281e3140b8e4c03/research/M2_LANDSCAPE_AND_OPPORTUNITIES.md) | External references, applicability and decisions |
| [CI success at closing SHA](https://github.com/Soturine/Derivanta-Engine/actions/runs/41275111247) and [at final HEAD](https://github.com/Soturine/Derivanta-Engine/actions/runs/41275707006) | **Engine**, not Assertiva, passed four remote jobs for each revision |

The `M2_REPORT.md` narrative was frozen with **62** entries and an outdated ENG-GAP-005 note; the final canonical ledger has **63** and the Engine gap register correctly closes ENG-GAP-005 for the executed CI revision. These are **Engine documentation drift**, not Assertiva detector defects. Both remote CI runs really executed 4/4 jobs; historical M0/M1 billing-blocked runs remain blocked.

## 2. How much did Assertiva help?

**It did help materially, as a test-quality instrument**, and the combined Claude/Engine/Assertiva investigation exposed real problems. A mutant survivor is not automatically a production defect; a killed mutant is only evidence that the selected tests detected that particular mutation. Distinguish tool-driven mutation, manual inspection and Engine's own gates.

| Targeted Engine module | First killed / evaluated | Retest killed / evaluated | Scope and limit |
| --- | ---: | ---: | --- |
| `core/assurance.py` | 191/261 | 227/261 | Two rounds; 70 first survivors, truncated list; 10 additional real gaps became visible in later untruncated output |
| `core/sarif.py` | 178/216 | 196/214 | **Denominator changed** after two redundant conditions were removed; do not report a same-denominator percentage uplift. Hand-applied follow-up also strengthened an identity assertion |
| `core/policy.py` | 43/54 | 48/54 | Surviving classifications documented by Engine agent |
| `core/lockfiles.py` | 36/68 | 56/68 | Surviving classifications documented by Engine agent |
| `core/traceability.py` | 79/114 | 92/114 | Surviving classifications documented by Engine agent |
| `core/maintainability.py` | **NOT_EXECUTED** | — | 594 planned mutations exceeded Assertiva's 300-run budget; only Engine hand-written negative/mutation controls covered this component |

Mutation runs were **targeted**, not a whole-suite mutation qualification. The source record states that some survivors may be caught by tests outside the selected suites. The Engine's **57/57** deliberately hand-written smoke mutants are a separate local/CI measure and **must never be added** to Assertiva's mutation result or described as full mutation coverage.

**Concrete effects, attributed correctly:**
- Engine wrote discrimination tests from surviving mutations in comparison, SARIF, gate policy, lockfile and traceability logic. The first assay of `assurance.py` showed **26 real test gaps over two rounds**, classified through manual source review and follow-up tests; not every survivor was a gap.
- The truncation in AXF-04 caused missed visibility: **70** survivors but only **50 names / 20 sites** in the output; **10** further real gaps emerged after the list shortened in a retest.
- A `StrEnum` order mutation (`is` to `<` or `>`) cannot be bulk-marked equivalent just because `is` to `==` is equivalent for the relevant enum instance. Counterexamples and regression oracles matter.
- Mutation also found two **redundant code conditions** in SARIF URI logic; those were removed. This is a product-code cleanup surfaced during mutation review, not necessarily an Assertiva analyzer bug.
- Other Engine bugs (positional fingerprints, baseline mutation harness, raw non-ASCII IRIs, no-op false positives in Engine's own AST detector) were fixed during combined engineering investigation. **They are not new Assertiva defects.**
- The Engine's cross-platform success (Windows **760 pass / 4 skip**, Linux WSL **763 pass / 1 skip**, remote CI 4/4 twice, installed-wheel smoke) shows Engine M2 qualification under the stated gates; **it does not repair or qualify Assertiva 0.10.0**.

## 3. Assertiva-specific findings: retained identities, differentiated current evidence

| ID | Evidence from M2 | Resolution required in Assertiva |
| --- | --- | --- |
| **AXF-01 — P1** | **REPRODUCED**: relative interpreter under `audit --dependencies` raises uncaught `FileNotFoundError` when the probe switches cwd; manifest-less variants may not exercise the failing branch | Canonicalize interpreter paths before cwd changes; test relative, absolute and missing interpreter; return typed actionable status, not a traceback |
| **AXF-02 — P1** | **REPRODUCED**: two `python -m unittest discover -s` commands in one multiline Actions `run:` still produce a false HIGH unobserved suite finding | Parse all relevant commands/roots; both-present, one-missing and reordered controls; unknown shells must remain uncertain rather than fabricated |
| **AXF-03 — P2** | **REPRODUCED**: assigned repeatability test misclassified as SELF_REFERENTIAL_ORACLE | Recognize direct-vs-assigned deterministic repeatability; do not confuse repeatability with expected-value correctness |
| **AXF-04 — P1** | **REPRODUCED on Engine CP2**, with more significant impact than M1: 70 raw survivors, truncated presentation, 10 real gaps not initially visible | Expose raw denominator, displayed count, truncation/hidden sites, stable identifiers and assessment completeness. Refuse “all reviewed” while any survivor is unreviewed or hidden. Add >display-limit negative controls |
| **AXF-05 — P1** | **NOT RE-EXECUTED** in M2; historical M1 reproduction of `unittest -s` roots stays open | Preserve M1 fixture, reproduce configured discovery roots with a truthful count |
| **AXF-06 — P2** | **NOT RE-EXECUTED** in M2; historical M1 typed-exception oracle remains open | Re-run historical typed-exception counterfactual and calibrate oracle semantics |
| **AXF-07 — P2** | **REPRODUCED**: different imported `lib` subjects, similar `test_add` body, falsely flagged as redundant | Preserve distinct subject identity; distinguish text similarity from redundant protective value |
| **AXF-08 — P1** | **NOT SEMANTICALLY RE-RUN**; old Skill file unchanged, M1 verdict **2 PASS / 1 REVIEW** remains a review item, not a pass | Ensure authorization and actual OS isolation requirements are explicit; venv/copy does not itself isolate OS side effects. Independent safety review still needed |
| **AXF-M2-01 — P1 (NEW)** | **REPRODUCED**: `assert add(1, 2) == 4 or True` is **not reported** by Assertiva although `assert True` is reported; control `assert add(1,2) == 3` correctly remains unflagged. Locally registered as `AFB-7c31f0fdb0` | Detect constant truthy `or` (and equivalent always-pass forms) using bounded static expression analysis; negative controls for legitimate `or` expressions and runtime-dependent truthiness |

**Important identity rule:** AXF-M2-01 is **not** a renumbering of AXF-01..08. A local `AFB-*` Portfolio identifier is an evidence-record identity, not a substitute for the cross-repository AXF finding ID. AXF-07 (absent from original M1 Portfolio export) and AXF-08 (Skill review) should be accounted for without claiming they were retroactively recorded in M1.

### AXF-M2-01 minimal reproducible example

```python
def add(a: int, b: int) -> int:
    return a + b

def test_always_passes_even_when_result_is_wrong() -> None:
    assert add(1, 2) == 4 or True  # should be a false-green/tautology candidate

def test_meaningful_control() -> None:
    assert add(1, 2) == 3         # should NOT be flagged as a tautology

def test_existing_positive() -> None:
    assert True                   # existing detector reports this
```

**Acceptance:** mutate `add` to return a wrong result; the first test stays green, the meaningful control goes red. Assertiva flags only the structurally always-pass assertions with non-ambiguous evidence. Add cases for `True or expr`, `expr or True`, nested `or`, side-effect-bearing expressions (static predicate still true but executing left expression may raise), and false-positive controls. Do not execute inspected repository code just to infer tautology.

## 4. Additional cross-dogfood observations (not automatically Assertiva bugs)

These come from **Engine `inspect --maintainability` running on Assertiva** at source SHA `2e34542`. Findings are **candidates**, not confirmation of unnecessary code or sound refactor decisions.

| Item | Observation | Recommendation |
| --- | --- | --- |
| `assertiva/report_html.py::_STRENGTH` | Exactly one repository-wide textual occurrence reported by the Engine's follow-up `git grep` | Review whether obsolete or part of an intentionally retained future contract; if unused, remove with tests |
| `assertiva/environment.py::ISOLATION_SANDBOX` | Unused by implementation yet intentionally documented as unsupported | Keep explicitly specified-only / UNKNOWN_DYNAMIC, **not** auto-delete |
| Four `tests/test_* .py::_run` helpers | Similar bodies used by tests in agent flow, mutation tools, PIT and protection demo | Consider shared test utility only if it reduces maintenance without reducing fixture independence; don't blindly deduplicate |
| 150 functions crossing Engine's 15-decision-path threshold | Broad complexity signal; this is **Engine's own metric**, not a benchmarked diagnosis | Use targeted prioritization by volatility, defects and review cost; do not initiate 150 blind refactors |
| Engine `--maintainability` no-op false positives | Two **Engine detector** false positives were fixed during M2 | Transfer lesson: oracle quality and negative controls should precede any new Assertiva static-no-op heuristic |
| Six-repository dogfood & six valid SARIF exports | Good Engine integration / contract evidence on heterogeneous repositories | Do **not** infer Assertiva recognized every real defect or was run on all six projects |

## 5. Opportunities, ideas and proposed experiments for Assertiva

These are **proposals**, not defects already proven in Assertiva or promises to implement all of them in one patch. Reuse existing owners before adding more modules. Decision vocabulary: **ADOPT / ADAPT / EXPERIMENT / DEFER / REJECT**.

| ID | Priority | Proposal | Rationale and acceptance criteria | Disposition |
| --- | --- | --- | --- | --- |
| **AXO-M2-01** | P1 | **Mutation evidence completeness + review accounting** | Address AXF-04: separate raw count, listed count, truncated count, site count, equivalents, unreviewed, status; ensure assessment cannot close hidden survivors; >20/>50 controls | ADOPT as defect fix |
| **AXO-M2-02** | P1 | **Tautology / constant-truth AST detection with false-positive calibration** | AXF-M2-01: catch `assert x or True` and variants, but not legitimate alternative contracts; source-faithful disabled/runnable-state logic | ADOPT as defect fix |
| **AXO-M2-03** | P2 | **Budget-aware mutation targeting with honest partial status** | `core/maintainability.py` 594 planned vs budget 300: test scoped targets by function/region/shard only if feasible with the actual mutator; retain original total and denominator/selected set; otherwise BLOCKED with workaround instructions | EXPERIMENT; do not claim full-module mutation |
| **AXO-M2-04** | P2 | **Reference/subject-aware redundancy assessment** | AXF-07: imported implementation identity matters even when test bodies match. Controlled tests with renamed imports and true duplicates; retain uncertain classification | ADAPT existing oracle/duplication detector |
| **AXO-M2-05** | P2 | **Explicit oracle strength tiers** | Separate determinism/repeatability, simple exception type guard, behavioral expected-value and full integration evidence; avoid upgrading weak protection or false positives | ADAPT AXF-03/06 correction |
| **AXO-M2-06** | P2 | **Dogfood measurement-system quality protocol** | Report negative controls, synthetic ground truth, TP/FP/FN per class, judge identity, scope, errors, and upstream tool-output limitations. No single magic score; independent confirmation when material | ADAPT existing evals and Portfolio |
| **AXO-M2-07** | P3 | **Candidate refactoring queue from Engine maintainability reports** | Start with unused constant, repeated test helpers; triage dynamic/public names and no-op signals before any patch; keep only justified changes | EXPERIMENT; not part of bugfix release by default |
| **AXO-M2-08** | P3 | **Engine SARIF/CI integration as an optional corpus** | In future dogfood, ingest Engine SARIF as untrusted candidate evidence and compare CI-gate outputs without claiming imported findings are independently confirmed | EXPERIMENT; avoid a second source of truth |
| **AXO-M2-09** | P2 | **Reproducer retention and no-duplicate-feedback routing** | Link `AXF-01..08` and `AXF-M2-01` to immutable snapshots and Portfolio AFB IDs; preserve old failure records and add status of rerun/negative control/release validation | ADAPT existing intake and Portfolio |

**Separate Engine/Framework findings:** project-declared scan exclusions (M2-I-007), Type-2 clone detection, complexity growth ratchet, pytest-marker traceability, FCP-018..023, Engine's stale M2 report count and future MCP adapters are not automatically Assertiva requirements. They are upstream evidence or possible integration ideas; do **not** import the Engine's 63 ledger items as 63 Assertiva defects.

## 6. Recommended implementation order for a later Assertiva maintenance milestone

1. **CP-A — evidence integrity:** AXF-04/AXO-M2-01 and AXF-M2-01/AXO-M2-02, including deliberately truncated lists and always-pass `or True` assertions; prove detector precision via negative controls.
2. **CP-B — prior reproducible regressions:** AXF-01/02/05, followed by AXF-03/06/07 with matched contrasts; retain inherited AXF-08 as safety review until independently evaluated.
3. **CP-C — bounded mutation experiment:** investigate <300-target selection or multiple traceable shards without masking the 594 full target population, worktrees, timeouts or tool cost; do not manipulate a score by excluding inconvenient mutants.
4. **CP-D — dogfood on frozen subject revisions, independent challenge, installed-wheel packaging, Windows and Linux gates, published red/green reports, Portfolio and documentation reconciliation.**

**Patch/release status:** no new version number is declared here; any 0.10.1 decision is separate and requires working code, regression evidence and explicit qualification. Do not merge an intake as though it fixed the bug.

## 7. Reporting contract and privacy

- Keep the full source outputs in **Derivanta Engine** (immutable links above). This Assertiva PR stores only this intake and a [small structured summary](DERIVANTA_ENGINE_M2_FEEDBACK.json).
- Mutation counts, original denominators, tool build identities, snapshot provenance and honest NOT_EXECUTED must remain visible.
- Include both successes and weaknesses; none of these 0.10.0 results is a present-day independent run against a newer Assertiva build.
- Never publish private paths, credentials, unredacted environment dumps or corporate/project-private artifacts.
- Distinguish `reproduced`, `historical not rerun`, `specified only`, `candidate`, `confirmed after manual review` and `blocked` in every later report.

**Conclusion:** Assertiva contributed tangible, targeted defect-detection evidence and improved the Engine's tests, while the Engine M2 exercises produced a new reproducible Assertiva false negative and additional calibration/budget/reporting opportunities. The PR is deliberately an **evidence intake**, not a code-fix claim.
