# Derivanta Engine M0 → Assertiva 0.9.0 cross-dogfood (2026-10-29)

**State:** independently reviewable feedback; **not a feature implementation, release, or full self-qualification**. This record belongs to PR #1's evidence-first dogfooding series and retains the earlier TCC evidence unchanged.

- **Assertiva under test:** `cf5cb7d0c0893f609df970911a28f43ed0bba83d`, version `0.9.0`. 
- **Engine auditing revisions:** `5c6d7d3c712fcc57fa931a19a8852d6ee0aa5db3` (baseline), `87a8f1be887f01e5a3f1857ad86e58f51bcdb4b3` (intermediate), `2f65aa1d0fea283f32f5aea4f166019b4f64a45f` (final Assertiva audit).
- **Framework specification revision:** `218761dbd7ce78809ace0ae2c03ee23adf9b406b`; the Engine's later M0 publishing HEAD is `0d846a89d4dab23aa0ab80d6eb6d4fb9f13512ab`, **not the SHA audited by Assertiva**.
- **Environment:** Windows 11, Python 3.12.10; a single auditing agent performed both audits and adjudication. Do not call this an independent blind evaluation.
- **Published Engine evidence:** [cross-dogfood index](https://github.com/Soturine/Derivanta-Engine/blob/0d846a89d4dab23aa0ab80d6eb6d4fb9f13512ab/docs/audits/assertiva/m0/README.md), [Audit A findings](https://github.com/Soturine/Derivanta-Engine/blob/0d846a89d4dab23aa0ab80d6eb6d4fb9f13512ab/docs/audits/assertiva/m0/FINDINGS.md), [Audit B/Assertiva self-evaluation](https://github.com/Soturine/Derivanta-Engine/blob/0d846a89d4dab23aa0ab80d6eb6d4fb9f13512ab/docs/audits/assertiva/m0/ASSERTIVA_SELF_EVALUATION.md), [manifest](https://github.com/Soturine/Derivanta-Engine/blob/0d846a89d4dab23aa0ab80d6eb6d4fb9f13512ab/docs/audits/assertiva/m0/RUN_MANIFEST.json), [hash manifest](https://github.com/Soturine/Derivanta-Engine/blob/0d846a89d4dab23aa0ab80d6eb6d4fb9f13512ab/docs/audits/assertiva/m0/artifact-hashes.json), [sanitized final audit JSON](https://github.com/Soturine/Derivanta-Engine/blob/0d846a89d4dab23aa0ab80d6eb6d4fb9f13512ab/docs/audits/assertiva/m0/engine-final/audit.json) and [HTML](https://github.com/Soturine/Derivanta-Engine/blob/0d846a89d4dab23aa0ab80d6eb6d4fb9f13512ab/docs/audits/assertiva/m0/engine-final/audit.html). **Access note:** Engine may be private; URLs are not standalone public fixtures. The reproducible behavioral contracts below do not depend on access to it.

## Observed result, by instrument

| Instrument and scope | What was observed | What it does *not* prove |
|---|---|---|
| Assertiva Audit A, baseline `5994c81dd80640c3` | 13 of 15 Python test modules failed native collection; 55 invocations NOT_RUN; `ModuleNotFoundError: derivanta_engine`. Report exit 0 means audit completed, **not** suite success | No complete suite execution |
| Independent negative control on stale/noneditable install | A deliberate source-tree mutant survived while six relevant tests passed against an installed site-packages copy | Not an Assertiva-executed mutation; not whole-suite quality |
| Developer corrections and Assertiva final run `b6cf298a512c4327` | 291 native PASS, 3 SKIPPED in disposable copy; no package import confusion; wheel qualification ran and passed scope documented in Engine report | Not CI success or proof on final publishing SHA |
| Assertiva `--execute --mutate` targeting Engine `core/redaction.py` | Cosmic Ray: 11/11 selected mutants KILLED; no survivors in this file/operator set | Not an entire-codebase mutation score; regex literals are not generally changed by default operators |
| Developer-authored mutation smoke | Canary detected and 12/12 hand-picked mutations KILLED after three earlier survivors motivated new tests | Developer-operated smoke, not Assertiva's native mutation run |
| Assertiva Audit B on controlled `known-defects` fixture | 5 of 7 deliberately weak tests detected; 2 missed; 2 strong tests misidentified as weak. Native fixture results: 10 PASSED, 1 FAILED, 1 SKIPPED and appropriately retained | Limited Python fixture, not independently representative precision/recall |
| Assessment rejection tests | Four malformed/stale assessments refused (exit 2); one valid accepted | No broad security proof |
| `__main__` package probe A/B | Unguarded package entry point executed during closure import and blocked the probe; guarded case passed | A package import is *not* a safe no-execution operation |
| CI | No valid remote CI proof for Engine audit revisions; GitHub Actions jobs failed before any steps due to account billing block documented by Engine | No Linux, macOS or CI equivalence claim |

## Confirmed and actionable gaps in Assertiva

**AX-E01 — P1 — Package dependency-closure probe executes imported module entry points.** In `assertiva/adapters/python_package.py`, `_CLOSURE_PROBE` traverses `pkgutil.walk_packages` and imports the discovered modules, including `<package>.__main__`; a conventional *unguarded* `sys.exit(main())` can execute the program and abort the probe. The A/B controlled fixture generated `dependency_closure BLOCKED` in the unguarded case and PASS in guarded case. **Fix direction:** never treat import-based probing as safe metadata-only inspection; avoid importing entry points, explicitly gate runtime import probes as potentially effectful, and preserve UNKNOWN/BLOCKED semantics with exact cause. A simple `__main__` exclusion alone is incomplete because arbitrary imports can have side effects. **Gate:** safe/unsafe fixture pair; verify no program invocation for default metadata-only checks, error provenance, Windows/Linux, and no regression in legitimate dependency discovery.

**AX-E02 — P1 — Tested code identity is not proven by green pytest alone.** A `src/` mutant remained unnoticed with tests importing an installed package instead of source under test; originally, without that installed package, 13/15 files failed collection. This was an Engine configuration fault **found by the auditing agent**, not a bug in Assertiva's implementation, but Assertiva lacked an identity guard that would spot it. **Proposal:** record imported module origins / source-tree identity when native tests execute, detect source-vs-installed artifact mismatch, and issue a bounded claim, not a false definitive failure. **Gate:** two controlled src-layout cases (editable tree vs non-editable wheel), same mutant, recognized mismatch and correct source verification; allow deliberately installed-artifact qualification to remain valid in its own modality.

**AX-E03 — P1 — Missing vacuity signals for empty-container subset assertions.** `assert set() <= {...}` is always true; the 0.9.0 engine missed this in controlled `test_vacuous_subset`. **Gate:** recognize a known-empty left operand while retaining meaningful subset assertions as valid, and confirm with a mutant.

**AX-E04 — P1 — Self-mocking can fake the tested boundary.** A controlled test patched the very function it claimed to verify (`test_mocks_the_unit_under_test`) and Assertiva did not nominate it. **Gate:** distinguish patching the subject under test vs a legitimate dependency; Python `patch` aliases/helpers; positive and negative examples; do not replace evidence-backed inspection with a blanket mocking prohibition.

**AX-E05 — P2 — False-positive weak-oracle calibration.** `test_imported_helper_asserts` (oracle inside imported helper) and `test_parse_must_not_raise` (explicit no-exception contract) were flagged as weak. Independent repeated-call equality used to test determinism was also initially treated as a tautology candidate, although that comparison can be meaningful. **Gate:** account for contracted no-raise behavior, helper assertions when resolvable, and distinguish repeated evaluation from literal tautology; otherwise report UNKNOWN/contextual, not auto-dismiss other warnings. Related existing backlog: `TCC-A05`.

**AX-E06 — P2 — Python dev-extra preparation clarity.** `--execute --provision` may resolve the declared runtime dependencies without installing optional test extras; projects requiring pytest/Hypothesis can be BLOCKED unless the caller selects a suitable interpreter. **Gate:** preflight identifies declared optional dev requirements and distinguishes missing test dependencies from application defects, without auto-installing untrusted or undesired extras. Existing consent constraints remain.

## Proposed priority and integration

**Wave 1 — high-signal and safety:** AX-E01, AX-E02, AX-E03, AX-E04; each gets a failing reproduction/fixture *before* code changes and a positive/negative regression oracle. Separate metadata read from potentially effectful import and retain the existing read-only and consent model.

**Wave 2 — heuristic precision:** AX-E05 and AX-E06, with controlled holdout fixtures to prevent suppressing genuine weak-oracle findings.

**No new implemented capability is claimed here.** Earlier work fixed Engine-side test configuration and assertions; this PR adds only Assertiva-side feedback. Promotion to an Assertiva release requires engine changes, tests (including cross-language/OS where applicable), documentation and executed CI at the exact release candidate SHA.

## Reproduction and provenance policy

Full original vs published artifact SHA-256 values are recorded in the Engine's [hash manifest](https://github.com/Soturine/Derivanta-Engine/blob/0d846a89d4dab23aa0ab80d6eb6d4fb9f13512ab/docs/audits/assertiva/m0/artifact-hashes.json). Absolute local paths were redacted for publication, so published hashes should be checked against **published** values, not original hashes. Reports were generated by Assertiva and assessments attached through `--assessment`; do not manually edit the HTML.

The controlled fixtures `known-defects` and `main-probe` and their oracles are linked in [Audit B](https://github.com/Soturine/Derivanta-Engine/blob/0d846a89d4dab23aa0ab80d6eb6d4fb9f13512ab/docs/audits/assertiva/m0/ASSERTIVA_SELF_EVALUATION.md); the public-facing eval cases in this PR specify equivalent tests without requiring the private Engine checkout.

**What remains unknown:** quality across other languages, comprehensive runtime-self-qualification, cross-OS compatibility, independently judged precision/recall, and actual CI behavior for this PR while Actions are blocked. External study is not a substitute for those runs.
