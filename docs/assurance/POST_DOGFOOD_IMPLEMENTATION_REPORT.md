# Implementation report — 0.10.0 development line

Branch `feature/assertiva-0.10.0-hardening`, from `main` at `cf5cb7d` (0.9.0). Each checkpoint was committed and
pushed with `[skip ci]` (no workflow run was triggered: `gh run list --branch …` stayed empty); CI runs only on the
final push. Per-gap dispositions: [POST_DOGFOOD_GAP_MATRIX.md](POST_DOGFOOD_GAP_MATRIX.md).

## Checkpoints

| CP | Commits | What | Local evidence at the commit |
| --- | --- | --- | --- |
| CP0 entry audit | `7042c25` | [entry audit](POST_DOGFOOD_ENTRY_AUDIT.md), computable gap matrix (JSON + validator/renderer) | baseline `cf5cb7d`: 807 core, 137 integration/artifact passed |
| CP1 security | `45f5a21` | AX-E01 static closure, TCC-A16/ENG-01 wrappers, SEC-EVAL-01/02 + AG-13 eval boundary | artifact 25, eval 215 (+1 skip), Gradle/Maven/CLI 53 passed |
| CP2 evidence | `6216e62`, `171c9ad` | TCC-A01, AG-01/02/03/07/08/09/10/12, AX-E02, ENG-02 | core 915; identity/artifact/pytest 40 passed |
| CP2 oracles | `3a821ac` | AG-04/05/06, AX-E03/04/05, TCC-A05/A17 | 8 calibration tests FAIL→PASS; core 923 |
| CP3 mutation | `4dcffce`, `5377e49` | AG-11 targeted mutation (real Cosmic Ray 8.7.0), TCC-A14/A23 manual mutants | 25 mutation tests with Cosmic Ray; core 934 |
| CP3 surface | `eed84aa` | TCC-A11 script graph | core 931 |
| CP4 adapters | `0fd95b8`, `2f6ebc3` | TCC-A03 `node --test` (Node 24.19 real runs), TCC-A04/A07/A13 modalities, AX-E06 | core 952 |
| CP5 portfolio | `7412ac2` | `assertiva portfolio` registry, statuses, feedback loop, offline page | 6 portfolio tests; core 957 |
| CP6 explorer | `2fb0110` | `assertiva explain` | 3 tests incl. a real mutation run |
| CP7 dependencies | `dc01f49` | `audit --dependencies` | 5 tests; core 962 |
| CP8 dogfood + skill | `4acb036`, `e6ddd9b` | PR #1 and DrawLab evidence integrated, PRIVATE_FILE_BOUNDARY case, Skill rules | 71 cases pass the lint; core 1003 |
| CP8 self-assurance | `54cb130` | dead code and duplicates removed; helper-resolution cost and precision fixed; benchmarks | see [ASSERTIVA_SELF_DOGFOOD.md](ASSERTIVA_SELF_DOGFOOD.md) |
| CP9 qualification | final commits | docs, version `0.10.0.dev0`, schema, full local qualification, final push | [RELEASE_READINESS.md](RELEASE_READINESS.md) |

## Before / after (same inputs)

- Every new or changed test file fails or cannot import on pure 0.9.0 (clean venv, worktree at `cf5cb7d`):
  [evidence/fail-before-0.9.0.txt](evidence/fail-before-0.9.0.txt). The 0.9.0 passes inside those files are the
  negative controls that must already hold.
- Frozen confirmation sets v1+v2: unchanged, precision 1.0 / recall 0.841 on both (no regression, no gain there).
- Static self-audit of this repository: 16.8 s → 19.7 s, identical findings.
- Contract changes (deliberate, in the CHANGELOG): `f(x) == f(x)` is DETERMINISM (weak) instead of TAUTOLOGY;
  failure origins outside the project's code are no longer PRODUCT; relative Windows paths normalize in failure
  signatures; a job with `defaults.run.working-directory` is no longer reproduced at the repository root. New report
  fields are additive; `dependencies` is a new optional top-level key (schema updated).

## Decisions and their reasons

- **Static closure instead of an isolated import sandbox.** An import sandbox would still run package code; reading
  modules answers the question asked (do declared dependencies cover the imports) without executing anything.
- **The eval boundary is a guard plus a canary**, not prompt text: the guard refuses tool calls on private files and
  outside paths when installed as a hook; the canary makes a read observable even without it; the safety gate is
  deterministic and outranks the judge.
- **Imported helpers only from test-support modules**: cheaper, and a product function that asserts is not an oracle.
- **No new subcommands beyond `portfolio` and `explain`**; dependencies are an `audit` option.
- **Cut:** a dashboard, SQLite storage (JSON with schema version and atomic writes suffices for the MVP), automatic
  upgrades, advisory lookups, new mutation engines.
