# Delivery, selection, diagnosis and refactor safety

## Contents
- Verification surface
- CI and revision provenance
- Local vs pipeline parity and matrices
- Built artifacts
- Test selection
- Flaky and unstable tests
- Diagnosing failures
- Refactor safety
- Keeping evidence compact

## Verification surface

Everything that can block or influence delivery counts: tests, lint, type and static checks, schema/generated-code checks, migrations, i18n checks, security scans, build/package/container/startup/health checks, hooks and custom project commands. For each: does it exist, where does it run (local, hook, CI, release), is it gating or advisory, which paths/markers/projects does it exclude, and what does it actually prove? A repository containing a check does not mean the delivery path runs it. Unknown commands stay unknown until something classifies them.

## CI and revision provenance

- Workflow files are declared evidence: they say what *should* run, not what did.
- A step's status is its shell's: a pipeline (`pytest | tee log`) returns its last command's status unless `pipefail` is set (GitHub Actions' default `bash -e` has none; `shell: bash` adds it), and grepping a log for "passed" is not a result. Read the runner's own summary or exit code before trusting a green step.
- A CI run proves a revision only when its identity is confirmed — its head SHA equals `git rev-parse HEAD`, or an equally explicit link. Otherwise say "CI green observed; correspondence to HEAD unknown". A dirty working tree is proven by no run.
- When the provider is reachable (for example `gh run list --json headSha,conclusion,name`), checking for a run on HEAD is cheaper than a full local run that only tells you whether HEAD is green. A local run still adds evidence when the question needs per-test outcomes, coverage or a different environment; say what it adds.
- Expressions, conditions, reusable workflows, includes and branch protection are not evaluated from configuration: whether a conditional job ran or gates merges stays unknown without run evidence.

To tie a provider run to the audited revision, export it with the user's provider access and pass it with `--ci-run`: for GitHub, `gh run list --commit "$(git rev-parse HEAD)" --json databaseId` then `gh run view <id> --json headSha,conclusion,jobs,url,workflowName`; for GitLab, the pipeline and its jobs from the API for that SHA. Only `SAME_REVISION` on a clean tree proves that revision.

## Local vs pipeline parity and matrices

Compare what runs locally with what CI runs: commands, filters, markers, environment variables (a skip condition that holds in CI too means the tests never run anywhere), runtime and OS versions. A runtime declared as supported (`requires-python`, `engines.node`, compiler release, browser projects) but selected by no CI job is untested. Reproducing one matrix cell locally is partial evidence; reproducing a CI step locally is not pipeline equivalence.

## Built artifacts

Source-tree tests do not prove the built and installed artifact. Missing package data, undeclared dependencies and imports that resolve to the source tree instead of the installed package are common gaps. Lineage — this source revision built these bytes, these bytes were tested, these bytes were published — holds only as far as evidence goes.

## Test selection

- Choose tests from the strongest available mapping: declared mappings, runtime test-to-code maps, import/fixture graphs, then heuristics.
- Exact or deterministic mappings may exclude tests only within their proven scope; heuristic impact prioritizes, never proves "unaffected". Unknown relations, configuration and shared fixtures widen the selection.
- A green selected set proves the selected tests at that revision, never the full suite or a release gate.

## Flaky and unstable tests

Retries classify instability; they do not erase the first failure. One vocabulary: observed unstable in this run (failed and passed), historically flaky (same revision and environment, several failures and a pass), consistent failure, environment-specific, no instability observed (not proof of stability), insufficient evidence. A single failure is not "flaky".

## Diagnosing failures

1. Identify the failing check and the first divergent stage.
2. Cluster failures that share a cause (identical fingerprints first).
3. Find the smallest useful reproducer; descend from E2E only when a lower layer reproduces the same failure. Do not rerun an expensive E2E blindly.
4. Escalate diagnostics only as needed: summary → failure → context → trace → forensic. Verbosity flags are not portable across runners.
5. Classify: product defect, test/oracle defect, environment or infrastructure, data, flake, or unresolved.

After a fix: rerun the reproducer, then affected dependents and regression, then the relevant integration/E2E evidence, then broader gates when risk or release policy requires them.

## Refactor safety

The question is whether a meaningful unintended behavior change in the refactored scope would be detected. Establish the authoritative behavior, then map important behaviors and contracts to unit/property/characterization, integration/contract, E2E and non-functional evidence. Classify the target READY, READY_WITH_GAPS, NOT_READY or UNKNOWN; for whole-project refactors, classify behavior slices as protected, weakly protected, characterization-only, integration-only, E2E-only, unprotected or unknown. A green suite or 100% line coverage does not make a refactor safe. Never weaken an expectation to make a refactor pass.

## Keeping evidence compact

Prefer structured summaries with references to the raw artifacts over pasting output into context. Never save tokens by hiding failures, skips, retries, limitations, environment, revision, fidelity, contradictions or unknowns. Keep secrets and environment values out of the context unless they are the subject.
