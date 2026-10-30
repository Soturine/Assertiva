# Release readiness — 0.10.0.dev0

**Verdict: not releasable yet; `READY_WITH_EXTERNAL_BLOCKER` at best once CI passes.** No tag, no GitHub Release, no
merge to `main` without the owner's decision. The CI result for the final commit is recorded in the pull request.

## Local gates (2026-10-30)

| Gate | Environment | Result |
| --- | --- | --- |
| Fast/core suite | Windows 11, Python 3.12.10 | PASS: 1004 passed, 4 skipped (POSIX-only and privileged-symlink tests) |
| Integration + artifact, Django, Cosmic Ray and JS required | Windows 11, Python 3.12.10, Node 24.19, pinned venv (`constraints.txt`) | PASS: 166 passed, 5 skipped (Maven/PIT/POSIX by design) |
| Fast/core suite | Linux (Docker `python:3.12-bookworm`), Python 3.12.15 | PASS: 1007 passed, 0 skipped (symlink tests included) |
| Integration + artifact, Django and Cosmic Ray required | same container, no Node | 158 passed, 12 skipped, 1 failed: the StrykerJS test fails by design when `ASSERTIVA_REQUIRE_MUTATION=1` and its npm fixture is not installed (no Node in the image); it passed on Windows and CI installs the fixture |
| Eval harness security (link refusal) | Linux | PASS: 2 passed |
| Wheel and sdist | Windows | PASS: `assertiva-0.10.0.dev0` both built; new modules present in both |
| Installed CLI outside the repository | fresh venv with only the wheel | PASS: `--version` 0.10.0.dev0; `audit --execute --dependencies --timeout-s` exit 0, fixture tree unchanged; `explain` works; the run is BLOCKED by the AX-E06 preflight (no pytest in that venv), as intended |
| Repository validation, gap matrix check, ruff F-rules | Windows | PASS |
| Frozen benchmarks v1+v2 | static | unchanged: precision 1.0, recall 0.841 (same as 0.9.0) |
| Browser (Playwright), JVM (Maven/Gradle/PIT) | — | NOT_RUN locally (no browsers installed, no JDK); CI jobs `browser` and `java` cover them |
| Python 3.11 | — | NOT_RUN locally; CI matrix covers it |
| Semantic eval with agents | — | NOT_RUN: needs the owner's budget approval |

## External gates

| Gate | State |
| --- | --- |
| GitHub Actions on the final commit | pending until the final push (intermediate pushes carried `[skip ci]` and triggered no run) |
| Owner review of contract changes (CHANGELOG "contract change" items) | pending |
| Independent holdout / second labeler | not available |

## Open items that do not block a 0.10.0 tag (backlog with reasons in the gap matrix)

TCC-A02, TCC-A06, TCC-A12 (NEW); TCC-A09, TCC-A13 (PARTIAL); TCC-A18, TCC-A15 (BLOCKED); TCC-A20, TCC-A21, TCC-A24
(ACCEPTED_LIMITATION).
