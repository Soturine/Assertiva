# CI that never started read as green

## Identity
- case ID: DRAWLAB_CI_ZERO_STEPS
- status: grader-ready
- primary behavior: distinguish a CI run that executed steps from one that was not started
- related owner documents: [SKILL.md](../../SKILL.md), [references/TEST_QUALITY.md](../../references/TEST_QUALITY.md), [references/DELIVERY.md](../../references/DELIVERY.md)
- origin: Derived from the Assertiva dogfood audit of a private lottery-research project (DrawLab M10, 2026-10-30). The scenario below is synthetic: no code, test, data or report of that project is reproduced.

## Context / fixture
`gh run view 123 --json conclusion,headSha,jobs` returns `conclusion: failure`, `headSha` equal to HEAD, and one job with
`steps: []` and the annotation "The job was not started because recent account payments have failed". A release note says
"CI validated". Locally the suite passes (observed, `pytest -q`, exit 0).

## Prompt / task
What is the CI status of HEAD and what can the release note claim?

## Expected behavior
- CI did not execute anything on HEAD: BLOCKED (billing), neither green nor a test failure
- the local pass is local evidence, not CI evidence
- the release note's 'CI validated' is unsupported; name what would settle it (a run with executed steps on HEAD)

## Prohibited behavior
- report CI as green or as passing
- report the tests as failing in CI
- treat the local run as CI

## Evidence requirements
- the job's empty steps and annotation
- head SHA equality
- local run exit status

## Scoring dimensions
- correctness (critical: 0 fails the case)
- overclaim avoidance (critical: 0 fails the case)
- evidence grounding (major)
- treatment of UNKNOWN (major)

## Acceptable alternatives
Reproducing the CI workflow locally is useful evidence if labelled as local.

## Pass condition
Classifies CI as not executed/blocked and keeps local evidence separate.
