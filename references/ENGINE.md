# The Assertiva engine

## Contents
- Availability
- Calls: what each costs and what it buys
- Reading the output
- What engine findings are
- Attaching your assessment to the report
- Driving `assertiva improve`

## Availability

`assertiva --version` answers when the engine is installed. When it is not, keep auditing: read, reason, and, where it is safe, run the project's runner in a copy outside the project. Say that engine evidence and the HTML report were not produced. Installing the engine is the user's call.

## Calls: what each costs and what it buys

| Call | Buys | Costs |
| --- | --- | --- |
| `assertiva audit <p> --output json` | static inventory and oracle / negative-path signals (Python), the verification surface (GitHub Actions, Azure Pipelines, GitLab CI, Jenkins, pre-commit, `package.json` scripts, Maven), declared matrix and artifact lineage, project boundary facts | seconds; executes nothing |
| `… --execute` | native runs of the project's declared runner — pytest, unittest, Django `manage.py test`, Jest, Vitest, Playwright, Maven or Gradle (Java, Kotlin/JVM, Android local tests, the JVM targets of Kotlin Multiplatform) — in a disposable copy: per-invocation outcomes, collection errors, coverage when the tooling is present, built-wheel qualification (Python), local history | one suite run plus artifact build; never installs dependencies or browsers |
| `… --execute --provision` (or `provision = true` for the project in the consent file) | what the tests need, prepared in a run workspace outside the project and removed at the end: a virtual environment from the declared requirements (an installed compatible interpreter is found, never downloaded), `npm ci --ignore-scripts`, a Temurin JDK and a Gradle distribution (sha256-verified; the project's wrapper jar never runs), a disposable PostgreSQL (generated password; verified by a mutually authenticated login before tests connect). The report lists each step (DONE, REUSED, BLOCKED, FAILED, NOT_NEEDED), its downloads and divergences | downloads on first use (cached in `ASSERTIVA_TOOLS` or `<ASSERTIVA_HOME>/tools`); what cannot be prepared (an Android SDK, a missing interpreter, a device) is BLOCKED, never failed |
| `… --changed-since REV [--execute]` | the tests with a proven path to the change, widened whenever impact is not proven (Python graph) | like the above, on the selected set |
| `… --run-check CHECK_ID` (repeatable) | reproduces a discovered check — what CI, a hook or a script declares, by its id in `verification_surface` — in a disposable copy. A test runner with an engine adapter runs through it (per-test outcomes); anything else runs as a whole command (exit status, no per-test outcomes). Each record keeps the executed argv, exit code / signal / timeout, duration, output digest, environment, and `parity` per dimension (command, selection, revision, environment, services, result) | that command's run. Tests and side-effect-free checks run when named; migrations, containers, custom and unknown commands need the user's consent (the exact command in `<ASSERTIVA_HOME>/consent.toml`, never a file of the project); deploy/publish and compound shell steps (`a \| b`, `a && b`) never run |
| `… --ci-run FILE` | a CI run the provider reported (`gh run view <id> --json headSha,conclusion,jobs,url,workflowName`, or a GitLab pipeline from its API), compared with the audited revision: `SAME_REVISION` proves it (`EXTERNAL_VERIFIED`), a different SHA or local changes do not | reading a file you exported with the user's provider access; nothing is fetched by the engine |
| `… --coverage-report F` / `--junit-xml F` / `--mutation-report F` | ingests existing tool output (coverage.py, istanbul, LCOV, Cobertura, JaCoCo; JUnit XML; Stryker-family JSON, PIT, mutmut) — including output you produced in your own copy | reading a file |

Optional `.assertiva.toml` (the project's file; never write it during an audit) only describes the project: `[tests] runners` and `timeout_s` when detection cannot know. Consent is never read from a project: commands with effects and withheld variables are allowed only in `<ASSERTIVA_HOME>/consent.toml` (`[[project]]` with `root`, `authorize`, `env`), which only the user writes.

Executions run project code with the user's permissions and network: a disposable copy protects the project tree, not the machine. Credential-looking variables and connection targets (`DATABASE_URL`, `PG*`, `REDIS_URL`, `DJANGO_SETTINGS_MODULE`, …) are withheld, with or without a password in the value (names in the report's limitations). A consented connection reaches only this machine (localhost); one pointing at another host stays withheld. When tests need a database, use a disposable local one (a container or SQLite); never propose consent for a command or variable that reaches a shared, staging or production system. Consent is the user's decision.

Options combine in one call; every call writes one canonical `audit.html` + `audit.json` under `ASSERTIVA_HOME` (outside the project) and replaces the previous one for the project. Exit code 0 means the audit ran and reported (a failing suite still exits 0: the verdict is in the report), 2 a refusal or misuse, 3 a read-only violation.

## Reading the output

Parse the whole JSON; do not sample or truncate it. Each run says who produced it (`provenance`: `ENGINE_EXECUTED`, or `EXTERNAL_UNVERIFIED` for a report the engine only read); coverage says `origin` (`MEASURED` / `INGESTED`) and, when the format has per-file numbers, `product_counts` without test files; JUnit reports carry cases, not declarations, and accumulated case time, not the run's duration. `execution_manifest` identifies the code (tree digest; no SHA without version control), what ran and what was only read. Useful fields: `run_id`, `status`, `findings[]` (`id`, `code`, `severity`, `summary`, `evidence`), `states.current.runs[]` (per-outcome `outcomes`), `claim_boundary` (`observed`, `not_evidenced`, `limitations`), `execution_budget.decisions` (what ran, was reused or not run, and why), `report_path`. Read `report_path` with `python -c "import json,sys; print(json.load(sys.stdin)['report_path'])"` or `jq -r .report_path`, and confirm the file exists; a missing path after a successful call is an engine defect.

## What engine findings are

- **Deterministic** (runner outcomes, collection errors, report parsing, links, artifact checks): true facts about what was observed. Their *importance* is still yours to judge in context.
- **Declared** (CI and build configuration): what configuration says, not what ran.
- **Heuristic** (`WEAK_ORACLE_SIGNAL`, `ERROR_STATUS_ONLY_SIGNAL`, `BROAD_ERROR_EXPECTATION_SIGNAL`, `SUITE_SMOKE_DOMINANT`, review candidates): static AST signals. They follow same-module helpers that assert, `assert*`-named calls, test-double interaction checks and call guards (`side_effect=AssertionError`), but not imported helpers, fixtures or custom matchers, and they cannot read a "must not raise" contract; so they still produce false positives and miss weak tests that look strong. `WEAK_ORACLE_SIGNAL` lists each candidate's signal (`evidence.signals`).

Severities are the engine's defaults for the code, not a judgment of this project.

### Test effectiveness

Every audit reads each test in every language it supports (Python by syntax tree; JavaScript/TypeScript and Kotlin/Java lexically, limits stated per language) into the same facts — oracles, doubles, boundaries crossed or simulated, observed surfaces, smells, declared level — and nominates candidates with one set of rules: `FALSE_GREEN_CANDIDATE` (swallowed exceptions, assertions only behind a condition, tautologies, unawaited async work, actions nothing checks, snapshot-only), `WEAK_ORACLE_SIGNAL`, `TEST_FIDELITY_MISMATCH` (declared integration/E2E with every boundary simulated), `REDUNDANCY_CANDIDATE` (same body within one component, repeated parameter rows), `TEST_SMELL_SIGNALS`. Each says what the evidence shows, why it may be weak, what would settle it, and its basis — INFERRED unless an execution confirmed it. They are leads: dispose each material one in your assessment (per-test `subjects` when you reviewed some of them). A sleep in a timeout or expiry test, a conditional whose `else` also checks, and helper or inherited assertions are not nominated; anything else static analysis cannot see is yours to judge. With a mutation report that names the killing tests, `mutation_sensitivity` shows which tests are the only detector of a mutant.

## Attaching your assessment to the report

`assertiva audit <project> --assessment <file.json>` attaches your assessment to the latest audit of that project and re-renders the same `audit.html` / `audit.json`. It executes nothing. It refuses (exit 2, with the reason) when the assessment names another run, when the project changed since that run, or when the assessment is malformed. Attaching again replaces the previous assessment. Engine findings and their raw evidence are never removed: your disposition sits next to them.

```json
{
  "run_id": "<run_id from the audit JSON>",
  "summary": "Your conclusion in one paragraph, in the user's language.",
  "lang": "pt-BR",
  "dispositions": [
    {
      "finding": "PROJECT_LINK_ESCAPES_ROOT",
      "disposition": "CONTEXTUAL",
      "priority": "info",
      "rationale": "The link is an untracked local install of an audit tool, not part of the product, its build, tests or CI.",
      "evidence": ["git status: ?? .claude/", ".claude/skills/assertiva -> ../Assertiva"]
    },
    {
      "finding": "WEAK_ORACLE_SIGNAL",
      "disposition": "PARTIAL",
      "rationale": "3 of 4 assert through assert_problem(), which checks status, code and field.",
      "evidence": ["tests/helpers.py:12-30", "tests/test_cart.py:41"],
      "scope": {"reviewed": 4, "of": 4},
      "subjects": [
        {"subject": "tests/test_cart.py::test_cart_total_smoke", "disposition": "CONFIRMED", "note": "asserts only response.ok"}
      ]
    }
  ],
  "findings": [
    {
      "id": "reservation-rollback-untested",
      "title": "Stock reservation rollback is never exercised",
      "claim": "No checkout test makes payment fail after stock is reserved.",
      "why": "A broken rollback would leave stock reserved forever while every test stays green.",
      "priority": "high",
      "basis": "INFERRED",
      "evidence": ["shop/checkout.py:88-120", "tests/test_checkout.py (all 9 tests)"],
      "recommendation": "Add a test where payment fails after reservation and assert the stock level afterwards."
    }
  ],
  "unknowns": ["Whether CI ran on this revision: no provider access."]
}
```

- `disposition` is about the engine's claim, not about the code: `CONFIRMED` (the claim holds as stated), `PARTIAL` (holds for some items: give `subjects`), `CONTEXTUAL` (the fact is true but its impact here differs: `priority` required), `FALSE_POSITIVE` (the claim does not hold here), `UNRESOLVED` (reviewed, evidence insufficient).
- `subjects` name individual items of the finding, one entry per item, with the same meaning: for a weak-oracle finding, a test that really is weak is `CONFIRMED`, a test the heuristic misread is `FALSE_POSITIVE`.
- `priority`: `high`, `medium`, `low` or `info`; optional except for `CONTEXTUAL` and agent findings; not allowed on `FALSE_POSITIVE` (it leaves the action plan).
- A whole-finding `CONFIRMED` or `FALSE_POSITIVE` on a finding with several items needs `"scope": {"reviewed": n, "of": n}` covering every item; with fewer reviewed, use `PARTIAL` or `UNRESOLVED` and say what was reviewed.
- `basis` for your own findings: `OBSERVED` (you saw it run or read it directly), `DECLARED` or `INFERRED`. Every disposition and finding needs at least one evidence reference.

## Driving `assertiva improve`

1. `assertiva improve <p>` measures the baseline in an isolated copy and prints a candidate workspace. Write candidate changes only there.
2. `assertiva improve <p>` again qualifies the candidate. Optional:
   - `--negative-controls <file.json>`: a list of `{"control_id", "path", "find", "replace", "claim", "tests"?}` deliberate behavior-breaking edits the tests claiming `claim` must detect (run only in disposable copies);
   - `--mutation-report baseline=<path>` / `candidate=<path>`: mutation-tool reports for each state (run the tool in the matching workspace; the engine ingests, it does not mutate);
   - `--coverage-report baseline=<path>` / `candidate=<path>`;
   - `--run-check <CHECK_ID>`: only when the human authorizes a specific discovered delivery check (migration, container, custom command). Deploy and publish checks never run.
3. Show the report. Approval (`--approve <change ids>`) names specific changes and belongs to the human.
4. `--discard` drops the candidate without touching the project.

Qualification has five pillars — execution, behavioral assurance, fault sensitivity, delivery fidelity, stability and cost. A check that did not run never passes a pillar; read the remaining unknowns before calling a candidate ready.
