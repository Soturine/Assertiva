# VozNativa v0.4 hardening / v0.5 — Assertiva 0.10.1 dogfood intake

**Status:** DOCUMENTED / NOT IMPLEMENTED IN ASSERTIVA. **Observation date:** 2026-11-05.
**Subject:** VozNativa (Python library, CLI and Agent Skill; tests run by stdlib `unittest`), revisions `4044cfc` → `5d7ae60`.
**Instrument:** Assertiva **0.10.1**, wheel built from tag `v0.10.1` (`2618d95`) into its own venv; project venv with PyYAML, coverage 7.17.2, build 1.6.1, Cosmic Ray 8.7.0; Windows 11, CPython 3.12.10.
**Provenance:** the same model family built VozNativa, ran Assertiva and judged the results: self-review plus tool evidence, not an independent qualification. Nothing in Assertiva was changed for this round.

## 1. Primary sources (immutable VozNativa links)

| Source | What it establishes |
| --- | --- |
| [Dogfood ledger](https://github.com/Soturine/VozNativa/blob/5d7ae603b3ecc715da66cc5c7e8fa8d72e04c9db/evals/assurance/DOGFOOD.md) | every item, with hypothesis, reproduction, expected, observed and forwarding state |
| [CP0 run](https://github.com/Soturine/VozNativa/tree/5d7ae603b3ecc715da66cc5c7e8fa8d72e04c9db/evals/assurance/runs/2026-11-05-cp0-baseline) | static and `--execute` audits (sanitized JSON, raw/published SHA-256), negative controls NC1–NC4b, analysis |
| [CP4 mutation run](https://github.com/Soturine/VozNativa/tree/5d7ae603b3ecc715da66cc5c7e8fa8d72e04c9db/evals/assurance/runs/2026-11-05-cp4-mutation) | the `--mutate --mutate-tests FILE` audit that ran no mutant, and the agent's own Cosmic Ray runs |

## 2. How much did Assertiva help?

| Use | Contribution | Classification |
| --- | --- | --- |
| static audit at `4044cfc` | `FALSE_GREEN_CANDIDATE` (`CONDITIONAL_ASSERTION`, 4 tests) → negative controls: 1 confirmed (a frozen-holdout check that a renamed manifest key turned vacuous), 1 contextual, 2 false positives in practice | **real defect found and fixed** in VozNativa (`ada5aa6`); AXF-VN-02 for the recommendation |
| `--execute` | native unittest run in a disposable copy (281 then 316 invocations, exit 0), coverage measured (product 91.0% lines / 84.5% branches), wheel built and installed without index | trustworthy runtime evidence for the round |
| `--execute --mutate … --mutate-tests FILE` | no mutant ran | AXF-VN-01 |
| synthetic reproducer | `TAUTOLOGY` and a real survivor (`x > 0 → x != 0`) correctly reported | true positives |

Most VozNativa defects of the round came from its own new gates, profiling, metamorphic tests and the agent's mutation runs. Assertiva's narrow signal was real (one confirmed false green).

## 3. New findings

### AXF-VN-01 — `--mutate-tests FILE` fails under unittest (P1)

Reproduction (synthetic, no VozNativa code):

```bash
mkdir -p proj/calc proj/tests proj/.github/workflows && cd proj
printf 'def add(a, b):\n    return a + b\n\n\ndef is_positive(x):\n    return x > 0\n' > calc/__init__.py
printf 'import unittest\nfrom calc import add, is_positive\n\n\nclass T(unittest.TestCase):\n    def test_add(self):\n        self.assertEqual(add(2, 3), 5)\n\n    def test_positive(self):\n        self.assertTrue(is_positive(1))\n        self.assertFalse(is_positive(0))\n' > tests/test_calc.py
touch tests/__init__.py
printf 'name: CI\non: [push]\njobs:\n  test:\n    runs-on: ubuntu-latest\n    steps:\n      - uses: actions/checkout@v4\n      - run: python -m unittest discover -s tests -p "test_*.py" -v\n' > .github/workflows/ci.yml
git init -q && git add -A && git commit -qm repro
assertiva audit . --execute --python <venv-with-cosmic-ray>/python --mutate calc/__init__.py --mutate-tests tests/test_calc.py --output json
```

- Expected: the baseline and every mutant run only `tests/test_calc.py` (the `--help` text says "files or folders").
- Observed: the selection becomes `unittest discover -s tests/test_calc.py` → `ImportError: Start directory is not importable: 'tests/test_calc.py'`; `evaluated: 0`; finding `MUTATION_REPORT_UNREADABLE` ("a mutation report could not be read").
- Positive control: `--mutate-tests tests` → 18 mutants, 17 killed.
- Impact: targeted mutation is impossible on unittest projects whose whole suite is slow (VozNativa: 70 s per run, 825 mutants in one module); the label points at the report instead of the selection.
- Proposed fix: map a file to `discover -s <dir> -p <file name>` (or a dotted module id), and report a selection failure as such.

### AXF-VN-02 — `CONDITIONAL_ASSERTION` recommends the wrong fix for filtered properties (P3)

```python
CASES = [(1, True), (0, False), (5, True), (-2, False)]

class Property(unittest.TestCase):
    def test_positive_cases_are_accepted(self):
        for value, expected in CASES:
            if expected:
                self.assertTrue(is_positive(value), value)
```

- Observed: `FALSE_GREEN_CANDIDATE` / `CONDITIONAL_ASSERTION`, recommendation "make the check unconditional".
- Negative control: `return x > 3` instead of `x > 0` → the test fails. The test protects the behavior; the real risk is vacuity if the selection stops matching.
- In VozNativa, 2 of 4 candidates had this shape; the confirmed one (NC1) was also a filter, over manifest flags.
- Proposed fix: a `FILTERED_LOOP_ASSERTION` sub-pattern whose `resolve_with` is a non-vacuity assertion (count the cases that reached the assertion) or a negative control on the selection, instead of "make it unconditional".

### AXF-VN-03 — unittest runs carry no source identity (P2)

Every `--execute` run through the unittest adapter (VozNativa and the reproducer) has `source_identity`, `interpreter` and `temp_root` = `null`; pytest runs record them (`references/ENGINE.md`: "read them before trusting a green run"). A green unittest run therefore cannot show which copy of the code it imported. Proposed fix: record module origins in the unittest evidence module the adapter already injects.

### AXF-VN-04 — installed-wheel tests NOT_RUN for unittest projects (P2)

On VozNativa, artifact qualification reports `tests: NOT_RUN — "no test runner adapter for this project"` although the unittest adapter ran the source tree in the same audit. Proposed fix: reuse the unittest adapter for the installed-artifact run.

### AXF-VN-05 — stdlib-only project without CI or config is treated as pytest (observation)

The reproducer without `.github/` produced `pytest-native BLOCKED` and `ENVIRONMENT_NOT_PREPARED` instead of trying `unittest discover` (no pytest installed, only `unittest.TestCase` tests). Proposed: fall back to stdlib discovery when pytest is absent and only `TestCase` classes exist, or say the runner is unknown.

## 4. Not a defect

A machine-global editable install answered `assertiva 0.10.1` while pip metadata said `0.5.5` (stale editable install). The round used its own venv from the tag; recorded as environment hygiene only.


## Update 2026-11-06 — VozNativa v0.7.0 round

| Item | State | Evidence |
|---|---|---|
| AXF-VN-01 | **fixed on this branch** (not released) | `assertiva/adapters/cosmic_ray.py::test_command_for`; tests in `tests/test_cosmic_ray.py` (5, including a negative control that runs the old command and sees "not importable") and `tests/test_mutation_tools.py::test_cosmic_ray_runs_only_a_selected_unittest_file` (Cosmic Ray 8.7.0, ASSERTIVA_REQUIRE_MUTATION=1: 3/3 cosmic-ray integration tests pass); full suite 1273 passed, 19 skipped (Windows, CPython 3.12.10) |
| AXF-VN-02, 03, 05 | open | unchanged |
| AXF-VN-04 | open, reproduced | `assertiva audit --execute` on VozNativa `3fb4163`: unittest PASS (660 invocations), "python-package tests against the installed wheel: NOT_RUN — no test runner adapter for this project" |
| New observation | not a defect | an `--execute` run aborted with `READ-ONLY VIOLATION` when the auditor edited the project during the run: the guard worked (no partial report) |
