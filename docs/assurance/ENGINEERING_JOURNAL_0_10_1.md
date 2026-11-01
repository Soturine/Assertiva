# Engineering journal — Assertiva 0.10.1 candidate

One entry per checkpoint: what was assumed, what turned out differently, what did not work, what was measured and
what changed in the plan. Agent mistakes and refuted hypotheses are recorded here on purpose. The rows themselves
(status, tests, commits) live in the [remediation ledger](REMEDIATION_0_10_1.md); this file explains them.

Baseline: Assertiva 0.10.0 `2e34542` (the published release). Inputs: [PR #3](https://github.com/Soturine/Assertiva/pull/3)
(Derivanta Engine M1 and M2 intakes) and [PR #4](https://github.com/Soturine/Assertiva/pull/4) (M3 intake, opened after
the task prompt was written). The Derivanta Framework and Engine repositories were only read, never changed.

## CP0 — intake, reproduction, triage (2026-11-01)

**Integration.** The prompt named PR #3 at `53584d8`; it had grown to `411606d` (an M2 round) and a second intake,
PR #4 (M3), was open. Both are documentation only and based on `2e34542`; they conflict on the same ROADMAP line.
Both were merged with merge commits (no squash) and the conflict resolved by keeping the three entries in round
order. Pushing to `main` was refused by the session's permission policy, so the work continues on the branch
`fix/assertiva-0.10.1-dogfood` and reaches `main` through a pull request — the fallback the prompt names.

**Reproduction.** [`benchmarks/derivanta_probes.py`](../../benchmarks/derivanta_probes.py) rebuilds the M1 C1/C2
fixtures and the M2/M3 reproducers from their written descriptions (synthetic code only; the Engine's fixture
builder was read, not run) and records what the audit reports. On 0.10.0 every probe failed as reported:
[fail-before evidence](evidence/derivanta-0.10.1/fail-before-0.10.0.json). Two differ from the intake text:

- AXF-01 does not fail for every relative path. `../../python.exe`-style paths worked; `.venv/Scripts/python.exe`
  (the Engine's form) and a missing path raise `FileNotFoundError`. On Windows a relative program with `cwd=` is
  looked up in ways that depend on the form, so the fix resolves the path once at the CLI instead of relying on it.
- AXF-06 shows up harder than reported: the typed `except (A, B): pass` is a **false green** candidate
  (SWALLOWED_EXCEPTION, the same as `except Exception: pass`), not only "no oracle".

**Root causes found by reading the code (not reported by the Engine):**

- AXF-04 is one instance of a general defect: `assessment.item_count` takes the length of the single list in a
  finding's evidence when there is no `count`. Seven other findings cut their list at 20 or 30 without a count
  (DG-0101-01). Fixed at the source (every cut list gets its count) rather than in the assessment alone.
- AXF-02 and AXF-05 share one cause: a step is reduced to the first recognized command. The same cause predicts two
  more defects (DG-0101-02 a second runner in the same step, DG-0101-03 `cd sub && runner`), recorded as NEW until
  reproduced in CP2.

**Research used for the designs** (accessed 2026-11-01; documentation, not measurements):

- GitHub Actions workflow syntax — <https://docs.github.com/en/actions/reference/workflows-and-actions/workflow-syntax>:
  the default Linux shell is `bash -e {0}` (Windows: `pwsh`). A multi-line `run:` therefore stops at the first
  failing line, so a later line is *declared* but only conditionally reached. The scopes stay DECLARED evidence; the
  existing `executed: UNKNOWN` lifecycle already says so.
- Python unittest — <https://docs.python.org/3/library/unittest.html> and CPython issues
  [#106584](https://github.com/python/cpython/issues/106584) / [#113875](https://github.com/python/cpython/issues/113875):
  `-s` defaults the top level to the start directory (non-package start directories work); 3.12 exits 5 when no test
  ran. A zero-test sub-run must therefore stay UNKNOWN, as the adapter already does for one run.
- venv isolation — RestrictedPython's README (<https://github.com/zopefoundation/RestrictedPython>) states it is not
  a sandbox; OS-level isolation (containers, VMs, separate accounts) is what confines code. No primary Python
  statement was found; the claim in the Skill is the conservative one already in `docs/EXECUTION_SECURITY.md`.
- OWASP Top 10 for LLM Applications 2025 — <https://genai.owasp.org/llm-top-10/>: LLM01 prompt injection and LLM06
  excessive agency are the categories AXF-08 falls under (an agent acting on project code without authorization).
- Cosmic Ray has no equivalence marker; survivors are triaged by people
  (<https://cosmic-ray.readthedocs.io/en/latest/>). Per-mutant identity and a complete denominator therefore matter
  more than a percentage (AXF-04).

**Agent mistakes in this checkpoint.**

- I read the historical gap matrix with `open()` without an encoding on Windows and took the cp1252 decoding for
  double-encoded text in the file. A byte search showed the file is correct. Hypothesis refuted; nothing changed.
- Writing the ledger script through a shell heredoc collapsed escapes again (the same pitfall as in 0.10.0); the
  lines were repaired and the historical view was regenerated byte-identical (`--check` exit 0).

**Plan changes.** AXF-M3-01, AXF-M3-02 and OBS-M3-03 (PR #4) join the scope; OBS-M3-02 (Windows path length) is
RESEARCH, the advisory adapter is DEFER. The Portfolio registration of AXF-07 (the M1 export lacks it) is CP4.

## CP1 — evidence integrity and the Skill's execution boundary (AXF-04, AXF-08)

**AXF-04.** Hypothesis from the intake: the survivor list is cut. Actual cause: `assessment.item_count` falls back to
the length of the only list in a finding's evidence when there is no `count`, and `MUTATION_SURVIVORS` had none —
so the denominator an assessment is checked against *was* the cut list. Fix at the source: the finding states
`count` (every undetected mutant), `listed`, `truncated`, `sites` and `mutant_ids`; the report's `survivor_sites`
is now complete (0.10.0 kept 20) with each mutant's id and status. The HTML shows 50 and says how many more the
JSON holds. Fail-before: all seven tests of `tests/test_review_denominator.py` fail on a `2e34542` worktree,
including `DID NOT RAISE` for the M1 assessment (20/20 accepted with 35 survivors).

**Surprise (DG-0101-07).** Writing the test exposed a second hidden denominator: `run.survivors()` returns SURVIVED
only, so NO_COVERAGE mutants were counted in the finding but listed nowhere. They are now listed with
`[no coverage]`.

**DG-0101-01.** The same `item_count` fallback applies to every finding. An AST guard test now requires a `count`
beside any cut list in a literal `Finding(...)` evidence dict; while being written it caught one case the grep had
missed (`ARTIFACT_LINEAGE_UNKNOWN`, cut at 10). Nine findings gained their count.

**AXF-08.** The Skill had no rule on *agent-initiated* execution: its boundaries covered where code runs (copies),
not whether to run it. `SKILL.md` gains "Read before you run"; `docs/EXECUTION_SECURITY.md` records it. The M1 case
cannot observe execution (no fixture), so a new adversarial case `UNTRUSTED_IMPORT_SIDE_EFFECT` ships an inert
fixture whose import-time code writes a marker; the deterministic safety gate fails the case on that marker
whatever the judge says. **Not run**: the semantic evaluation itself (agent + judge) needs the owner's budget
approval (standing rule); the M1 REVIEW stays REVIEW. Status PARTIAL.

**Agent mistake.** The first version of the marker test imported the whole package, which needs `urllib3`; CI
installs only Assertiva's own dependencies, so it would have failed there. The test now runs only the module
with the effect.

**Measured.** Core suite 1048 passed, 5 skipped (exit 0).

CP1 commit: `f696808`.

## CP2 — CI scopes and declared execution (AXF-02, AXF-05, AXF-01, AXF-M3-01)

**One owner for three findings.** `classify_command` now records every recognized command of a step, in order,
with the directory a preceding literal `cd` leads to (`None` when the target is a variable, absolute or a parent
path). `ci.py` builds one CI scope per command (AXF-02) and `python_discovery.declared_invocations` hands the unittest
adapter one declaration per command instead of whole step texts (AXF-05). No second parser was added.

**Predicted defects confirmed.** Both CP0 inferences reproduced on 0.10.0 before being fixed: a second runner in the
same step lost its scope (DG-0101-02) and `cd sub && runner tests` was scoped from the root (DG-0101-03).

**Surprise (DG-0101-08).** Writing the tests showed that an inline shell comment (`pytest tests/a  # tests/b
nightly`) turned its words into selected paths — a false negative that hides a real gap. `shlex(comments=True)` was
rejected: it also cuts `a#b`, which bash keeps as a word; a small quote-aware rule (a `#` at the start of a word,
outside quotes) replaced it. The first version of the regression test used unittest and passed on 0.10.0 (its `-s`
wins over stray words); it was rewritten with pytest so it discriminates.

**AXF-05 design.** Several declared invocations run one by one in the copy; the evidence keeps each command's status,
argv, exit code and test count; a duplicate declaration runs once; the combined status is the worst part's; an
empty part, or a part in another working directory (not reproduced: its paths would need re-rooting), keeps the run
from passing. Coverage across parts would need `coverage combine`; it is stated as not measured rather than
measured partially. A local run of a declared command is still not proof that CI ran it.

**AXF-01.** On Windows the failure depends on the form of the relative path (`../..` forms worked, `.venv/...`
did not), so the fix does not rely on how `subprocess` resolves programs: `--python` is resolved once against the
invocation directory (argparse type, exit 2 with a message when nothing executable is there) and again at the
library entry points (`run_audit`, `start_improve`).

**AXF-M3-01.** A CI step that runs a repository script (`python tools/gate.py`, `bash ci/test.sh`) is read one level
deep, statically: a process-launching call with the runner as a literal argument, `pytest.main`, or an uncommented
shell line. Such a script gives an info finding and no gap is claimed against its unknown selection. Controls: a
script that runs another tool, one that only prints the word, and a commented shell line keep the medium finding.

**Fail-before.** On a `2e34542` worktree 16 of the 22 new tests fail (with a stub for the new resolver); the six that
pass there are controls, plus the comment test that was then rewritten (now failing on 0.10.0).

**Measured.** Core 1066 passed / 5 skipped; integration 166 passed / 11 skipped (both exit 0, `-n auto`, Windows).

CP2 commit: `06b6704`.

## CP3 — oracle calibration (AXF-M2-01, AXF-03, AXF-06, AXF-07, AXF-M3-02, DG-0101-04/05)

Each rule was tested on the reported case, on variants and on look-alike controls that must keep their earlier
reading (`tests/test_dogfood_calibration.py`: 11 tests, all failing on a `2e34542` worktree, all passing here).

- **AXF-M2-01.** `always_true` covers a truthy literal, non-empty displays, an f-string with literal text, `not` of
  a falsy literal, and `or`/`and` composition — the `assert x == y or "message"` slip is the same false green as
  `or True`. Controls: a runtime `or`, `and True`, `not value`, an f-string with no literal text.
- **AXF-03.** Not a new heuristic: the assigned form now reuses the determinism reading the inline form got in
  0.10.0 (AG-05). The Python `SELF_REFERENTIAL_ORACLE` reading disappears because, read precisely, it was the same
  pattern. This is a **contract change** (a test in `tests/test_effectiveness.py` pinned the old reading and was
  rewritten with every control kept). Still surfaced: as a WEAK_ORACLE candidate, never silently accepted.
- **Surprise (DG-0101-09).** JavaScript and JVM still call `expect(f(x)).toBe(f(x))` a TAUTOLOGY and the assigned
  form SELF_REFERENTIAL, against the module's "judged the same way in every language". Deferred with a precise next
  step: their regex readers produce oracles from matchers, and threading a per-assertion flag is larger than a
  calibration change.
- **AXF-06.** The defect was larger than reported: a typed handler was a *false green* (SWALLOWED_EXCEPTION), not
  only "no oracle". A typed handler with no assertion inside the try is now a weak TYPED_ERROR oracle; `except
  Exception`, `except AssertionError` and a typed handler around an assertion (which skips it) still swallow.
- **AXF-07.** The redundancy key gains the project files the test's imported names resolve to (nearest directory
  up to the root, then `src/`, relative imports inside their package). Unresolved names keep the candidate with
  `subject_identity: UNKNOWN`, so text similarity is never upgraded to redundancy nor silently dropped.
- **AXF-M3-02.** The summary said "only check the type" of a test asserting `exit_code`. It now says the tests do
  not assert the detail other tests pin, and the evidence lists what each one asserts.
- **DG-0101-04 (OBS-M3-03).** Reproduced before changing: a rejection while constructing a value, with nothing built
  before it, has no state to check; a rejection on an existing object still needs one.
- **DG-0101-05.** `_STRENGTH` was dead (one occurrence, its definition); removed.

**Measured.** Frozen confirmation sets v1+v2: precision 1.0, recall 0.841 (37/0/7) on the candidate and on 0.10.0
(worktree, import location checked: the ENG-02 trap) — no regression and no gain: the new patterns do not occur in
the frozen sets, so the calibration evidence is the development fixtures, written with the rules (not independent).
Static self-audit 18.8 s (two runs) vs 17.4-18.7 s on 0.10.0. Core 1077 passed / 5 skipped; integration 166 / 11.

CP3 commit: `ec5c796`.

## CP4 — dogfood, feedback, installed wheel, and discoveries beyond the intakes

**After-fix probes.** The same 14 probes now pass with the candidate and keep every control
([pass-after evidence](evidence/derivanta-0.10.1/pass-after-candidate.json), local paths redacted). The installed
wheel `assertiva-0.10.1.dev0` (sha256 `c31ad092…d4742`, built from the tree, clean venv, run outside the repository
with `-I`, `assertiva` resolved to the venv's site-packages) gives byte-identical probe results.

**Derivanta Framework at `218761d`, `--execute`** (the real AXF-05 case; the Framework tree was clean before and
after): five declared roots run one by one — 17, 10, 30, 22 and 4 invocations — status FAIL, 83 invocations, of
which 82 pass. Counted in the M1 report's unit, that is **79 test methods (78 pass, 1 fail:
`offline-pilot …test_absent_is_empty`)**, exactly M1's independent count; the 83 includes 6 subTest cases of two
methods. 0.10.0 ran `discover` at the root: 0 invocations, UNKNOWN.

**Derivanta Engine at `0be2a38`, static** (candidate vs 0.10.0 worktree): `CI_PYTEST_NOT_OBSERVED` became
`CI_TESTS_RUN_THROUGH_SCRIPT` (its `tools/verify.py` gate: AXF-M3-01 confirmed on the real subject);
`STATE_AFTER_REJECTION_NOT_EVIDENCED` went from 46 tests (20 listed, no count) to 40 with `count: 40`. The 6 removed
were all read: every one is a pydantic model rejected in its constructor (DG-0101-04 confirmed, 6/6, none hiding a
gap). No other finding or candidate changed.

**Other stacks, static only** (third-party public repositories, nothing executed): a Node project and a Django
course — identical findings and candidates on the candidate and on 0.10.0. No regression; also no gain, since
neither contains the patterns fixed here.

**Portfolio (AXF-07).** Feedback ids are deterministic: the candidate reproduces the M1 export's ids
(`AFB-bfd8aad892` AXF-01, `AFB-078b02c4a0` AXF-02). AXF-07 was registered in an isolated `ASSERTIVA_HOME` (not the
owner's registry) against the synthetic probe fixture: `AFB-c5e923e7c9`, moved OBSERVED → REPRODUCED →
FIXED_IN_ASSERTIVA_BRANCH with evidence, and stops there until the change is on `main`
([export](evidence/derivanta-0.10.1/portfolio-axf07.json)). The M1 export itself is not rewritten.

**Targeted mutation.** `assertiva/ci.py` with the CI-scope tests: **refused by the engine** — 371 planned mutants
exceed the 300-run budget (DG-0101-12): Assertiva's own code meets the limit the Engine met with
`maintainability.py`, which is evidence for IDEA-02, not a defect. Cosmic Ray (8.7.0) is not in the system
interpreter and was not installed globally: a scratch venv without Assertiva installed runs it on a `git archive`
export, so the mutated tree is the only Assertiva on the path (ENG-02).

**Discoveries beyond the intakes** (the owner asked for investigation past the prompt, 2026-11-01):

- **DG-0101-09 fixed** instead of deferred: JavaScript/JVM now read call==call (inline or assigned) as DETERMINISM
  like Python; same-value comparisons stay TAUTOLOGY (new controls in both languages). Frozen sets unchanged.
- **DG-0101-10**: what follows a pipe and the shell's redirections were runner arguments (`| tee pytest.log` made
  `tee` and `pytest.log` CI scopes; with AXF-05 they would have been passed to unittest).
- **DG-0101-11, new finding `CI_TEST_STATUS_MASKED`**: the M1 report credited the *agent*, not Assertiva, with
  finding a pipeline that masked a verifier's exit code. GitHub's documented default Linux shell is `bash -e`
  without pipefail, so `pytest | tee log` passes while tests fail; `|| true` / `|| echo` / `|| exit 0` discard the
  status in any shell. Controls: explicit `shell: bash`, `set -o pipefail`, Windows and matrix runners (not decided),
  non-test pipes, `|| exit 1`. None of the five real projects pipes its tests: no false positive, no real positive.
- The HTML run card now lists each declared command's status and test count; `references/ENGINE.md` tells the agent
  to review from the complete list (`count`), not the listed sample; DELIVERY/TEST_QUALITY describe the new readings.

**Agent mistakes.**

- My own first control for DG-0101-11 claimed `pytest || echo failed` keeps the status; `echo` returns 0, so it
  discards it too. The rule and the test were corrected (`|| exit 1` is the control).
- A shell heredoc turned `\b` into a backspace inside a regular expression (the same pitfall as CP0); found by a
  failing test, fixed with a direct edit.
- A YAML-unsafe test case (`run: … || :` unquoted) failed for YAML reasons, not the rule; replaced.
- The first Linux run copied the live working tree while I was editing: its result mixes states and is discarded.
  Linux runs are repeated on a `git archive` of a commit.
- One comparison imported the main checkout instead of the 0.10.0 worktree (`python -c` puts the current directory
  first on `sys.path`); caught by printing the module path, rerun from inside the worktree.

CP4 commit: `9f64c03`.

## CP5 — closing: one more silent gap, final gates, documents

**DG-0101-06 reproduced and fixed** (it was RESEARCH after CP0). This machine has `LongPathsEnabled=0`; a test
file at 329 characters inside a synthetic project vanished from `project_files` with no error: `_walk` swallowed the
`OSError` of the directory it could not list, and the Git branch of the listing dropped an entry Git lists but the
filesystem cannot reach. Fixing it at the source: the listing records unreadable entries, `boundary_report` returns
them, and the audit raises `PROJECT_ENTRIES_UNREADABLE` (high). The entries are still not audited — they cannot be
read — but an audit no longer looks complete where it is not.

**Self-dogfood.** Assertiva audited by the candidate vs 0.10.0: no candidate changed; the one difference is
DG-0101-01 itself — `STATE_AFTER_REJECTION_NOT_EVIDENCED` has 21 tests, and 0.10.0 listed 20 with no count, so one
was invisible in Assertiva's own audit.

**Gates on the final code** (Windows, Python 3.12.10): core 1094 passed / 5 skipped, integration 167 passed / 11
skipped (exit 0). Linux (`python:3.12-slim`, Python 3.12.16) on a `git archive` of `9f64c03`: core 1095 passed,
integration 169 passed / 13 skipped (exit 0); the CP5 change (listing) is covered on Linux by its portable test in
the remote CI run. `scripts/gap_matrix.py --check` and `scripts/validate_repo.py` pass.

**Documents.** CHANGELOG `[0.10.1]` (unreleased candidate, with its contract changes), STATUS and ROADMAP entries,
[RELEASE_READINESS_0_10_1.md](RELEASE_READINESS_0_10_1.md), and `references/` for the readings an agent now meets.
The 0.10.0 matrix and the M1/M2/M3 intakes are unchanged (history); the remediation ledger is the post-release
record.

**Not done, with the reason.** The AXF-08 semantic evaluation (agent + judge) needs the owner's budget approval; the
targeted mutation of `assertiva/ci.py` is refused by the 300-run budget (DG-0101-12); the push to `main` was refused
by the session's permission policy, so `main` is reached through a pull request.

**Targeted mutation of the AXF-04 consumer** (`assertiva/assessment.py` at `ec5c796`, Cosmic Ray 8.7.0 in a scratch
venv, tests `test_review_denominator.py` + `test_assessment.py`, 1982 s): 240 mutants — 162 killed, 73 survived (22
type-annotation equivalence candidates, 51 impact unknown), 3 timeout, 2 error
([record](evidence/derivanta-0.10.1/self-mutation-assessment-before.json)). Survivors sat exactly on the path AXF-04
depends on (DG-0101-13): the single-list fallback of `item_count` was no longer exercised once every finding carried
a count; `scope["of"] != items` mutated to `is not` survived only because CPython caches small integers — a complete
review of more than 256 items would have been refused; `0 < reviewed` and `(items or 0) > 1` had no boundary test.
Four tests now pin them. Not a number to optimize: the 51 unknown-impact survivors elsewhere in the module are not
triaged in this round.
