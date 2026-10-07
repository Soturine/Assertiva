# User Experience and Reporting

Assertiva exposes two user-facing workflows:

```text
assertiva audit
assertiva improve
```

Everything else is internal orchestration, adapter behavior, or an advanced implementation detail.

## Audit

`audit` inspects the project, executes only permitted verification work, measures evidence and reports gaps. It never changes project files.

It may inspect tests, coverage, hooks, CI/CD, build/package checks, validation/error paths, test composition, fixtures, mocks, browser evidence, security/static checks and other verification sources discovered through adapters.

The result contains:
- current test and verification inventory;
- observed execution/results;
- coverage and other available metrics;
- weak or shallow evidence;
- missing behaviors and verification gaps;
- CI/local/deployment parity gaps;
- recommended changes;
- explicit unknowns and limitations.

Recommendations are proposals, not changes already present in the project.

## Improve

`improve` performs the audit first, creates candidate changes in an isolated workspace, verifies the candidate, compares it with the baseline, and presents the result before touching the original project.

The user sees one simple flow. Candidate qualification includes **test-the-tests**: the candidate suite is challenged with available mutation/negative-control evidence, original regression evidence, coverage/oracle analysis, pipeline-equivalent checks and, when explicitly authorized and safe, an ephemeral non-production preview deployment.

The user sees one simple flow:

```text
audit current state
        ↓
build candidate outside the project
        ↓
verify candidate
        ↓
show before vs candidate
        ↓
ask for approval
        ↓
apply only when approved
        ↓
verify applied result
```

The isolation mechanism is intentionally hidden from ordinary UX. It may use a temporary workspace or Git worktree internally, but users should not need to learn a separate "sandbox mode".

Candidate removals are conservative. Assertiva may recommend retirement or consolidation and may evaluate that change only inside the isolated candidate, but the original project test remains active until explicit human approval. Original tests are not commented out in active source files by default; baseline revision/fingerprint plus side-by-side diff preserves them more safely.

Candidate qualification is defined in [Candidate Qualification and Test-the-Tests](CANDIDATE_QUALIFICATION_AND_TEST_THE_TESTS.md).

Before applying, Assertiva must detect stale source changes and refuse unsafe blind overwrite. Application should be patch/change-set based rather than replacing newer user work.

## Internal write policy

The runtime, not only the prompt, enforces write boundaries.

- `audit`: project files are read-only.
- `improve`: candidate writes are isolated from the original project.
- approved application: only the approved candidate change set may modify the project.

Read-only analysis artifacts and reports should default to Assertiva-owned storage outside the audited repository so an audit does not dirty the working tree.

Project boundaries are part of the write policy: links are entries identified by their target and never followed, content outside the project root is never copied in as project material, and an approved change is refused if its path traverses outside the project, passes through a linked directory, introduces a link leaving the project, or collides with an existing path by case only. Application is all-or-nothing: if any approved change fails to install or the result does not match the candidate, every touched file is restored.

## Assurance Report

Assertiva produces one responsive HTML report. The same report model adapts to the workflow.

For audit:

```text
CURRENT
+ FINDINGS
+ RECOMMENDATIONS
+ REMAINING UNKNOWNS
```

For improve:

```text
BASELINE
vs
CANDIDATE
+ CHANGE SET
+ EVIDENCE DELTA
+ REMAINING GAPS
```

After approval/application:

```text
BASELINE
vs
CANDIDATE
vs
APPLIED
+ POST-APPLY VERIFICATION
```

Never describe candidate results as already present in the project.

## Visual contract

The HTML report is one self-contained, offline page (inline CSS and a small progressive-enhancement script; no CDN, web font, framework or network request). It works without JavaScript; the script adds language and theme switching, filters, copy buttons and opening a finding from a link. Rendering lives in `assertiva/report_html.py`, the presentation catalog in `assertiva/report_i18n.py`; neither changes the report model.

The page reads in four areas:

1. **Overview** — project, revision, workspace state, workflow and states shown (Current, or Baseline vs Candidate, + Applied); the report status in words with its raw value; the decision surface; key evidence cards; **What does green prove?** (Observed / Not evidenced / Limitations); highest-priority findings; recommended improvements grouped by domain.
2. **Evidence** — candidate qualification and change set (improve), metrics by state, evidence delta, negative paths, mutation, built artifact, delivery, selection, history.
3. **Verification** — the verification surface grouped by origin (local, hooks, CI, build, …) with the full command, gate and tier behind each row plus a table view; runs and provenance; execution budget.
4. **Details** — all findings with severity/category/search filters, remaining unknowns, provenance pairs, the raw report JSON.

Decision surface rules (presentation only; no new semantics):

- **What is working** lists evidence-backed strengths drawn from structured data only (a run that passed, a qualified artifact, no surviving mutant, detected negative controls, passed qualification checks), each with its tier. The absence of a finding is never shown as a strength.
- **What needs attention** lists high and medium findings and failed or blocked qualification checks.
- **What is not evidenced** is the claim boundary's not-evidenced list.
- **What to improve next** is an existing recommendation, and only when the evidence ranks one: a finding whose own recommendation says it comes first (collection errors, failing tests), or a single finding at the highest severity. Otherwise the page says no single next action can be selected.
- The overall status is never painted as success; green belongs to specific evidence.

Each finding shows a human title, severity, category, evidence basis (tier), what was observed, why it matters, the evidence (affected items, progressively disclosed), the recommended improvement marked **Proposed** (proposed ≠ applied ≠ verified), what would close it, and technical details (finding code, original text, raw evidence). Title, category, basis, "why it matters" and "what would close it" come from a catalog keyed by finding code; "why" restates the consequence the engine's own text states and "close" negates the detection condition.

Metrics use display names with the metric id beneath; the delta column appears only when states are compared. Charts are drawn only for compared states and sit next to tables with the same numbers. Status is never conveyed by color alone (icon and text), and the page supports keyboard navigation, light and dark themes and reduced motion, with no horizontal scroll down to phone width.

### Languages

English (canonical) and Brazilian Portuguese. The choice is remembered when browser storage is available; otherwise the browser language decides, falling back to English. Text is looked up by stable key; engine sentences are translated only when they match a fixed English template exactly, and otherwise appear as written, marked `lang="en"`. Finding codes, metric ids, enums, commands, paths, hashes, revisions, adapter names and raw evidence are never translated. Only the strings a page uses are embedded.

## Metric discipline

The report distinguishes measured, candidate-measured, inferred and unknown values.

Good:

```text
Branch coverage
Baseline: 67.4% observed
Candidate: 78.8% observed in isolated verification
```

Bad:

```text
Projected quality score: 92/100
```

Counts should distinguish test declarations, materializations, invocations and attempts when those dimensions are available.

A decrease in test count is not automatically negative; an increase is not automatically positive. The report emphasizes evidence gained, lost or still missing.

## Evidence Delta

Instead of one magic score, summarize:

- improved evidence;
- unchanged evidence;
- regressed evidence;
- still unknown evidence.

This makes the effect of proposed changes understandable without pretending heterogeneous signals are one number.

## What does green prove?

Every report should end with a bounded claim such as:

```text
Observed
- selected unit and integration evidence passed
- package installed and startup check passed

Not evidenced
- production-like database behavior
- two configured browser targets
- rollback under concurrent writes
```

The purpose is not to make green look stronger. It is to make its meaning explicit.
