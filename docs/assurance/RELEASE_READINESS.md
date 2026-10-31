# Release readiness — 0.10.0.dev0

**State:** v0.9.0 is the published release. 0.10.0.dev0 is in development on `feature/assertiva-0.10.0-hardening`
(draft PR #2). No tag, GitHub Release, PyPI upload or merge to `main` happens without the owner's decision.

## Evidence by kind

| Kind | What it covers |
| --- | --- |
| **Implemented** | every FIXED row of the [gap matrix](POST_DOGFOOD_GAP_MATRIX.md) (40 of 53), each with its commit |
| **Executed on fixtures** | every FIXED row has a test that failed before its commit and passes after ([evidence/fail-before-0.9.0.txt](evidence/fail-before-0.9.0.txt) for the first 34; the matrix names the reproducer of each later one); real tools where named: Cosmic Ray 8.7.0, Node 24.19, Django, pytest in a separate venv |
| **Validated on a real project** | Assertiva itself only: static self-audit (same findings as 0.9.0), engine-run mutation of `assertiva/failures.py` ([self-dogfood](ASSERTIVA_SELF_DOGFOOD.md)). The dogfooded projects (TCC, Derivanta Engine, DrawLab) were **not** re-audited with 0.10.0 (not authorized for this work) |
| **Proven by CI** | the table below, per SHA; a skipped job is not a pass |
| **Documented, not executed** | semantic Skill evaluation of the 0.10.0 Skill changes (needs the owner's budget approval); browser and JVM suites on this machine (no browsers or JDK here; CI runs them); Python 3.11 locally (CI runs it) |
| **Planned or blocked** | TCC-A02, A06, A12 (open); A18 (needs an emulator), A15 (agent eval budget); A09, A13 partial; A20, A21, A24 accepted limitations |

## Local gates

| Gate | Environment | SHA | Result |
| --- | --- | --- | --- |
| Fast/core suite | Windows 11, Python 3.12.10 | `a14b3ff` | 1035 passed, 5 skipped (POSIX-only and symlink-privilege tests) |
| Integration + artifact; Django, Cosmic Ray and JS required | Windows, pinned venv (`constraints.txt`) | `b98386d` | 172 passed, 5 skipped (Maven/PIT/POSIX by design) |
| Fast/core suite | Linux (Docker `python:3.12-bookworm`), Python 3.12.15 | `b98386d` | 1038 passed, 0 skipped (symlink tests included) |
| Integration + artifact; Django required | same container, no Node | `b98386d` | 164 passed, 13 skipped (Node/Java absent in the image) |
| Registry concurrency (6 processes x 15 rounds) | Windows and Linux | `4422776`, `b98386d` | 0 lost, valid JSON (at `26461ce`: 180/180 lost, invalid JSON) |
| Identity check cost | Windows / Linux | `ea94d83` | 90 / 11 µs per module (5000 modules: 0.45 s / 56 ms) |
| Wheel and sdist from a clean `git archive` export | Windows | `10a900b` | both built; wheel installed in a fresh venv outside the tree |
| Installed CLI on a real fixture, `--python` with pytest | same | `10a900b` | PASS, 4 PASSED, ENGINE_EXECUTED, code identity SOURCE_TREE; `explain` shows the execution; fixture unchanged |
| Installed CLI, interpreter without pytest | same | `10a900b` | BLOCKED with the reason (AX-E06 preflight), as intended |
| Engine-run mutation of `assertiva/failures.py` (named tests) | Windows, Cosmic Ray 8.7.0 | `b98386d` | 209 mutants: 121 killed, 88 survived (55 equivalent) |
| Frozen benchmarks v1+v2 | static | `a14b3ff` vs `cf5cb7d` | identical: precision 1.0, recall 0.841 (37/0/7). No gain is claimed |
| Static audit cost on this repository | Windows, single samples | `a14b3ff` vs `cf5cb7d` | 13.7 s vs 15.0 s, identical findings (within run-to-run noise) |
| ruff F-rules, repository validation, gap matrix check, schema check | Windows | `a14b3ff` | PASS |

## CI (GitHub Actions, workflow `CI`)

| Run | Event | SHA | Result |
| --- | --- | --- | --- |
| [41163321031](https://github.com/Soturine/Assertiva/actions/runs/41163321031) | push | `26461ce` | success: 7 jobs ran with steps; Runtime self-qualification skipped (runs on dispatch only) |
| final push of this hardening round | push | recorded in PR #2 | see PR #2 |

## What blocks a release, and what is only the owner's decision

- **Blocks:** nothing technical in the local gates above. CI on the final SHA, including the dispatch-only runtime self-qualification, must pass before a tag.
- **Owner decisions:** the contract changes listed in the CHANGELOG; PR #1's disposition (superseded by #2); approval of a budget for semantic agent evals (or shipping with them recorded NOT_RUN); merging #2; tagging `v0.10.0` (the version string is then changed from `0.10.0.dev0`).
