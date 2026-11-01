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
