# v1.0 release readiness

**Candidate:** `integration/v1.0-foundation`, PR [#9](https://github.com/Soturine/Assertiva/pull/9). **Verdict and
remote CI:** see the end of this page. **READY is not an authorization to publish.** Tag, GitHub Release and any
announcement wait for the owner's decision.

## Gates

| # | Gate | Result | Evidence |
|---|---|---|---|
| 1 | `validate_repo.py` + core suite on the integration SHA | PASS | Windows 1146 passed / 6 skipped; Linux 3.12 1146 / 5; Linux 3.11 1146 / 6 |
| 2 | Integration and artifact suites with `ASSERTIVA_REQUIRE_*` | PASS locally (Windows, JS + Django + mutation required: 196 passed, 5 skipped); Linux 3.12: 190 passed, 1 environmental failure (StrykerJS fixtures not installed in the container; the requirement flag made it fail instead of skip) | remote run below |
| 3 | Fail-before/pass-after for the P1/P2 fixes | PASS | 25/27 fail on base `bb36fe1`, 27/27 pass on HEAD ([V1_REMEDIATION](V1_REMEDIATION.md)) |
| 4 | Windows and Linux, PermissionError, links, packages, installed artifacts | PASS | open-handle cleanup (Windows), unwritable directory and venv symlink (Linux), wheel runs on both |
| 5 | A real mutation cycle with scope and counts | PASS | Cosmic Ray on VozNativa: 72 mutants, selection of 13 tests, whole suite NOT_RUN |
| 6 | No overclaiming of PASS | PASS | identity required for wheel PASS; imported results not counted as executed; empty selections refused |
| 7 | Contracts and docs, with migration | PASS | [MIGRATION_V1](../MIGRATION_V1.md), schema updated for `gate` |
| 8 | Skill does not change user configuration | PASS by inspection (the Skill is files; nothing installs it automatically) | Skill bundle: DEFERRED, see below |
| 9 | Agent-led evals executed, with holdout and recorded cost | PASS with caveats | 8 cases: 6 PASS, 2 REVIEW, 0 FAIL; same model family ([V1_AGENT_EVALS](V1_AGENT_EVALS.md)) |
| 10 | Full remote CI | PASS on `e6fdc74` | [dispatch run 43491656694](https://github.com/Soturine/Assertiva/actions/runs/43491656694): validate (integration + artifact, `ASSERTIVA_REQUIRE_*`), Windows full, browser, java, Gradle/Android, services, Python 3.11 and runtime self-qualification all succeeded. [PR run 43491658829](https://github.com/Soturine/Assertiva/actions/runs/43491658829): fast jobs succeeded, heavy jobs skipped by design |
| 11 | No secrets, private files or personal paths | PASS | scans before each commit; eval paths redacted |
| 12 | Git state and `main` untouched | PASS | `main` = `2618d95`; nothing force-pushed; no tag |

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

The repository has no rulesets, and branch protection is off. Proposal for a solo maintainer: a ruleset on `main` that
requires a pull request (zero approvals), the `validate`, `Python 3.11 compatibility` and `Windows` checks, linear
history off (merge commits keep contributor SHAs) and no force pushes. Applying it is the owner's decision.

## Verdict

**READY (release candidate), pending the owner's decision.** Every technical gate above passed, and no blocker is
open. The residual risks are recorded and none of them is critical. The commit after `e6fdc74` changes only
documentation (this page and `docs/README.md`), so the full qualification of `e6fdc74` covers the code and tests of
the final SHA; the pull-request run checks the final SHA again.

Publication (`1.0.0` version bump, annotated tag, GitHub Release with wheel, sdist and SHA-256) is **not** done and is
**not** authorized by this verdict. It needs the owner's explicit approval, then a fresh check of base, SHA and checks.
Before tagging, the two REVIEW eval verdicts should also be decided by a human.
