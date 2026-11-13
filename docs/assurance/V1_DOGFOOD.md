# v1.0 dogfood: before and after on public projects

**Instrument.** Baseline: the `v0.10.1` release wheel (sha256 `45c3a3dd…593a`, matches the release's `SHA256SUMS.txt`).
Candidate: a wheel built from `integration/v1.0-foundation`. The final runs used the wheel built after `ab38227`; the
CI and static runs below were repeated on `517ce4b`. Both wheels report version `0.10.1` because nothing was bumped,
so they are told apart by digest and commit, never by version.

**Confinement.** Projects were cloned at the SHAs below and checked out with `core.autocrlf=false`. Every execution ran
in a Docker container (`python:3.12-bookworm`) with `--network none`, the projects mounted read-only, an unprivileged
user and a tmpfs `/tmp`. The image was built once, with the network on, from pinned `constraints.txt` plus
`flit_core==4.1.0` (released 2026-09-16). Static audits of Randomizer also ran on the host, because they read files
and execute nothing. The private Derivanta Engine was **not** used.

**Attribution.** "Engine" results are what Assertiva produced. "Agent" conclusions are the operator's own reading of
those results and of the projects, and they are labeled as such.

## Runs

The same command was run with the baseline and with the candidate.

| Project (license) | Revision | Command | v0.10.1 (baseline) | Candidate | Disposition |
|---|---|---|---|---|---|
| VozNativa (owner's project) | `3fb4163` | `audit --execute --mutate voznativa/stuffing.py --mutate-tests evals/test_community_and_stuffing.py` | unittest PASS 660; `source_identity` **null**; wheel tests **NOT_RUN** ("no test runner adapter"); mutation: selection error labeled **MUTATION_REPORT_UNREADABLE**, 0 mutants | unittest PASS 660; SOURCE_TREE (48 modules observed); wheel tests **run**: 645 invocations, INSTALLED_ARTIFACT 48/48, FAIL (see below); mutation: **72 mutants, 40 killed, 32 survived**; baseline ran **13 tests of the selected file**; whole suite NOT_RUN | AXF-VN-01/03/04 FIXED |
| tomli (MIT), independent holdout | `43a86ad` | `audit --execute` | source run FAIL with a load error; wheel tests **NOT_RUN** | same source result; wheel tests **run**: **760 invocations, PASS, INSTALLED_ARTIFACT** | AXF-VN-04 FIXED on a project not used to design the change |
| idna (BSD-3), pytest control | `d357725` | `audit --execute` | FAIL: collection error; identity SOURCE_TREE | identical findings and counts (no regression); the cause is now stated: `ModuleNotFoundError: No module named 'hypothesis'` | PRE-1 FIXED; pytest path unchanged |
| Randomizer (Apache-2.0) | `fccc561` (tag `v0.7.12`) | static `audit` | `LOCAL_CHECK_NOT_OBSERVED_IN_CI` **high** (verify, verify:release, test:ui), `CI_PYTEST_NOT_OBSERVED` medium, `NESTED_SCRIPT_REPETITION` across workflows | `LOCAL_CHECK_NOT_OBSERVED_IN_CI` **medium**, test:ui only, basis UNKNOWN with `may_run_inside`; `CI_TESTS_RUN_THROUGH_SCRIPT` info (INFERRED via `npm run verify` → `tools/verify.py`); no repetition claimed | AXR-03/04/05/06 FIXED |

## What the runs found in Assertiva itself

- **The venv interpreter is a symlink (fixed in `ab38227`).** The first candidate run in Linux reported the VozNativa
  wheel run as MISMATCH, with 48 modules "outside the artifact". The code resolved the venv's `python`, which is a
  symlink to `/usr/local/bin/python3.12`, so the artifact root came out as `/usr/local`. The local Windows suite could
  not see this. After the fix, the same run is INSTALLED_ARTIFACT 48/48.
- **The synthetic reproducer was not enough (fixed in `517ce4b`).** After `2e4b437` the synthetic Randomizer
  reproducer was clean, but the real project still showed both findings. Its `tools/verify.py` keeps commands as data
  and launches them later through a variable. Only the real project exposed that shape.
- **Fail-before through an editable install.** In the fail-before worktree, a module that exists only on `HEAD`
  (`assertiva/gate.py`) was imported from the main checkout through the editable install's import finder. That is the
  same shadowing that `source_identity` detects (see [V1_REMEDIATION.md](V1_REMEDIATION.md)).

## Agent reading of the remaining failures (not engine conclusions)

- **VozNativa, tests against the wheel: FAIL.** This is a correct observation: these tests cannot qualify the installed
  wheel. It is *not* evidence that the wheel is broken. Of the two failures,
  `test_bench_v3_harness::test_runner_end_to_end_with_a_fake_model` is VozNativa's own guard ("engine imported from
  the wrong checkout"), which refuses on purpose to run from an installed copy. `test_regional` loads
  `ROOT/"voznativa"/"data"/...` from the source tree, and qualification removes that tree from the test copy.
  Recognizing tests tied to the source tree automatically is **DEFERRED** (P3). Until then the engine reports FAIL and
  the agent explains it.
- **tomli, source-tree run.** It fails on both baseline and candidate because the tests import `tomli` from a `src/`
  layout that is not installed in the project environment. tomli's own CI runs `pip install .` first. This is the
  environment, not the product, and it did not change.

## Not run

- Derivanta Engine and Framework: private repositories, so not used; synthetic fixtures cover their findings (0.10.1).
- Prescripta: not a public base. Its two fixes are covered by synthetic tests (Windows open handle, POSIX unwritable
  directory, collection causes).
- JS/TS, JVM, Gradle/Android, browser and services were not part of these confined runs. They are covered by the
  suites with `ASSERTIVA_REQUIRE_*` (locally for JS, Django and mutation; in CI for the rest).
- No agent-led audit of these projects was run. This round's agent-led evidence is [V1_AGENT_EVALS.md](V1_AGENT_EVALS.md).
