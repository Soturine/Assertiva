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

The HTML report is one self-contained, offline page (inline CSS and a small progressive-enhancement script; no CDN, web font, framework or network request). It works without JavaScript; the script adds language and theme switching, filters, copy buttons, the active-section indicator and opening collapsed detail from a link. Rendering lives in `assertiva/report_html.py`; presentation text lives in `assertiva/report_i18n.py` (by stable key) and `assertiva/report_narrative.py` (the engine's own sentence templates). None of them changes the report model.

The page has two layers that show the same truth.

**Layer 1, decision** (`data-layer="decision"`), read in about 30 seconds:

- **Identity and conclusion** — project, revision, workspace state, which states are shown; the conclusion in words with its reason (for example "Needs review: 1 high-priority finding and 6 medium", or "Candidate not ready yet: what blocks review: pipeline-equivalent checks (failed)"); whether there is execution evidence or only static inspection. The raw status enum is a technical detail, and the overall status is never painted as success.
- **Next step** — an existing recommendation, only when the evidence ranks one: a finding whose own recommendation says it comes first (collection errors, failing tests) or a single finding at the highest priority. A tie is reported as a tie with the tied actions listed; it is never broken by guessing. In improve: review the change set when the candidate is ready, otherwise the checks that block review.
- **Confirmed / Needs attention / Not proven** — Confirmed lists only execution or deterministic facts (a run that passed, a verified artifact, no surviving mutant, detected negative controls, passed qualification checks). Heuristic (E3) positives are shown apart as a *positive signal*, never counted as confirmed. The absence of a finding is never a strength. Not proven is the claim boundary's not-evidenced list as short labels.
- **What does green prove?** — in audit, the audit scope: each area (tests, coverage, test quality, negative paths, fault sensitivity, artifact, CI, local hooks, deploy) with its evidence strength — executed / verified, measured / ingested, inspected, declared, not proven — and what was observed, from the model only. In improve, each qualification check from proven to not proven. Limitations are counted and disclosed.
- **Improve story** — whether the candidate is ready, how many metrics improved, regressed, changed contextually, stayed unchanged or are not comparable, and that nothing was applied.
- **Findings** (collapsed rows) — priority in words, human title, why it matters, area, affected count, and links to the evidence and to the fix.
- **Recommendations** — grouped as Do first (the ranked next step), High priority, Important, Optional; each with the action, the full recommendation, why, the finding, the area and what closes it, always marked *Proposed · not applied*.
- **Candidate pillars and evidence delta** (improve) — regressions first, then improvements, contextual changes and not comparable, each as before → after; unchanged metrics collapsed.

**Layer 2, auditability**, behind disclosure: each finding's observation, affected evidence, recommendation, closing condition and technical details (identifier, evidence basis, original text, raw evidence JSON); a summary by domain, then every metric with id, direction, basis and delta; declared checks grouped by origin with full commands; runs; negative paths, mutation, artifact, delivery, selection and history panels; compact provenance with all fields disclosed; the complete claim boundary; remaining unknowns; the execution budget; the canonical JSON.

Charts are not drawn for their own sake: comparisons are before → after rows with the change marked. Status is never conveyed by color alone (icon and text), and the page supports keyboard navigation, light and dark themes and reduced motion, with no horizontal scroll from 1920 px down to phone width.

### Languages

English (canonical) and Brazilian Portuguese, selected in the header, remembered when browser storage is available, otherwise taken from the browser language. Three kinds of text are kept apart:

- **Presentation text** is always localized, by stable key.
- **Assertiva's own narrative** (claim boundary, limitations, qualification summaries, change reasons, dynamic finding summaries) is localized when it matches one of the engine's exact sentence templates; the values inside it (paths, ids, counts, tool output) are kept as written. A contract test scans the engine for every sentence it writes into a report and requires a template, so new sentences cannot leak untranslated.
- **Raw external or technical evidence** (commands, paths, hashes, artifact names, tool and runner messages, sentences with no fixed template) stays as written, marked `lang="en"`, and only in technical detail, never in the decision layer.

Finding codes, metric ids, enums, commands, paths, hashes, revisions and adapter names are never translated. Only the strings a page uses are embedded.

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
