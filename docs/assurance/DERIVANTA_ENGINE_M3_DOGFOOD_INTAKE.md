# Derivanta Engine M3 — Assertiva 0.10.0 dogfood intake and engineering feedback

**Status:** DOCUMENTED / NOT IMPLEMENTED IN ASSERTIVA. **Observation date:** 2026-11-01.
**Subject:** Derivanta Engine M3, final revision `562d2ec6ed863060578cd513a0f1f6a5e51d41f4` (checkpoints CP0–CP10 from
`0be2a38`).
**Instrument:** released **Assertiva 0.10.0** wheel `assertiva-0.10.0-py3-none-any.whl`, SHA-256
`5c96356a47dce59e68851f90c91b8feba2dc7c5d93f7d291eb26a2dc13a2adc1` (equal to the release digest), own venv, on a
Windows 10 machine with CPython 3.12.6; source `2e34542b4d04f2553618875498cd0e71842b9196`, unchanged.
**Relationship:** third round after the M0.1/M1 and M2 intakes in [PR #3](https://github.com/Soturine/Assertiva/pull/3).
Those records stay authoritative for their rounds; nothing here says an AXF item was repaired.

**Provenance:** the Engine round executed Assertiva directly (static audits of the Engine at CP0, CP1, CP3, CP8, CP10;
synthetic fixtures; one `--dependencies` run). The same model family built the Engine, ran the audits and judged the
results: self-review plus tool evidence, not an independent qualification.

## 1. Primary sources (immutable Engine links)

| Source | What it establishes |
| --- | --- |
| [Assertiva feedback](https://github.com/Soturine/Derivanta-Engine/blob/562d2ec6ed863060578cd513a0f1f6a5e51d41f4/docs/audits/m3/ASSERTIVA_FEEDBACK.md) | AXF-M3-01, AXF-M3-02 with reproducers; recheck of AXF-01..08 and AXF-M2-01 |
| [Assertiva dogfood A/B/C](https://github.com/Soturine/Derivanta-Engine/blob/562d2ec6ed863060578cd513a0f1f6a5e51d41f4/docs/audits/m3/ASSERTIVA_DOGFOOD.md) | Per-checkpoint use, results and attribution |
| [Findings ledger](https://github.com/Soturine/Derivanta-Engine/blob/562d2ec6ed863060578cd513a0f1f6a5e51d41f4/docs/audits/m3/FINDINGS.md) | 69 entries; `M3-AS-*` rows are Assertiva-related |
| [Run manifest](https://github.com/Soturine/Derivanta-Engine/blob/562d2ec6ed863060578cd513a0f1f6a5e51d41f4/docs/audits/m3/RUN_MANIFEST.json) | Commands, exit codes and report hashes |
| [M3 report](https://github.com/Soturine/Derivanta-Engine/blob/562d2ec6ed863060578cd513a0f1f6a5e51d41f4/docs/milestones/M3_REPORT.md) | What the round built, measured and learned |
| [Dogfood on four stacks](https://github.com/Soturine/Derivanta-Engine/blob/562d2ec6ed863060578cd513a0f1f6a5e51d41f4/docs/audits/m3/DOGFOOD.md) | Engine results on Rust, Kotlin, TypeScript and Python repositories (context for the advisory notes below) |

Raw Assertiva reports stay outside Git; the Engine records their SHA-256 (e.g. CP0 `9d229209…a19967`, CP3 `96fec134…1454b1`).

## 2. How much did Assertiva help in M3?

| Checkpoint | What ran | Contribution | Classification |
| --- | --- | --- | --- |
| CP0 | static audit of the Engine at `0be2a38` | 4 findings; `NO_ASSERTION` already known as a false positive since M0; `CI_PYTEST_NOT_OBSERVED` new in this form | AXF-M3-01 (false positive) |
| CP1 | static audit after 26 new exclusion tests | no weak-oracle signal on the new tests | no new defect |
| CP3 | static audit after the MCP and application-layer tests | `ERROR_CONTRACT_FIELD_NOT_OBSERVED` on one test: the textual error code was never pinned, so the test was strengthened and the re-audit was clean | **real improvement** + AXF-M3-02 (imprecise evidence wording) |
| CP8 | rechecks on regenerated M1 fixtures and an Engine `--dependencies` run | AXF-01/02/03/07/M2-01 reproduced | see §4 |
| CP10 | static audit of the final tree | no signal on the new routing/registry tests | no new defect |

Every Engine defect found in M3 (Windows output encoding and line endings, an MCP SDK default that ignored misspelt
arguments, a scope bug in exclusions, duplicated validation, a dead test constant) came from code reading, the Engine's
own gates/equivalence tests or its self-scan, **not** from Assertiva. That is reported as a fact about this round, not
as a weakness: the Engine's suite was already heavily gated, and the instrument's useful signal was narrow and real.

## 3. New findings

### AXF-M3-01 — CI that runs pytest through a repository script is reported as "no pytest in CI" (FALSE_POSITIVE, P2)

- **Rule:** `CI_PYTEST_NOT_OBSERVED` (medium).
- **Reproducer:** two synthetic projects identical except for the CI step.

  ```yaml
  # indirect/.github/workflows/ci.yml
  steps:
    - uses: actions/checkout@v4
    - run: pip install pytest
    - run: python tools/gate.py          # tools/gate.py: subprocess.run([sys.executable, "-m", "pytest", "-q"])
  # direct/.github/workflows/ci.yml (negative control): same, with  - run: python -m pytest -q
  ```

- **Observed (0.10.0):** `indirect` → `CI_PYTEST_NOT_OBSERVED`, `UNCLASSIFIED_VERIFICATION`, `CI_SINGLE_OS`; `direct` →
  `CI_SINGLE_OS` only.
- **Expected:** an unclassified step is not evidence of absence. Either follow one level of a repository-local script
  statically, or keep the step as UNKNOWN (`UNCLASSIFIED_VERIFICATION` already does) without a medium recommendation to
  "add the test suite to the pipeline".
- **Impact:** every project with a single gate script (the Engine's own pattern: CI calls `tools/verify.py`) receives
  a medium finding recommending work that is already done.
- **Regression oracle:** the two fixtures; plus a third whose script does **not** run pytest, which must keep the finding.
- **Duplicates:** none — AXF-02 is about multi-line `run:` blocks, AXF-05 about unittest start directories.

### AXF-M3-02 — `ERROR_CONTRACT_FIELD_NOT_OBSERVED` says "only check the type" when other fields are asserted (P3)

- **Test that triggered it:** asserted `raised.value.exit_code == code` and `json.loads(cli_out) == raised.value.payload()`
  (code, exit code, message and details compared with the CLI). The finding summary said the tests "only check the type".
- **After adding** `raised.value.code == kind`, the finding disappeared: the detector recognises an attribute named
  `code`, not `exit_code` or a whole-payload equality.
- **Assessment:** partly useful (the textual code was not pinned; pinning it was a genuine improvement) but the
  evidence text is false as stated.
- **Expected:** name the observed and unobserved fields ("asserts `exit_code` and a payload equality; `code` is not
  pinned"), or treat a full-payload equality as observing every field.
- **Regression oracle:** three variants of one test — type only (finding), `exit_code` only (finding naming `code`),
  `code` asserted (no finding).

## 4. Recheck of earlier IDs against 0.10.0 (re-executed in M3)

| ID | M3 status | How |
| --- | --- | --- |
| AXF-01 | **REPRODUCED** | `audit . --python .venv/Scripts/python.exe --dependencies` on the Engine → `FileNotFoundError`, exit 1; the same with an absolute interpreter path → exit 0 |
| AXF-02 | **REPRODUCED** | `c1-multiline-both` → `CI_TEST_EXECUTION_GAP` (high) for `b/tests/test_b.py` although the step runs both suites |
| AXF-03 | **REPRODUCED** | `c2-determinism::test_assigned` → `FALSE_GREEN_CANDIDATE` SELF_REFERENTIAL_ORACLE |
| AXF-04 | NOT RE-EXECUTED | needs a mutation run with a long survivor list |
| AXF-05 / AXF-06 | NOT RE-EXECUTED | need `--execute` on the Framework suites / with Hypothesis |
| AXF-07 | **REPRODUCED** | `c1-multiline-both` → `REDUNDANCY_CANDIDATE` for tests importing different `lib` modules |
| AXF-08 | NOT RE-JUDGED | semantic Skill review; no independent judge available |
| AXF-M2-01 | **REPRODUCED** | `assert add(1, 2) == 4 or True` not reported; `assert True` in the same file reported TAUTOLOGY; control `assert add(1, 2) == 3` not reported |

Fixtures were regenerated outside both repositories from the M1 generator kept in the Engine
(`docs/audits/assertiva/m1/assertiva-self/fixtures/audit_c_fixtures.py`).

## 5. Observations relevant to Assertiva's roadmap (not defects)

1. **Dependency advisories are out of scope for `--dependencies` ("vulnerabilities are not looked up").** In the same
   round, `pip-audit` and `npm audit --package-lock-only` on two owner projects found real advisories on *resolved*
   versions (e.g. a TypeScript MCP SDK in the 2.0–2.2 advisory window; `pypdf` 6.19.0 with seven CVEs). If Assertiva
   ever reports dependency readiness, an optional, clearly-labelled advisory adapter (network, DECLARED claims of the
   advisory database, resolved ≠ installed) would add value; keep it opt-in.
2. **Windows path length.** Long working directories break git fixtures and clones silently (`MAX_PATH`); a clone of a
   1 512-file repository under a long path checked out 100 files with an empty index and no error from `git clone -q`.
   Assertiva copies projects into temporary folders: worth a guard or a diagnostic when the copy path is long.
3. **`STATE_AFTER_REJECTION_NOT_EVIDENCED` on validation-only tests.** It lists tests that reject a pydantic model at
   construction, where no object or state exists afterwards (2 of 20 read). Consider not flagging constructor-level
   rejection of immutable values.

## 6. Proposed follow-up (ranked)

| Rank | Item | Why first |
| --- | --- | --- |
| 1 | AXF-M3-01 (+ AXF-02, AXF-05: CI scope fidelity) | wrong recommendations on common CI patterns; three related CI findings can share one design |
| 2 | AXF-M2-01 | an always-true assertion is the canonical false green the tool exists to catch; reproduced again |
| 3 | AXF-01 | crash on a common invocation; small fix (canonicalize before changing directory) |
| 4 | AXF-M3-02 | evidence wording; improves trust in an otherwise useful signal |
| 5 | observations §5 | product decisions, not defects |

No Assertiva code, version, tag or release is changed by this intake.
