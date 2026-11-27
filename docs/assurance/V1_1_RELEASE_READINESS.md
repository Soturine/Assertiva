# v1.1.0 release readiness

Branch `integration/v1.1-foundation` (PR #13), candidate `1.1.0rc1`, version `1.1.0` on this branch. The owner authorized merging everything into `main`, tagging and releasing on 2026-11-27; the final addendum (CP-FINAL-A/B/C) was applied before publication. The publication record (merge and tag SHAs, CI runs, asset checksums) is the GitHub Release `v1.1.0`, not this file.

**Recommendation: CONDITIONAL** — engine, demos and CI qualification hold; the agent evaluations are NOT_RUN and need the owner's explicit decision (accept as a documented limitation, or approve a budget) before publication. The engine contracts, the demos and the local qualification hold; publishing 1.1.0 still needs (1) the GitHub CI full qualification of the final SHA green, (2) the owner's decision on the agent evaluations that were not run (blind multimodal reading, PR #12's cases), and (3) explicit authorization to merge, tag and release.

## Checkpoints

| CP | Scope | State | Evidence |
| --- | --- | --- | --- |
| CP0 | real state, baseline, #11/#12 integration, architecture map, decisions | IMPLEMENTED_AND_VERIFIED | [V1_1_BASELINE_AND_INTEGRATION](V1_1_BASELINE_AND_INTEGRATION.md) |
| CP1 | documentary context, native-first reading, read states, denominators | IMPLEMENTED_AND_VERIFIED (engine); multimodal agent capability demonstrated once, not blind | `assertiva/context.py`, `tests/test_context_traceability.py`; visual read of the demo PDF ([V1_1_DOGFOOD](V1_1_DOGFOOD.md) §1) |
| CP2 | traceability, authority, coverage dimensions, status strength, selective invalidation | IMPLEMENTED_AND_VERIFIED | same files; demo: PROVEN_IN_SCOPE only with a detected break |
| CP3 | adaptive tool discovery on stacks without an adapter | IMPLEMENTED_AND_VERIFIED for Ruby and .NET 10 (real runners, Stryker.NET, manual negative control, receipts); C++ NOT_RUN | `assertiva/receipts.py`, `references/ADAPTIVE_TOOLS.md`, V1_1_DOGFOOD §2 |
| CP4 | providers and independent reviews | contract IMPLEMENTED_AND_VERIFIED (consent, independence, no status change); provider integration DEFERRED; no real second-model review run | `assertiva/reviews.py`, tests |
| CP5 | portable dogfood | IMPLEMENTED_AND_VERIFIED (engine-only, agent-led, sanitization canaries, disable, failure path) | `assertiva/dogfood.py`, `schemas/assertiva-dogfood.schema.json`, tests |
| CP6 | Portfolio import, lifecycle, report sections | IMPLEMENTED_AND_VERIFIED (two installations, idempotency, dry run, regression by version, resolved commits) | `assertiva/portfolio.py`, V1_1_DOGFOOD §3 |
| CP7 | qualification, experiments, dogfood | PARTIAL: engine suites and demos done; agent evaluations NOT_RUN | below |
| CP8 | docs, contracts, PR, candidate | IMPLEMENTED (this document, CHANGELOG, MIGRATION_V1_1, release-notes draft) | — |

## Local qualification (Windows 11, CPython 3.12.10)

| Revision | Command | Result |
| --- | --- | --- |
| `b615b13` (main, baseline) | `pytest -q -n auto -m "not browser and not jvm"` | 1349 passed, 19 skipped, 0 failed |
| `bd50683` (candidate, first full run) | same | 1387 passed, 19 skipped, 3 failed — a missing pt-BR template for the new re-rooting limitation, and two tests pinning the report directory to two files; fixed in `978069e` |
| `978069e` (candidate, final code) | same | **1391 passed, 19 skipped, 0 failed** (510 s); +42 tests over the baseline |
| `tests/test_installed_artifact_context.py` | wheel built and installed outside the checkout, self-tests run without git or source package | 2 passed |
| Ruff (`ruff==0.17.3`) | `ruff check .` | All checks passed |
| `scripts/validate_repo.py` | — | passed |
| Wheel / sdist from `git -c core.autocrlf=false archive` | `python -m build` | `assertiva-1.1.0rc1-py3-none-any.whl` sha256 `60f6a98b…64e3b`; installed in a clean venv and run with `python -I -m assertiva.cli` (App Control blocks pip launchers in temporary venvs on this machine) |

The browser and JVM suites, Linux and Python 3.11 run in GitHub CI (full qualification by `workflow_dispatch` on the final SHA).

## Fail-before / pass-after

| Change | Before (`b615b13`) | After |
| --- | --- | --- |
| #11 environment build cause | collection error | 10 passed |
| Re-rooted mutation report | `test_a_report_from_another_root_is_tied_by_identical_content` fails; control passes | both pass |
| Feedback regression by version | (contract change: old test expected REGRESSION for the same version) | same version → `before_fix`; newer → REGRESSION |

## Agent evaluations

NOT_RUN. Proposed set (needs the owner's budget approval before any agent runs; estimate ~40k tokens per evaluated run and 20–40k per judged case, historically ~2× low): blind reading of the demo PDF with a text-only control and an irrelevant-figure control; PR #12's qualification candidates (paraphrased oracles, empty green, seeded defect, cloned test with changed permission, inaccessible diagram, stale source, fabricated PASS, legitimate characterization); one unknown-stack discovery case. Gold and rubrics must be frozen before the runs; the author and the judge must be different model families or the limitation stated.

## Residual risks

- Reading is agent-reported; the engine cannot detect a confident misreading of a figure. Mitigation: citations must be inside what was read; independent reviews are recorded; blind evaluations pending.
- The dogfood sanitizer is pattern-based; files are LOCAL_ONLY and require human review before sharing.
- Receipts prove integrity of cited files and agreement of counts, not that the tool ran as declared.
- A 1.0.x engine silently ignores the new assessment sections.

## Publication plan (only on explicit authorization)

1. Confirm CI full qualification green on the final SHA; mark the PR ready.
2. Bump `1.1.0rc1` → `1.1.0`, update CHANGELOG date and release notes; rerun the local suites and the wheel smoke on that SHA.
3. Merge with a merge commit (no squash/rebase), guarded by the expected head SHA; confirm #11 and #12 show as merged.
4. Wait for CI on `main`; annotated tag `v1.1.0` on the merge commit; wait for the tag CI.
5. Build wheel and sdist from `git -c core.autocrlf=false archive v1.1.0`, verify metadata, entry point and an install outside the checkout; `SHA256SUMS`; publish the GitHub Release as Latest with the notes. No PyPI, no ruleset or branch changes.
