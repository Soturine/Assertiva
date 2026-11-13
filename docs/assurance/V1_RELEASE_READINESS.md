# v1.0 release readiness

**Candidate:** `integration/v1.0-foundation`, PR [#9](https://github.com/Soturine/Assertiva/pull/9) (requalified after the v1.0 addendum). **Verdict and
remote CI:** see the end of this page. **READY is not an authorization to publish.** Tag, GitHub Release and any
announcement wait for the owner's decision.

## Gates (requalified after the v1.0 addendum, code SHA `874eeab`)

| # | Gate | Result | Evidence |
|---|---|---|---|
| 1 | `validate_repo.py`, ruff, core suite | PASS | Windows 1149 passed / 6 skipped; Linux 3.12 1149 / 5; Linux 3.11 1149 / 6 |
| 2 | Integration and artifact suites with `ASSERTIVA_REQUIRE_*` | PASS on Windows (JS + Django + mutation required: 199 passed, 6 skipped: the symlink test that this Windows machine cannot run (it passes on Linux), 4 Gradle and 1 services test that need downloads; CI runs them). Linux 3.12: 192 passed, 1 environmental failure, `test_stryker_proves_…`: the StrykerJS fixtures are not installed in the container, and the requirement flag made it fail instead of skip. CI runs it | remote run below |
| 3 | Fail-before/pass-after | PASS | first round: 25/27 fail on `bb36fe1`; addendum: 6/7 fail on `0f3f5cc` (the control passes on both) ([V1_REMEDIATION](V1_REMEDIATION.md)) |
| 4 | Windows and Linux, PermissionError, links, packages, installed artifacts | PASS | open-handle cleanup (Windows), unwritable directory and venv symlink (Linux), wheel runs on both |
| 5 | A real mutation cycle with scope and counts | PASS | Cosmic Ray on VozNativa (72 mutants, 13 selected tests) and in the suites |
| 6 | No overclaiming of PASS | PASS | wheel PASS needs INSTALLED_ARTIFACT; imported results are counted and reported as imported (metrics and findings, CP-B); an opaque CI step cannot lower a gap (CP-A) |
| 7 | Contracts and docs, with migration | PASS | [MIGRATION_V1](../MIGRATION_V1.md); schema updated for `gate` |
| 8 | Packaging | PASS on the branch build | wheel `e3412c92…f715` and sdist `28027853…68f9` (version **0.10.1**: no bump yet) built from `e44573f`, the same code as `874eeab`; each installed into a clean venv and imported from site-packages, with the new modules present; the sdist has 180 files |
| 9 | Agent-led evals | **2 REVIEW open** | 6 PASS, 2 REVIEW, 0 FAIL by the judge; operator reading: FISCAL REVIEW, PROFILE does not meet its pass condition ([V1_AGENT_EVALS](V1_AGENT_EVALS.md)) |
| 10 | Full remote CI of the final code SHA | PASS | [dispatch 43499037205](https://github.com/Soturine/Assertiva/actions/runs/43499037205) on `874eeab`: validate, Windows, Python 3.11, browser, java, Gradle/Android, services and runtime self-qualification succeeded; [PR run 43499048379](https://github.com/Soturine/Assertiva/actions/runs/43499048379) fast jobs succeeded |
| 11 | No secrets, private files or personal paths | PASS | scans before each commit; eval paths redacted |
| 12 | Git state and `main` untouched | PASS | `main` = `2618d95`; PR #9 is a draft; nothing force-pushed; no tag, Release or ruleset |

## Residual risks (by severity)

1. **Agent-led evaluation is not independent** (same model family; 8 cases, single runs). The two REVIEWs need a human.
2. **Wheel tests can fail for reasons other than a broken wheel**: tests tied to the source tree (VozNativa) report
   FAIL, and the agent has to explain them. Automatic classification is DEFERRED (P3).
3. **Static `--dependencies` misses undeclared imports** (found by the AXF-08 agent). Only `--execute` artifact
   qualification checks that closure. DEFERRED (P2).
4. **AXR-01/07/10..14** (Lua classification, lineage tiers, Node contract runners, Windows path friction) are DEFERRED.
5. **Bugbear lint findings (23)** are not reviewed; the gate covers correctness rules only.

## Decisions (ADOPT / DEFER / REJECT)

- ADOPT: an opt-in `--fail-on` gate; a ruff correctness gate; event-gated CI; a shared identity observer; `imported_*`.
- DEFER: a new ecosystem executor (.NET first, then Go, in 1.1: no toolchain here to qualify a real adapter); PIT via
  Gradle; Inspect AI / Promptfoo / DeepEval (no measured gain for this round's threat); a separately versioned Skill
  bundle with an installer (the Skill is published as repository files; a bundle adds no evidence for 1.0).
- REJECT: a parser for shell/Lua to resolve the two Randomizer examples; ecosystem-specific detectors for fiscal,
  RBAC or Grafana shapes without labeled cases.

## Proposed protection for `main` (not applied)

There are no rulesets, and branch protection is off. The check names below were read from the check runs of a real
commit, all from the `github-actions` app: `validate`, `Windows`, `Python 3.11 compatibility`. These are the three
jobs that run on every pull request, so a version-bump PR satisfies them. The heavy jobs report `skipped` on pull
requests and must not be required. Proposal for a solo maintainer: a ruleset on `main` that requires a pull request
with **zero** approvals, those three checks, and no force push or deletion; merge commits stay allowed, so
contributors' SHAs are kept. Bypass goes to the repository-admin role, for emergencies only. Applying it needs the
owner's authorization.

## Verdict

**CONDITIONAL.** The code at `874eeab` passed every technical gate, including the full remote qualification of that
exact SHA, and no evidence-integrity blocker is open. It is not READY for publication because:

1. **The version is still 0.10.1.** The 1.0.0 artifact has not been built or qualified. The release step (after
   approval) bumps the version, merges PR #9, qualifies the merge commit on `main`, tags `v1.0.0` (annotated), builds
   wheel and sdist from the tagged SHA, writes `SHA256SUMS.txt`, smoke-installs in isolation and publishes the GitHub
   Release (not PyPI). Each step needs its own SHA and digest evidence.
2. **Two agent-eval REVIEWs** need the owner's decision (accept as known risk, or fund a re-evaluation after a Skill
   change).

The commit after `874eeab` changes only this page; its pull-request run is the record for it.
