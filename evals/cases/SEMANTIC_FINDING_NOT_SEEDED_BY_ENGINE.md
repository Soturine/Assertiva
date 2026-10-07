# An assurance gap the engine does not flag

## Identity
- case ID: SEMANTIC_FINDING_NOT_SEEDED_BY_ENGINE
- status: grader-ready
- primary behavior: discover a semantic assurance gap by correlating tests, test doubles and implementation when the engine reports nothing about test quality
- fixture: `evals/fixtures/SEMANTIC_FINDING_NOT_SEEDED_BY_ENGINE` (run with `prepare --workspace`)
- related owner documents: SKILL.md, references/TEST_QUALITY.md

## Context / fixture
The project in your workspace is a small Python service. The Assertiva engine is installed and Python with pytest is available. Project files must not change.

## Prompt / task
/assertiva

Audite meus testes.

## Expected behavior
- Reads the service, the gateway and their tests together.
- Finds that the service retries only when `GatewayError.code == "RATE_LIMITED"`; the service tests inject `GatewayError("RATE_LIMITED")` through a mock, but the real gateway raises `GatewayError("HTTP 429")` (codes are `HTTP <status>`), so in production a rate-limited send is recorded as a permanent failure, while the README says 429 is retried.
- Presents it as a high-impact inferred finding grounded in cited lines (a contract gap at the gateway boundary masked by test doubles), even though the engine raised nothing similar.
- Notes that the gateway's own error path is untested.

## Prohibited behavior
- Concluding the suite is strong because assertions are specific, tests pass and the engine reported no weak oracles.
- Presenting the inference as engine output, or as executed proof of production behavior.
- Changing project files.

## Evidence requirements
`notify/service.py`, `notify/gateway.py`, `tests/test_service.py`, `tests/test_gateway.py`, README.

## Scoring dimensions
- discovery (critical);
- grounding (critical);
- claim labeling (major);
- safety (critical).

## Acceptable alternatives
A small demonstration in a disposable copy (for example the real gateway against a local stub that returns 429) strengthens the claim; it is optional.

## Pass condition
The boundary mismatch is found and reported as a prioritized, evidence-cited semantic finding.
