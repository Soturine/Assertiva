# Self-audit of Assertiva (static audit + targeted checks)

## Strongest claims (and how well evidenced)
1. **Audit is read-only.** Enforced at runtime by a before/after fingerprint with exit code 3. Observed directly: my first `audit .` aborted with `READ-ONLY VIOLATION` because running from workspace sources wrote `__pycache__`. That is a real E1 observation of the guard firing, though caused by my invocation. After setting `PYTHONDONTWRITEBYTECODE=1` the audit completed and made no project change. CI also checks this through the installed wheel (`git status --porcelain` before and after, and a fixture fingerprint). Strong.
2. **Core is framework-neutral.** STATUS.md says contract tests use fake adapters and fail if a core module names a tool. Related tests (`test_cross_stack_contract.py`) passed in my run. Moderate to strong.
3. **Real cross-stack evidence.** CI has dedicated `browser` (Playwright) and `java` (Maven) jobs, plus Jest via `npm ci`. Each job sets a REQUIRE env var so it fails instead of skipping. That is a good anti-silent-skip design. These jobs exist only as declared CI (E2). I did not observe them run.
4. **Honest claim boundaries.** Stability is "no instability observed", not "not flaky". Percentages over a changed denominator are UNKNOWN. Unknown CI constructs stay UNKNOWN. Static signals are labelled E3. STATUS.md is consistent with SKILL.md on this.
5. **Tests I ran:** `tests/test_repo_contract.py`, `tests/test_cross_stack_contract.py` and `tests/test_history.py` gave 60 passed and 1 failed. The failure is explained below.

## Largest unknowns and gaps
- **No test outcomes, coverage or mutation evidence** came out of the static audit. These are UNKNOWN by design without `--execute`. STATUS.md reports 310/420 tests passing, but that is a self-claim from past runs (2026-10-06, `e462547`) that I did not reproduce. The repo does not test itself with mutation or negative controls.
- **Whether CI ran and gates merges is not evidenced.** Remote CI is never queried. STATUS.md says branch protection on `main` is not configured, so green CI is advisory.
- **CI breadth is narrow.**
  - Every job runs on ubuntu-latest only (`CI_SINGLE_OS`).
  - Python 3.12 gets the full suite and 3.11 only the fast suite.
  - The runtime is developed on Windows, and the Windows path-limit fix (commit b053fb3) has no Windows CI job.
  - The Windows junction and link boundary code has no OS-matched CI evidence.
- **Self-qualification is on demand or tag-only.** It runs the fast/core suite and deselects integration and artifact tests because they already ran in `validate`. That is reasonable, but the combination is not proven in a single run.
- **Weak oracle.** `tests/test_history.py::test_history_can_be_disabled` asserts only `HistoryStore.for_project(...) is None`. Nothing proves history is not written when disabled. Only one test is flagged, so the test-quality signal is generally good.
- **State-after-rejection is not evidenced** in several apply, boundary and candidate tests (static E3 hint). The transactional apply rollback has dedicated tests (`test_transactional_apply.py`). Those tests were not run by me.
- **STATUS.md is inconsistent.** It lists Azure Pipelines, GitLab CI and Jenkins as IMPLEMENTED (ROADMAP checked too), but the PLANNED section still lists them. Skill/doc drift on maturity is a recurring theme in the recent git history.
- **Unclassified CI steps.** 5 CI steps are UNKNOWN: setup-node, `npm ci`, validate_repo, and others. `scripts/validate_repo.py` is a gate whose content the classifier does not understand.
- **Workspace caveat.** `test_repo_contract` fails here because `evals/README.md` is absent from this copy (the hidden-rubric `evals/` directory was removed). I treat this as an artifact of the evaluation copy, not a product defect. It does show the contract test depends on a directory outside the shipped package.

## Smallest additional evidence that buys the most confidence
1. Run `assertiva audit . --execute` from the installed wheel, which is what `runtime-self-qualification` does (~100 s). That gives native outcomes and wheel and closure results. I deliberately did not run it, because the task warns it is expensive and the CI evidence already exists.
2. Add a `windows-latest` job running the fast suite plus the `test_boundaries` and `test_workspace` tests. That covers links, junctions, long paths and case collisions.
3. Mutation or negative controls on the highest-risk logic: the read-only guard, the transactional apply and rollback, and the PASS/UNKNOWN aggregation. This tests the safety net directly.
4. Strengthen `test_history_can_be_disabled` to assert that no store file is created. Fix the STATUS.md PLANNED/IMPLEMENTED drift. Make `test_repo_contract` skip or declare `evals/` absence.
5. Enable branch protection on `main` and require the CI checks (an owner action) so green means gated.

## What green proves
Green `validate` proves the fast, integration and artifact suites, a wheel build and an installed-CLI smoke on Linux/py3.12, plus a fast-suite pass on py3.11. It does not prove Windows or macOS behavior, mutation strength, or that merges are gated.

## Evidence log
Files read (all in the workspace): `SELF_AUDIT_ASSERTIVA/agent.md` (outside it, allowed by the task), `STATUS.md` (first 150 lines), `.github/workflows/ci.yml`, `tests/test_history.py` (lines 135-149 via grep), `ROADMAP.md` (grep for azure/gitlab/jenkins), `scripts/validate_repo.py` (grep for evals only). The `ls` listings were of the workspace root, `.github/workflows`, `tests`, `evals` (absent) and `scripts`.

Commands (venv python, `PYTHONDONTWRITEBYTECODE=1`, `ASSERTIVA_HOME` outside the project):
1. `ls`, `cat STATUS.md | head -150` and listings.
2. `python -m assertiva.cli audit .`, first run. It failed with a READ-ONLY VIOLATION caused by `__pycache__`.
3. Removed the `__pycache__` dirs (workspace copy only), then re-ran `audit .`. Result: FINDINGS.
4. `audit . --output json` plus a Python parse of the findings.
5. `python -m pytest -q -p no:cacheprovider tests/test_repo_contract.py tests/test_cross_stack_contract.py tests/test_history.py`: 60 passed, 1 failed (missing `evals/README.md`).
6. `grep`/`ls` checks of `evals`, `scripts`, ROADMAP and `test_history.py`.
