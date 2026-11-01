# Release readiness — Assertiva 0.10.1 candidate

**Decision: not released.** The candidate is qualified locally (Windows, Linux) and by its own probes, dogfood and
benchmarks; publishing needs the owner's approval, the remote CI run of the final commit, and — for AXF-08 — a
semantic evaluation the owner has to budget. Nothing here is a tag or a GitHub Release; `pyproject.toml` says
`0.10.1.dev0`.

Baseline: 0.10.0 `2e34542`. Branch: `fix/assertiva-0.10.1-dogfood` (PR into `main`; a direct push to `main` was
refused by the session's permission policy). Items, tests and commits:
[REMEDIATION_0_10_1.md](REMEDIATION_0_10_1.md); reasoning: [ENGINEERING_JOURNAL_0_10_1.md](ENGINEERING_JOURNAL_0_10_1.md).

## What each kind of evidence says

| Evidence | Where | Result |
| --- | --- | --- |
| Fail-before / pass-after | 0.10.0 worktree vs branch, same tests | every new regression test fails on `2e34542` and passes on the candidate, except the controls, which pass on both by design |
| Probes of the intake reproducers | [fail-before](evidence/derivanta-0.10.1/fail-before-0.10.0.json), [pass-after](evidence/derivanta-0.10.1/pass-after-candidate.json) | 14/14 probes reproduce the defects on 0.10.0 and pass on the candidate with controls kept |
| Installed wheel | `assertiva-0.10.1.dev0-py3-none-any.whl`, clean venv, run outside the repository with `-I` | probe results identical to the source tree (`assertiva` imported from the venv) |
| Real subject, executed | Derivanta Framework `218761d`, `audit --execute` in a disposable copy | 5 declared roots, 79 test methods (78 pass, 1 fail) = M1's independent count; 0.10.0: 0 executed |
| Real subjects, static | Derivanta Engine `0be2a38`, Assertiva itself, two third-party repositories (Node, Django) | only the intended changes; no new false positive; the new rules have no positive in these projects (no measured gain there) |
| Frozen confirmation sets v1+v2 | `benchmarks/effectiveness.py` | precision 1.0, recall 0.841 (37/0/7) on both 0.10.0 and the candidate: no regression, no gain |
| Cost | static self-audit | 18.8 s vs 17.4–18.7 s on 0.10.0 (two runs each) |
| Targeted mutation | `benchmarks/self_mutation.py` | `assertiva/ci.py`: refused, 371 planned > 300 budget (DG-0101-12, BLOCKED). `assertiva/assessment.py` (ec5c796): 240 mutants, 162 killed, 73 survived (22 annotation candidates), 3 timeout, 2 error; scope-path survivors pinned by new tests (DG-0101-13); rerun on `4e2268c`: 181 killed, 57 survived, 0 timeout, 2 error |
| Local suites, Windows | `pytest -m "not integration and not artifact"` / `-m "(integration or artifact) and not browser and not jvm"` | core 1094 passed / 5 skipped, integration 167 passed / 11 skipped (exit 0) |
| Local suites, Linux | the same commands in `python:3.12-slim` on a `git archive` of `9f64c03` | core 1095 passed, integration 169 passed / 13 skipped (exit 0) |
| Remote CI | GitHub Actions | `4e2268c`: push [41341845670](https://github.com/Soturine/Assertiva/actions/runs/41341845670) 7/7, pull_request [41341849603](https://github.com/Soturine/Assertiva/actions/runs/41341849603) 7/7; Runtime self-qualification not run (tags / dispatch only) |
| Semantic evaluation (AXF-08) | `evals/semantic.py` with a separate agent and judge | **NOT_RUN** — owner budget approval; the Derivanta M1 REVIEW stands |

## Contract changes a consumer may notice

- `MUTATION_SURVIVORS` / `MUTATION_REPORT_UNTIED` evidence gains `count`, `listed`, `truncated`, `sites`,
  `mutant_ids`, and lists not-covered mutants (suffix `[no coverage]`); an assessment's scope must now match the
  complete count. `survivor_sites` is complete and gains `mutant_id` and `status`.
- Nine other findings gain `count`; `ERROR_CONTRACT_FIELD_NOT_OBSERVED` has a new summary and `asserted` /
  `detail_asserted_elsewhere`.
- New findings: `CI_TESTS_RUN_THROUGH_SCRIPT` (info), `CI_TEST_STATUS_MASKED` (medium), `PROJECT_ENTRIES_UNREADABLE` (high); `boundary` data gains `unreadable`. New assertion kind
  `TYPED_ERROR_BOUNDARY`, oracle `TYPED_ERROR`. Python `SELF_REFERENTIAL_ORACLE` and the JavaScript/JVM
  call==call TAUTOLOGY/SELF_REFERENTIAL readings become the weak `DETERMINISM` oracle.
- A run with several declared unittest invocations carries `declared_invocations`; its status is the worst part's.
- `--python` that names nothing exits 2 (argparse error) instead of a traceback.

All additive to the JSON schema (`schemas/assurance-report.schema.json` does not constrain the changed objects), but
an assessment that relied on the cut list as its denominator is now rejected — on purpose.

## Still open (not blockers for a maintenance candidate, recorded with a next step)

- AXF-08 semantic evaluation (budget); DG-0101-12 / IDEA-02 mutation of
  modules over 300 mutants; IDEA-01 advisory lookup (deferred); TCC-A02/A06/A12 from 0.10.0 remain as they were.

## To publish 0.10.1 (owner)

1. Review and merge the PR into `main` (no squash, as for 0.10.0), after its CI run is green.
2. Optionally approve a budget for the AXF-08 semantic evaluation and record the verdict.
3. Set `version = "0.10.1"`, date the CHANGELOG entry, tag `v0.10.1`, build wheel and sdist from the tag with SHA-256
   checksums, publish the GitHub Release.
