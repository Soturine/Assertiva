# User Experience and Reporting

Assertiva exposes two user-facing workflows:

```text
assertiva audit
assertiva improve
```

Everything else is internal orchestration, adapter behavior, or an advanced implementation detail.

## Audit

`audit` inspects the project, executes only permitted verification work, measures evidence and reports gaps. It never changes project files.

The command's exit code reports whether Assertiva ran, not whether the audited tests passed: 0 means it completed and reported (an audit of a failing suite exits 0), 2 a refusal or misuse, 3 a read-only violation. The verdict is in the report.

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

Candidate qualification includes **test-the-tests**: the candidate suite is challenged with available mutation/negative-control evidence, original regression evidence, coverage/oracle analysis, pipeline-equivalent checks and build/artifact evidence. Preview deployment is specified but not executable today: it appears as not evidenced, and production is never used.

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

## Report artifact contract

One run produces one canonical page.

| Command | Written to the report directory |
|---|---|
| `assertiva audit <project>` | `audit.html` and `audit.json` |
| `assertiva improve <project>` (qualification) | `improve.html` and `improve.json` |
| `assertiva improve <project> --approve ...` | `improve.html` and `improve.json`, now including the applied state |

- Baseline, candidate and applied are states inside the same `improve.html`; they are never separate pages.
- The default report directory is `<ASSERTIVA_HOME>/reports/<project>-<hash>/`, outside the project; `--report-dir` chooses another directory outside the project. A new run replaces the page of the same workflow there; it never adds a second page for the same run.
- The execution trace is written separately and referenced from the report's provenance.
- Each HTML is self-contained and offline: CSS and the progressive-enhancement script are embedded; there is no CDN, font, framework or network request, and the page is useful with JavaScript disabled.
- A future history or bundle can lay runs out as `reports/<project>/<run-id>/audit.html` and add an optional `index.html`; nothing in a single run depends on more than one page.
- Several pages appear only when several independent runs are rendered (for example the dogfood scenarios: static audit, executed audit, improve, edge cases).

Provenance identifies the producer: `assertiva_version` is the version of the code that ran (read from the source checkout when running from one, so a stale editable install cannot misreport it), and `runtime` records the install kind and, for a checkout, its git revision and whether it had local changes. The page also states which Assertiva rendered it; when evidence produced by one version is rendered by another, the page says so.

## Visual contract

Rendering lives in `assertiva/report_html.py`; presentation text lives in `assertiva/report_i18n.py` (by stable key) and `assertiva/report_narrative.py` (the engine's own sentence templates). None of them changes the report model. The page answers one question: *can this green be trusted, why, where can it not, and what should be done now?*

**Layer 1, decision** (`data-layer="decision"`):

- **Identity** — project, revision, workspace state, when it was generated (shown in the browser's local time; the UTC timestamp stays in technical details), and for improve which states are shown.
- **Decision surface** — one panel with the conclusion and its reason as counts (for example *Needs review · 8 findings: 1 high, 6 medium, 1 informational*, or *Candidate not ready yet · what blocks review: pipeline-equivalent checks (blocked)*), whether tests were executed or only inspected, and an integrated **next step** rail: what to do, why, which finding it comes from and what would prove it resolved. The next step exists only when the evidence ranks one; a tie is listed as a tie. Nothing is changed automatically.
- **What was examined** (audit) — every area with its kind of evidence; **candidate lifecycle** (improve) — baseline, candidate, review, approval, applied, post-apply check, each shown done only with its evidence, so a candidate never reads as applied.
- **Confirmed / Needs attention / Not proven** — Confirmed holds execution or deterministic facts only; heuristic positives are shown apart as signals; the absence of a finding is never a strength.
- **What does green prove?** — the audit scope as a ledger, or each qualification check from failed to proven. Evidence strength is a *kind*, not a scale: ✓ executed / verified, ◐ measured / ingested, ◇ inspected, ○ declared, ? not proven, ✕ failed — always icon and label, never colour alone.
- **Findings** — compact rows (priority, title, why it matters, area, affected count, evidence basis in words with the E-tier as metadata); informational findings are more compact. Expanding shows what was observed, the affected evidence, the proposed fix, how to prove it resolved and technical details.
- **Recommendations** — an action plan: Do first, High priority, Important, Optional; each row shows the action, the reason and the priority, and expands to the full recommendation, the finding, the area, the closing criterion and its state (proposed → applied → verified).
- **Improve** — pillars ordered with failures first and open; the delta with regressions first, then improvements, contextual changes, not comparable, and unchanged metrics collapsed.

**Layer 2, auditability** (denser): an evidence snapshot by domain, then every metric, declared check, run, negative path, mutation report, artifact, delivery, selection and history panel behind disclosure; compact provenance with all fields disclosed; the complete claim boundary grouped by domain with counts; remaining unknowns; the execution budget; the canonical JSON. Long raw blocks are bounded with *show complete*; commands and the JSON have copy buttons.

A changed coverage denominator is shown next to the percentage it qualifies. Filters on findings are visible, clearable and kept in the URL. The page supports keyboard navigation, focus-visible, skip link, light and dark themes, reduced motion and print (interactive controls hidden, every collapsed detail opened), and is checked from 1920 px down to 390 px.

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
