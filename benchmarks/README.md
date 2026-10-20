# Benchmarks

Executed measurements of Assertiva's own capabilities on labeled inputs, and the protocol for comparing Assertiva with
other tools. A benchmark result is evidence about its fixtures, versions and conditions; it is never a general claim,
and a documentary comparison (what another tool's documentation says) is never presented as an executed one.

## Sets: calibration and confirmation

| Set | Where | Used for |
| --- | --- | --- |
| Calibration | `tests/fixtures/effectiveness-matrix/` and the unit tests in `tests/test_effectiveness.py` | designing and tuning rules; regression tests |
| Confirmation v1 — **spent, regression** | `tests/fixtures/confirmation/v1/` | used to find and fix a defect in 0.7.3; its results are pinned in `tests/test_benchmark_harness.py` so a lost detection or a new false positive shows; no longer evidence of how the rules generalize |
| Confirmation v2 — **frozen** | `tests/fixtures/confirmation/v2/`, digests in `benchmarks/confirmation-v2.sha256` | measuring rules after a change; never read to design or tune one. Any edit fails `test_v2_is_frozen`; a new set gets a new name |

Fixtures live under `tests/fixtures/` so that an audit of this repository treats them as inputs of its tests, not as
its own tests (a seeded defect must not count as a defect of Assertiva).

Rules of the confirmation set:
- Labels are written by a person with the fixture, before any scoring run, and say what a careful reviewer concludes
  about each test, not what a tool reports. Every test the extractors find must be labeled; a missing or extra label
  makes the fixture invalid instead of silently scored.
- Each fixture mixes real defects with correct tests that look like defects (a condition that only skips, a sleep that
  is the behavior under test, distinct rows that repeat values across stacked tables, settings that look like rows).
- When a confirmation result exposes a defect, the defect is reproduced in the calibration tests and fixed there; the
  confirmation fixture is then **spent** for that rule and the next measurement of that rule needs a new fixture. The
  history below records each such use.
- Fixtures are written from scratch with generic domains; nothing is derived from a real or proprietary system.
- A frozen set's individual misses are not backlog items: changes are designed from research, calibration and the
  regression set, then measured on the frozen set. The scorer prints the misses for whoever runs it; this page records
  the aggregate.

## Effectiveness benchmark (`benchmarks/effectiveness.py`)

```
python benchmarks/effectiveness.py [--json OUT] [FIXTURE_DIR ...]
```

Static only: reads the fixtures with the same extractors and rules as `assertiva audit`, runs nothing. Reports per
fixture and per candidate kind (FALSE_GREEN, WEAK_ORACLE, FIDELITY_MISMATCH, REDUNDANCY, DUPLICATE_CASES, SMELL), at
(test, kind) granularity:
- **precision** and **recall** against the labels, with the missed tests and false positives named;
- **correct tests nominated**: look-alikes the rules wrongly flagged;
- **cost**: seconds of static reading; whether project code was executed (never, for this benchmark);
- **safety**: the fixture's tree fingerprint before and after (the reading must not write).

Exit status 1 when a fixture is invalid or changed. Precision and recall are reported, not gated: a threshold would
turn the confirmation set into a tuning target.

### History

| Date | Revision | Fixtures | Precision | Recall | Notes |
| --- | --- | --- | --- | --- | --- |
| 2026-10-19 | 0.7.3 working tree, before the redundancy fix | py-loans, js-shipping, kt-thermostat (39 tests, 24 labeled pairs) | 0.92 | 0.958 | 2 false REDUNDANCY (same body, different `@CsvSource` tables); 1 miss: `test.each` bodies are not read for oracles |
| 2026-10-19 | 0.7.3 working tree, after the redundancy fix | same | 1.0 | 0.958 | the redundancy fix was reproduced in `tests/test_effectiveness.py`; **kt-thermostat and py-loans are spent for REDUNDANCY** |

| 2026-10-19 | 0.7.3 working tree | **v2** (frozen at creation): py-parking, js-tickets, kt-library (32 tests, 20 labeled pairs) | 1.0 | 0.70 | baseline at freeze: 14 tp, 0 fp, 6 fn (FALSE_GREEN 3, WEAK_ORACLE 3); no rule was changed after it |
| 2026-10-19 | 0.8.0 `c72d655` (new Python rules: no-op mock checks, self-referential oracles) | v1 (regression) and v2 (frozen, unchanged) | v1 1.0 / v2 1.0 | v1 0.958 / v2 0.70 | no new false positive; no recall change on v2, which has no case of either new pattern (their evidence is the calibration tests and the run on this repository's suite) |
| 2026-10-20 | 0.9.0 `c78d152` (JS/TS and JVM no-op, tautology and self-referential rules; oracle basis; fidelity ladder) | v1 (regression) and v2 (frozen, unchanged) | v1 1.0 / v2 1.0 | v1 0.958 / v2 0.70 | no new false positive and no recall change; the new rules' evidence is the calibration tests and 250 third-party test files (44 genuine signals, all in zod 4.6.7's own tests) |

Both sets were written and labeled by the same person who changed the rules in 0.7.3, after reading those rules;
v2 uses idioms v1 does not (unittest assertions, Jest `describe`/`it`, Kotlin `runCatching`, text blocks) but it is
still not an independent benchmark. A second labeler reviewing v2's labels (agreement recorded) is the next step before
its results are quoted outside this repository. Independent labeling (a second labeler, agreement
recorded) is part of the competitive benchmark below.

## Competitive benchmark design (prepared, not executed)

How Assertiva will be compared with other tools (ROADMAP after 0.7.2: M9). Nothing here has been run yet.

**Fair conditions.** Same fixture revision, same machine and environment, each tool's version and configuration
recorded, the same time budget, the same scope (the files each tool is given). A tool run under different conditions is
reported apart. Tools that need installation, network or services run only in a disposable environment the owner
authorized; the run records what was installed. Closed or unavailable tools are compared from their documentation only,
in a separate "documentary" column.

**Scenarios, each with known defects and negative controls:**
- false greens (swallowed failures, conditional checks, tautologies, unawaited async) and correct look-alikes;
- oracle strength (existence, truthiness, bare status, broad errors) against tests whose contract is presence;
- mutation sensitivity: a seeded defect per behavior, with the tests that must and must not detect it;
- integration/E2E fidelity: tests declared integration that simulate every boundary, and ones that cross a disposable
  real dependency;
- true and false redundancy (identical bodies over different inputs, platforms or configurations);
- protection after refactoring: a behavior-preserving refactor and a behavior-changing one;
- generated or strengthened tests: kept only if they fail on a negative control or mutant;
- selection: changes with known affected tests, measured as missed detections;
- execution safety: fixtures that try to write to their tree, read credentials or reach the network;
- agent-led investigation: `evals/cases` run with the same protocol for every agent configuration.

**Metrics.** Precision, recall and false positives on correct look-alikes per scenario; detected seeded defects;
missed selections; wall time and tokens (agents); writes to the fixture tree, credentials or connections reached;
reproducibility (two runs, same results).

**Acceptance.** A capability is claimed better than another tool only when both ran under the conditions above on the
same scenarios and the difference holds on the confirmation set; otherwise the comparison says "not compared" or
"documentary".
