# Agent vs engine — DrawLab M10 baseline audit (A0)

The audited project is private; this page lists categories and counts, never its paths, tests or data. Engine
0.9.0 (`cf5cb7d`); the agent followed `SKILL.md` and `references/` of the same commit.

## Engine findings and the agent's dispositions (baseline revision, clean tree)

| Engine finding | Items | Agent read | Disposition | Why |
| --- | --- | --- | --- | --- |
| NATIVE_TESTS_FAILING (run 1) | 435 | all, by fingerprint | CONTEXTUAL (environment) | 434 share one PermissionError in pytest's own `tmp_path` factory (machine ACL); 1 is a real pre-existing failure |
| (run 3) source-tree run | — | — | BLOCKED (engine) | "timed out after 900 s": the suite needs ~1 h; correctly not counted as pass or fail |
| ARTIFACT_QUALIFICATION_FAILED | 10 failing tests | 10 | CONTEXTUAL | all read the Git checkout (worktrees, remotes, tracked files) and cannot pass from an installed wheel |
| FALSE_GREEN_CANDIDATE (SWALLOWED_EXCEPTION) | 2 | 2 | FALSE_POSITIVE | `try: call(); assert False; except X: pass` — AssertionError is not caught |
| FALSE_GREEN_CANDIDATE (CONDITIONAL_ASSERTION) | 2 | 2 | FALSE_POSITIVE | conditions deterministically true several times |
| FALSE_GREEN_CANDIDATE (TAUTOLOGY) | 4 | 4 | PARTIAL (3 FP, 1 contextual) | determinism tests `f(x) == f(x)`; one constant-hash line inside a strong test |
| FALSE_GREEN_CANDIDATE (SELF_REFERENTIAL_ORACLE) | 1 | 1 | CONTEXTUAL | determinism + a formula checked against arrays the code produced |
| WEAK_ORACLE_SIGNAL (Python) | 3 | 3 | PARTIAL | two "must not raise" contracts; one broad type with a specific message |
| BROAD_ERROR_EXPECTATION_SIGNAL | 1 | 1 | CONTEXTUAL | message pinned |
| TEST_FIDELITY_MISMATCH (JS) | 6 | 6 (by file) | CONTEXTUAL | component tests named "integration"; a real-browser E2E crosses the boundary |
| ERROR_STATUS_ONLY_SIGNAL | 15 | 0 | UNRESOLVED | not read |
| WEAK_ORACLE_SIGNAL (JS) | 10 | 0 | UNRESOLVED | not read |

Effectiveness candidates read: 20 of 45 items; none of the 11 Python false-green / weak-oracle items was a false green.

## Agent-only findings (the engine raised none of these)

| Finding | Basis | Severity |
| --- | --- | --- |
| The machine's temp root denies access; every run without `--basetemp` errors | OBSERVED (reproduced outside the engine) | high (environment) |
| A test that a public verifier detects divergent history fails on the default branch | OBSERVED (operator's full run) | medium |
| A UI-translation completeness test truncates its dictionary at the first `};` inside a value | OBSERVED | low |
| (new code, M10) a campaign-level "max of search" null normalised null worlds by spreads containing themselves — biased towards the real campaign | OBSERVED (calibration test: exchangeable campaigns averaged far above 0.5) | high — found by the agent on its own analysis code, after a real study looked "too good" |

## Where the engine and the agent disagreed

* Origin of the 434 errors: engine PRODUCT, agent INFRASTRUCTURE (AG-01/AG-02). Resolved by reproduction, not by vote.
* Whether a full-suite outcome existed: engine run 3 BLOCKED (correct); the agent's own run had one (different
  instrument, kept apart, labelled OBSERVED by the agent).

## Cost (measurable parts)

Static audit 16.6 s; executed runs 11 min (run 1, fast because tests errored), 12 min (run 2), 29 min (run 3,
timeout + artifact); assessment attach seconds. Tokens of the agent are not measured here.
