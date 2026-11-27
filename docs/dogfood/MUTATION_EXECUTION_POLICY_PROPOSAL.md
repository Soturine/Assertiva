# Proposal: adaptive mutation execution without a fixed mutant ceiling

Status: **proposal, not implemented.** Supersedes the narrow "region filter under the 300 budget" suggestion of AXF-FTD-02 ([intake](ftd-v2.6.0/README.md), AXF-FTD-02) and gives DG-0101-12 / IDEA-02 a design. Applies to every orchestrated mutation adapter (Cosmic Ray, StrykerJS, PIT today; mutmut, Stryker.NET, Stryker4s, cargo-mutants, Infection and others later) and to imported reports.

## Problem

`MAX_MUTANTS = 300` in `assertiva/adapters/cosmic_ray.py` refuses any target whose planned population exceeds 300, whatever the user authorized, the machine can do or the time available. Real projects plan thousands to tens of thousands of mutants (FTD `scripts/reading.py`: 2058; Derivanta M2: 594; Assertiva's own `ci.py`: 371). The cap protects against runaway runs, but it does so by refusing measurement, and a filter-only fix would keep an arbitrary number at the centre of the design. Meanwhile the other adapters pin their tools to small fixed settings (StrykerJS `concurrency: 2`, `incremental: false`; PIT `threads: 2`, `withHistory: false`).

## Principles

1. **No fixed numeric ceiling.** Size is governed by an explicit, recorded policy: an estimate, the user's authorization and optional budgets. Running everything is allowed when authorized.
2. **Native first.** Use each tool's own selection, parallelism, resumption, incremental and timeout mechanisms; build in Assertiva only what no tool provides, and only once, in the shared layer.
3. **Accounting cannot improve a score.** Every reduction of work (scope, sampling, batches, budgets, reuse) is a named population, never a silent change of denominator.
4. **Runtime-verified.** A result counts for a state only when the sources, tests, runner and environment it ran with are tied to that state.
5. **Agent-first.** The engine estimates, plans, runs and accounts; the agent (with the user) decides scope, risk ordering and authorization, and interprets survivors.

## 1. Population accounting (the core contract)

Every mutation run — orchestrated or imported — reports these populations, each with its own count and reason list:

| Population | Meaning |
| --- | --- |
| `universe` | mutants the tool plans for the named targets with the configured operators (the module-level denominator) |
| `excluded` | removed from the universe by a declared rule (scope selection, `pragma: no mutate`, static/ignored mutants), each with its rule |
| `scope` | `universe − excluded`: what the run claims to measure |
| `sampled` | when sampling: the drawn subset of the scope, with seed and method; otherwise equal to `scope` |
| `reused` | results carried from an earlier compatible run (section 6), never counted as executed now |
| `executed` | evaluated in this run |
| `not_run` | in the sample but not evaluated (budget, stop, crash, interruption) — reported, never dropped |
| outcomes | per executed or reused mutant: `KILLED`, `SURVIVED`, `TIMEOUT`, `NO_COVERAGE`, `ERROR` (incompetent / non-viable / compile), `EQUIVALENT` (only with recorded evidence), `IGNORED` |

**Run mode**, derived, never chosen by the reporter:

- `COMPLETE` — scope = universe, nothing sampled, `not_run = 0`.
- `TARGETED` — scope ⊂ universe by a declared selection; `not_run = 0`.
- `SAMPLED` — sampled ⊂ scope; statistical estimate.
- `PARTIAL` — any of the above with `not_run > 0`.

**Scores** are always shown with their populations, never as one number:

- detection over evaluated: `detected / (executed + reused − ERROR − EQUIVALENT − IGNORED)`;
- for `PARTIAL`, the bounds over the scope: lower = `detected / scope`, upper = `(detected + not_run) / scope`;
- for `SAMPLED`, an estimate with a confidence interval (Wilson) over the sample, labelled as an estimate of the scope;
- for `TARGETED`, the scope and its rule next to the score; a targeted score is never shown as the module's or project's.

**Comparisons and gates** (baseline vs candidate, `--fail-on`, improve qualification) only between runs with the same mode, the same scope rule and the same plan digest (section 7). Anything else is reported as `NOT_COMPARABLE` with the reason. This rule is what keeps filters, sampling, batches and time limits from producing better-looking numbers.

## 2. Execution policy instead of a ceiling

```text
assertiva audit … --execute --mutate TARGET [--mutate TARGET …]
    [--mutation-scope file|class|function|lines|changed-since=REV]   # see section 3
    [--mutation-sample N|P% --mutation-seed S]                      # optional
    [--mutation-budget time=2h,mutants=5000,workers=8,memory=2GiB]  # all optional
    [--mutation-plan-only]                                          # estimate and stop
    [--mutation-authorize full|estimate-under=DURATION]             # see below
    [--mutation-session ID] [--mutation-shard K/N]
```

- **Estimate first.** The engine plans (native `init`/dry run), counts the universe and scope, runs the baseline, and estimates `cost ≈ Σ per-mutant test time / workers + overhead`, using per-test coverage when the tool provides it (StrykerJS `coverageAnalysis: perTest`, PIT's coverage, mutmut's test mapping) and the baseline otherwise. The estimate and its basis go into the report.
- **Authorization replaces the cap.** With no budget and no authorization, a run whose estimate exceeds a user-configurable threshold (consent file or CLI, default e.g. 30 minutes) stops after planning with `MUTATION_PLAN_REQUIRES_AUTHORIZATION`, showing the estimate and the options (run all, scope, sample, budget, shard). `--mutation-authorize full` runs the whole scope with no numeric limit. Authorization is recorded in the run.
- **Budgets are optional stop conditions, not denominators.** Time, mutant count, workers and memory stop or shape a run; what they leave undone is `not_run`. Memory is enforced where the platform allows (per-worker limits on POSIX, job objects on Windows); otherwise recorded as "not enforced".
- **Timeouts** follow the tool's native relative-plus-absolute model (StrykerJS `timeoutFactor`/`timeoutMS`, PIT `timeoutFactor`/`timeoutConst`, Cosmic Ray's per-mutant timeout from the baseline); the effective values are recorded.

## 3. Selection

| Selector | Native mechanism to reuse | Shared fallback |
| --- | --- | --- |
| file | every tool | — |
| class / function | PIT `targetClasses`/`excludedMethods`; StrykerJS `mutate` with line ranges from the symbol span | resolve the symbol with the language's parser to a line span, then lines |
| lines | Cosmic Ray `cr-filter-lines`; StrykerJS `--mutate file:5-7`; Stryker.NET mutate ranges | — |
| git changes | Cosmic Ray `cr-filter-git`; cargo-mutants `--in-diff`; Stryker.NET `--since`; Infection `--git-diff-lines --git-diff-base`; StrykerJS with ranges computed from the diff | diff hunks → lines |
| risk | none (a judgement) | ordering and sampling weights only |

Rules: the selector is recorded and becomes the scope rule; excluded mutants stay in `universe` and `excluded`; **risk never removes mutants from a declared scope** — it orders execution (so a budgeted run spends time where the agent judged risk highest, and the report says the order) or weights a declared sample. Changed-lines runs are `TARGETED` and say so, as cargo-mutants' own documentation warns that diff runs are not a substitute for full runs.

## 4. Batches, parallelism and distribution

- **Parallelism, native:** StrykerJS `concurrency`, PIT `threads`, cargo-mutants `--jobs`, Infection `--threads`, Cosmic Ray's `http` distributor with one worker clone per process (`cr-http-workers`). The current fixed values (2) become defaults derived from CPU count and the memory budget, recorded in the run.
- **Batches and shards:** where the tool shards natively (cargo-mutants `--shard k/n`), use it; otherwise the shared layer orders the scope by a stable mutant id and assigns deterministic shards. A merged result is accepted only when the union of shards equals the planned scope with no duplicate and every shard ran the same plan digest; a missing shard leaves its mutants `not_run`.
- **Workspace isolation:** each worker gets its own disposable copy (tools mutate files in place), as orchestrated runs already do.

## 5. Persistence and resumption

- A **mutation session** lives under `ASSERTIVA_HOME/mutation-sessions/<state digest>/<plan digest>/` (never in the project): the tool's native state (Cosmic Ray's session database, whose `exec` already continues the remaining work; StrykerJS's incremental file, which also stores partial results of an interrupted run; PIT's history file; cargo-mutants' output directory) plus Assertiva's plan and population ledger.
- `--mutation-session ID` resumes only if the state digest, plan digest, runner fingerprint and tool version still match; otherwise the session is refused as stale and a new one starts. Resumed results are `executed` in that session, with the session's start and resume times.

## 6. Incremental reuse, safely

Native incremental modes (StrykerJS `--incremental`, PIT history, Stryker.NET `--with-baseline`) are allowed only through the shared ledger, because Assertiva currently treats unmarked carry-over as a limitation. A result is reusable for a mutant only when all of these are unchanged and recorded: the mutant's stable id and the digest of its enclosing function or file region, the digests of the tests that covered it (or of all tests when coverage is unknown — StrykerJS documents that incremental mode does not see test changes by itself), the runner command and environment fingerprint, and the tool version and operator set. Reused results are counted as `reused` with their source session; a reused `SURVIVED` is shown as such; a gate may require `reused = 0` for release qualification.

## 7. Plan digest and capability discovery

- **Plan digest:** sha256 over targets, operators, scope rule, sample seed and method, runner command, environment fingerprint and tool version. It identifies what was measured and is the unit of comparability, resumption and reuse.
- **Capability discovery:** each adapter probes the installed tool (version and `--help`, Cosmic Ray `operators` and `distributors`, plugin lists) and records a capability set (`scope.lines`, `scope.diff`, `parallel`, `distributed`, `resume`, `incremental`, `per_test_coverage`, `killers_complete`). The planner uses native capabilities first and the shared fallback otherwise, and the report lists which was used. Missing capabilities are recorded, never emulated silently.

## 8. Runner, environment and import context

The mutation baseline and every mutant run use the **same runner, start directory, working directory and import path** as the audit's execution run (the fix for AXF-FTD-01 is the first instance). The baseline must report the same test count for the selected tests as that run; a mismatch stops at `stage: selection` before any mutant runs.

## Anti-gaming rules (testable)

1. A filter, sample, shard, budget or reuse never changes `universe`; scope changes are recorded rules.
2. `not_run`, `ERROR`, `TIMEOUT` and `EXCLUDED` are always visible with counts; `TIMEOUT` keeps today's meaning (detected), and the share of timeouts is shown beside the score.
3. Equivalence needs recorded evidence per mutant; it is never inferred from survival.
4. A `PARTIAL` run never shows a single score; it shows bounds.
5. A `SAMPLED` estimate is never compared with a `COMPLETE` value as if equal.
6. Comparisons require equal mode, scope rule and plan digest.
7. Risk ordering cannot shrink a declared scope.
8. Reused results are never counted as executed in the current run.

## Acceptance criteria

- `MAX_MUTANTS` is removed; no code path refuses a run only because of its planned count.
- A run over a 7082-mutant target with `--mutation-authorize full` evaluates every mutant (or reports the remainder as `not_run` with the reason when stopped).
- With no authorization and an estimate above the threshold, the run stops after planning with the estimate and options; nothing is executed.
- Each mode (`COMPLETE`, `TARGETED`, `SAMPLED`, `PARTIAL`) is derived from the populations, and the report shows the populations behind every score.
- Native capabilities are used when present (lines and diff filters, concurrency, resume, incremental) and recorded; fallbacks are recorded as such.
- A resumed session continues only on an unchanged plan digest and state; a changed source or test refuses it.
- Reuse requires the full key of section 6; a changed covering test invalidates the reused result.
- Shard merge refuses gaps, overlaps and mixed plan digests.
- The mutation baseline replicates the execution run's command and test count.
- Existing behaviour for runs under the old limit is unchanged in counts and statuses (regression fixtures).

## Qualification scenarios

| # | Scenario | Expected |
| --- | --- | --- |
| Q1 | synthetic 7082-mutant module, authorized full run, 1 worker vs N workers | same per-mutant outcomes, different wall time; mode COMPLETE |
| Q2 | same, time budget that stops halfway, then `--mutation-session` resume | first run PARTIAL with bounds; after resume COMPLETE with identical outcomes to Q1 |
| Q3 | scope by function, by lines, by `changed-since` on a commit touching one function | TARGETED; universe unchanged; excluded counted with its rule |
| Q4 | 10 % sample with seed, repeated with the same seed | identical sample; estimate with interval; marked not comparable with Q1 |
| Q5 | interrupt the process mid-run (kill a worker, kill the engine) | completed results kept; the rest `not_run`; resumable |
| Q6 | change one test that covers reused mutants, rerun with reuse | those results re-executed; others reused and counted as reused |
| Q7 | change the runner or environment fingerprint | reuse and resume refused |
| Q8 | shards 0/3, 1/3 merged without 2/3 | merge refused or remainder `not_run`; never a full score |
| Q9 | the AXF-FTD-01 sibling-helper layout with a file selection | baseline runs the file's 2 tests with discovery semantics |
| Q10 | adversarial: a filter that keeps only killed mutants' lines; a sample tuned to survivors' absence | reported as TARGETED/SAMPLED with the rule, never comparable with the complete run; gates refuse the comparison |
| Q11 | each adapter (Cosmic Ray, StrykerJS, PIT) on its synthetic fixture | capability set recorded; native features used where available; populations consistent across adapters |
| Q12 | a project with tens of thousands of tests (generated fixture) and per-test coverage | estimate uses coverage mapping; planned work proportional to covering tests, not to the suite size |
| Q13 | memory budget on POSIX and Windows | enforced or recorded as not enforced, per platform |
| Q14 | imported reports (mutation-testing-elements, PIT XML, Cosmic Ray dump) with pending or reused entries | populations derived from the report; carried-over results counted as reused |

## Delivery order

1. Population accounting and run modes in `MutationRun` and the report (no behaviour change for existing runs) — this makes every later step honest.
2. Execution-context fix (AXF-FTD-01) and plan digest.
3. Estimate, authorization gate and optional budgets; remove `MAX_MUTANTS`.
4. Native scope selectors and recorded capability discovery per adapter.
5. Sessions and resumption; native parallelism with derived defaults.
6. Shards and merge; sampling with intervals.
7. Incremental reuse with the full key.

Each step ships with its qualification scenarios and a regression run of the current mutation fixtures.

## Research basis (read 2026-11-27)

Features cited from the tools' documentation; items marked *local* were also checked on the installed tool.

- Cosmic Ray: sessions record work and results so a stopped session continues where it left off; `exec` performs the remaining work (*local*, 8.9.0 `--help`); `http` distributor with per-worker clones (`cr-http-workers`); `cr-filter-lines` (*local*: 7082 → 236 left to run on the synthetic module), `cr-filter-git`, `cr-filter-operators`, `cr-filter-pragma` (*local*); outcomes `KILLED`/`SURVIVED`/`INCOMPETENT` and worker outcomes `NORMAL`/`EXCEPTION`/`ABNORMAL`/`NO_TEST`/`SKIPPED` (*local*). — [concepts](https://cosmic-ray.readthedocs.io/en/latest/concepts.html), [distributed tutorial](https://cosmic-ray.readthedocs.io/en/stable/tutorials/distributed/index.html), [tools API](https://cosmic-ray.readthedocs.io/en/latest/reference/api/cosmic_ray.tools.html)
- StrykerJS: `--incremental` with `reports/stryker-incremental.json`, partial results saved on interruption, `--force` to rerun a scope, `--mutate file:5-7`; incremental does not detect test changes by itself; `coverageAnalysis: perTest` (default) runs only covering tests; `concurrency` defaults to n−1 cores (n when n ≤ 4); `timeoutMS` 5000 and `timeoutFactor` 1.5; `dryRunTimeoutMinutes`; `ignoreStatic`. — [incremental](https://stryker-mutator.io/docs/stryker-js/incremental/), [configuration](https://stryker-mutator.io/docs/stryker-js/configuration/), [parallel workers](https://stryker-mutator.io/docs/stryker-js/parallel-workers/)
- Stryker.NET: `--since` (changed code or changed covering tests) and `--with-baseline`, mutually exclusive since 3.11. — [discussion #2860](https://github.com/stryker-mutator/stryker-net/discussions/2860), [discussion #2742](https://github.com/stryker-mutator/stryker-net/discussions/2742)
- PIT: incremental analysis via `historyInputFile`/`historyOutputFile` (experimental); `threads` (default 1); `timeoutFactor` and `timeoutConst`; the status of the `scmMutationCoverage` goal varies by version (verify per version). — [incremental analysis](https://pitest.org/quickstart/incremental_analysis), [Maven quick start](https://pitest.org/quickstart/maven), [mailing list](https://groups.google.com/g/pitusers/c/PJ8kqod_8Q8)
- cargo-mutants: `--shard k/n` without runtime coordination (same arguments and denominator for all shards; `slice` default since 26.0.0, `round-robin` alternative); `--in-diff` (not a substitute for full runs); `--jobs` with a jobserver. — [sharding](https://mutants.rs/shards.html), [in-diff](https://mutants.rs/in-diff.html), [parallelism](https://mutants.rs/parallelism.html)
- Infection: `--git-diff-filter`, `--git-diff-lines` with `--git-diff-base`, `--threads`; coverage generated only for filtered files. — [command-line options](https://infection.github.io/guide/command-line-options.html), [0.25.0 notes](https://infection.github.io/2021/09/06/whats-new-in-0.25.0)
- mutmut 3: test relevance by stack depth (`max_stack_depth`), copying into `mutants/`, `do_not_mutate`; parallelism and incremental options were **not verified** in this round. — [README](https://github.com/boxed/mutmut), [docs](https://mutmut.readthedocs.io)
