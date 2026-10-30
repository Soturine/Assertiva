# Competitive position and benchmarks — 0.10.0 development line

Two parts that must not be confused: **executed** measurements (run on this machine, on named fixtures and revisions)
and **documentary** positioning (what other tools are designed to do, from their documentation). Documentary rows are
never evidence of how Assertiva compares in practice.

## 1. Executed: 0.9.0 against the candidate, same inputs

Conditions: Windows 11 Pro 10.0.26200, Python 3.12.10, Node 24.19.0, 2026-10-30. 0.9.0 is a Git worktree at
`cf5cb7d` run from a **clean virtual environment** (the first attempt used the main checkout's interpreter, whose
editable install served modules missing from 0.9.0 out of the candidate tree: mixed code, discarded, recorded as
ENG-02). The candidate is this branch.

### Frozen confirmation sets (never used to design or tune a rule)

`python benchmarks/effectiveness.py tests/fixtures/confirmation/v1/* tests/fixtures/confirmation/v2/*`

| Engine | Fixtures | Precision | Recall | TP / FP / FN |
| --- | --- | --- | --- | --- |
| 0.9.0 `cf5cb7d` | v1 + v2 (6 fixtures) | 1.0 | 0.841 | 37 / 0 / 7 |
| candidate | same | 1.0 | 0.841 | 37 / 0 / 7 |

No regression and **no measured gain**: the patterns the new rules target (expected-error idiom, call==call,
literal-loop conditions, vacuous subsets, self-mocking, imported helpers, no-raise pairs, Compose state checks) do
not occur in v1/v2. Their evidence is the development fixtures below, which were written with the rules and are not
independent. A new frozen set written by someone other than the rule author is the next step (§4).

### Development fixtures: fail on 0.9.0, pass on the candidate

The new and changed test files, run against pure 0.9.0
([evidence/fail-before-0.9.0.txt](evidence/fail-before-0.9.0.txt)): every file fails or cannot import on 0.9.0;
the 0.9.0 passes are the negative controls that must already hold (a product's own permission error stays PRODUCT,
real subsets are not flagged, optional imports pass). On the candidate all pass.

### Same static audit, same targets ([evidence/static-audit-0.9.0-vs-candidate.json](evidence/static-audit-0.9.0-vs-candidate.json), [evidence/self-audit-cost-0.9.0-vs-candidate.json](evidence/self-audit-cost-0.9.0-vs-candidate.json))

| Target | 0.9.0 | candidate | Findings |
| --- | --- | --- | --- |
| this repository (static audit) | 16.8 s | 19.7 s | identical codes |
| confirmation v2 py-parking / js-tickets / kt-library | 0.84 / 0.60 / 0.84 s | 0.86 / 0.62 / 0.77 s | identical codes and candidate counts |
| PRIVATE_FILE_BOUNDARY fixture | 1.06 s | 1.14 s | identical |

The candidate first measured 36–50 s on this repository: imported-helper resolution re-parsed and resolved project
modules for every test file. Fixed (helpers followed only into test-support modules, lexical checks first, memoized);
the fix also removed a precision risk (a product function that asserts an invariant was counted as the test's oracle).

## 2. Documentary positioning and decisions

Sources: the references named in the work briefs (2026-10-30). They were **not re-fetched in this session**; versions
below are those recorded in this repository's earlier research (`research/2026-10-19-competitive/`) or stated as
unknown.

| Project / practice | What it does | Decision for 0.10.0 | Why |
| --- | --- | --- | --- |
| Cosmic Ray (already integrated, 8.7.0) | Python mutation with a test command per mutant | **ADAPT** | targeted runs added (`--mutate-tests`); the mutator is not reimplemented |
| mutmut | incremental Python mutation, POSIX only | **REJECT (unchanged)** | evaluated for 0.9.0 (3.8.0): no evidence Cosmic Ray does not give; Windows needs WSL |
| StrykerJS incremental | reuses results by test/mutant digest | **DEFER** | principle noted (strong invalidation by config/env); selection here was implemented for Cosmic Ray only |
| PIT | JVM mutation | **unchanged** | no JDK on this machine; CI java job covers it |
| Hypothesis / Schemathesis | property and schema-based tests | **DEFER** | no gap in this round needed them; opt-in fixtures only when a schema and local service exist |
| CTRF | portable test results (pre-1.0 spec) | **unchanged** | import/export from 0.9.0 kept; no format change without a migration |
| Pact / can-i-deploy | contract matrix by version | **DEFER** | Broker queries remain out of scope; no deployed-verification claim |
| OSV-Scanner (offline mode) | vulnerabilities from lockfiles | **ADOPT as the named tool** | `--dependencies` reports vulnerabilities UNKNOWN and names OSV-Scanner; no advisory database is bundled |
| Renovate / Dependabot | update proposals | **REJECT (duplicate)** | Assertiva diagnoses declared/locked/installed drift and usage; it never proposes or applies updates |
| Backstage catalog | service metadata catalog | **ADAPT (idea only)** | the portfolio registry borrows the metadata-first idea; nothing installed |
| OpenSSF Scorecard, NIST SSDF | repository practice checks; secure development practices | **BENCHMARK_ONLY** | inputs for a release checklist; no conformance claim |
| OWASP LLM prompt injection / AI agent security cheat sheets | boundaries outside the model, least privilege | **ADOPT** | case text framed as data, directive lint, link-free copies, canary, tool-call guard, deterministic safety gate (SEC-EVAL-01/02, AG-13) |
| OpenTelemetry CI/CD semconv, SARIF | observability, code-scanning export | **DEFER** | release candidate / account-dependent; no backend required by an audit |
| GitHub Actions `[skip ci]` | skip push/PR runs | **USED** | intermediate pushes of this branch carried it; `gh run list` showed no run for them |

## 3. What is distinctive, and what is not

Assertiva does not compete with mutation tools, linters or CI dashboards; it orchestrates them and ties their output
to a claim. The chain this round strengthened: *which code ran* (source identity per module), *by which run* (engine,
imported, CI, operator-manual, device-blocked), *with which oracle* (calibrated rules with negative controls), *what it
would detect* (targeted mutation, kills by test), *at what cost* (limits and duration side by side), *what may be said*
(`assertiva explain`). Nothing here measures whether that chain is more useful than another tool's output for a real
team; that needs §4.

## 4. Not run (and what would close it)

- An independent holdout: a new frozen set written and labeled by someone other than the rule author, with
  agreement recorded, before the rules are scored on it.
- Executed comparison with other tools on the same fixtures (the protocol in `benchmarks/README.md`).
- Semantic evaluation of the Skill changes with agents: needs the owner's budget approval (standing rule).
