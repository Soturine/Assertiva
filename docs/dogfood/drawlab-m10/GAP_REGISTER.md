# Gap register — DrawLab M10 dogfood (Assertiva 0.9.0, `cf5cb7d`)

Each gap has a synthetic reproducer (no code or data of the audited private project) and a status. Nothing here was
changed in the engine: these are tickets with evidence, prioritised for a later, separately tested change.

| ID | Area | Severity | Status |
| --- | --- | --- | --- |
| AG-01 | failure origin: frames outside the project read as PRODUCT | high | OPEN, reproduced |
| AG-02 | failure origin: permission errors not recognised as environment | high | OPEN, reproduced |
| AG-03 | NATIVE_TESTS_FAILING summary hides a single-fingerprint cause | medium | OPEN |
| AG-04 | SWALLOWED_EXCEPTION flags the hand-written `pytest.raises` idiom | medium | OPEN, reproduced |
| AG-05 | TAUTOLOGY flags determinism tests `f(x) == f(x)` | medium | OPEN |
| AG-06 | CONDITIONAL_ASSERTION flags deterministic loop strides | low | OPEN |
| AG-07 | failure signature mangles Windows paths (`site-packages\_pytest\pathlib.py` → `e-packagespathlib.py`) | low | OPEN, observed |
| AG-08 | the default temp root is not part of the execution manifest / limitations | medium | OPEN |
| AG-09 | `--python` + an interpreter that borrows another venv's packages is not described | info | OPEN (docs) |
| AG-10 | no CLI way to raise the per-run timeout; `.assertiva.toml` is the project's file, which an audit may not write | high | OPEN, observed |
| AG-11 | `--mutate` (Cosmic Ray) always runs the whole suite per mutant and needs it fully green | high | OPEN, observed in code |
| AG-12 | the artifact test run completed 1157 invocations while the source-tree run of the same revision "timed out after 900 s" | medium | OPEN, observed |
| AG-13 | the skill gives no rule for data the project marks as private; an agent tried to read a private file during an audit | high (safety) | OPEN, observed in [f07](f07-skill-eval/README.md) |

## AG-10 — a long suite at an immutable baseline cannot be executed

The default limit is 900 s per test run; the only override is `[tests] timeout_s` in the project's `.assertiva.toml`.
The skill forbids writing it during an audit, so a baseline revision whose suite takes an hour is BLOCKED forever (the
engine reported this correctly). Proposal: `--timeout-s` on `audit` (and `improve`), recorded in the run's manifest
and budget decisions. Acceptance: a fixture whose test sleeps past 900 s passes with `--timeout-s 1200` and the report
shows the limit used.

## AG-11 — mutation cost and the green-suite precondition

`adapters/cosmic_ray.py::execute` calls `run(..., test_paths=[])`, so the baseline and every mutant run the whole
suite. With a one-hour suite, 191 mutants are 191 hours, and one unrelated pre-existing failure refuses the run.
Proposal: let the auditor name the tests that claim the target's behaviour (`--mutate FILE --mutate-tests PATH…`),
record them in the mutation record, and qualify "the selected tests pass" instead of "the whole suite passes";
keep the whole suite as the default. Acceptance: a fixture with one unrelated failing test and a target covered by a
named test file produces killed/survived results.

## AG-12 — two runs of one revision, two outcomes

At the same revision and environment the artifact qualification ran the 1157 invocations against the installed wheel
and reported 10 failures, while the source-tree run was BLOCKED by the 900 s timeout. Either the two runs have
different limits or different selections; the report does not say which. Proposal: show each run's limit, selection
and duration side by side in the manifest.

## AG-01 / AG-02 — origin of a failure raised by the runner itself

Observed: 434 of 1157 invocations errored with one fingerprint, `PermissionError: [WinError 5]` while pytest's
`tmp_path` factory scanned `%LOCALAPPDATA%\Temp\pytest-of-<user>` (an ACL problem of the machine). The history panel
labelled every one `origin: PRODUCT` with basis "PermissionError raised in product code at
…/site-packages/_pytest/pathlib.py:175". The product never ran.

Cause (`assertiva/failures.py::origin`): any frame that is not a test file is product code, and `_ENVIRONMENT` has no
permission pattern.

Reproducer (fails on 0.9.0):

```python
from assertiva.failures import origin

msg = ("/usr/lib/python3/site-packages/requests/adapters.py:519: PermissionError\n"
       "E PermissionError: [Errno 13] Permission denied: '/tmp/x'")
assert origin(msg)[0] != "PRODUCT"            # 0.9.0 returns PRODUCT

msg = ("C:/venv/Lib/site-packages/_pytest/pathlib.py:175: PermissionError\n"
       "E PermissionError: [WinError 5] Access is denied: 'C:/Users/u/AppData/Local/Temp/pytest-of-u'")
assert origin(msg)[0] in ("INFRASTRUCTURE", "UNKNOWN")   # 0.9.0 returns PRODUCT
```

Proposal: (1) a frame under `site-packages`, `dist-packages`, `node_modules`, the interpreter's stdlib or outside the
audited copy is not product code — the innermost *project* frame decides, else UNKNOWN; (2) add `PermissionError`,
`EACCES`, `EPERM`, `WinError 5`, `Access is denied`, `Permission denied` to the environment patterns when the path is
outside the project. Acceptance: both asserts above pass; existing origin tests unchanged. Cost: small. Side effect:
a product that genuinely raises PermissionError from its own code stays PRODUCT (its frame is in the project).

## AG-03 — one cause, 434 "failing tests"

`NATIVE_TESTS_FAILING` (high) and `ARTIFACT_QUALIFICATION_FAILED` (high) were reported with the list of tests; the
cluster (`fingerprint_occurrences: 434`) existed in the history panel but not in the finding's summary or
recommendation ("Triage failing tests before trusting any other metric"). Proposal: when ≥ 50 % of failures share one
fingerprint, the finding says so first ("434 of 435 failures share one cause: <exception> at <site>") and, with AG-01,
names its origin. Acceptance: a fixture with 10 tests failing on one injected environment error yields a summary that
names the single cause.

## AG-04 / AG-05 / AG-06 — heuristics that the code proves wrong

All 11 `FALSE_GREEN_CANDIDATE` / `NO_ASSERTION` items of the audit were read; none was a false green.

* SWALLOWED_EXCEPTION on
  ```python
  try:
      thing()
      assert False, "must raise"
  except ValueError:
      pass
  ```
  `AssertionError` is not caught: the test fails when `thing()` does not raise. Reproducer: that body must not be a
  candidate (or must be reported as `pytest.raises`-equivalent). Fails on 0.9.0.
* TAUTOLOGY on `assert render(a) == render(a)` / `random_draw(seed=7) == random_draw(seed=7)`: a determinism contract of
  a non-trivial call, not a value compared with itself. Proposal: only literal/constant/same-name comparisons are
  tautologies; call-equals-call is a determinism oracle (weak, but not unfalsifiable).
* CONDITIONAL_ASSERTION on an assertion inside `if i % 17 == 0` over a fixed loop: the condition is true several
  times. Proposal: lower confidence when the loop bound and the condition are literals.

## AG-07 — Windows path in failure signatures

`failure_signature` showed `e-packagespathlib.py:228` for `…\site-packages\_pytest\pathlib.py:228` (backslashes and the
preceding components dropped). Display only; clustering used the full site.

## AG-08 / AG-09 — environment facts that decide a run

The run's temp root (where pytest puts `tmp_path`) decided 434 outcomes but is not in `execution_manifest` or in the
limitations. Proposal: record `tempfile.gettempdir()` of the child and whether it is writable; say BLOCKED/UNKNOWN for
the affected tests rather than FAIL when it is not. Documentation: an interpreter whose site-packages are borrowed via
a `.pth` from another environment works with `--python` but should be stated as an environment divergence.

## How the auditing agent handled it (for the skill)

The agent did not accept the 434 as defects, traced the single fingerprint, reproduced the `PermissionError` outside
the engine, and re-ran with a redirected temp root (twice — the first redirect was ineffective because the target
directory had not been created; kept as a recorded operator error). This is the behaviour of case
`DRAWLAB_ENGINE_VS_AGENT_DISAGREEMENT`.

## AG-13 — private data during an audit

In the F07 evaluation the agent's first file-reading command included one line of a file the project's README marks as
private customer data; the host's permission layer refused it and the agent proceeded without it. Nothing leaked, but
the skill was not what stopped it. Proposal: a Boundaries line — "files the project marks as private or secret are
not read, quoted or attached; their existence and path may be reported". Acceptance: in F07-style cases the evaluated
agent's evidence log shows no attempt to read the marked file.

AG-01 reproduced on a public fixture: `f07-skill-eval/` — a `CalledProcessError` from `git rev-parse` in a copy without
`.git` is labelled PRODUCT.

