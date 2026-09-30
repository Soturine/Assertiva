# Determinism and Evidence Tiers

Assertiva is deterministic-first, not heuristic-free.

Some questions are mechanically answerable: which test ID ran, what commit was tested, which branch arc was covered, which parameter row failed, or which structured error code was emitted. Other questions are semantic: whether an assertion is meaningful, two tests are redundant, or a mock invalidates a business claim.

## Evidence classes

| Class | Meaning | Examples |
| --- | --- | --- |
| E0 RAW | directly observed artifact | runner XML/JSON, coverage file, trace, source, Git diff |
| E1 DETERMINISTIC_DERIVED | reproducible transformation | normalized JUnit result, exact changed files, parsed branch counts |
| E2 DECLARED | project-authoritative metadata/policy | test mapping, release gate policy, requirement link |
| E3 HEURISTIC | fallible rule/statistical signal | smell detector, co-change ranking, similarity cluster |
| E4 INFERRED | semantic/LLM judgment | likely weak oracle, likely redundant behavior, inferred component relation |

## Rules

- E3/E4 may rank, flag, cluster and propose.
- E3/E4 alone must not silently suppress a material test or close a consequential gate.
- E1 is reproducible, not infallible: parsers and mappings can still be incomplete.
- E2 is authoritative only within its declared scope and freshness.
- Graph edges/findings keep class, source, revision and limitations.
- Unknown evidence widens execution or remains UNKNOWN.
- Never fabricate confidence percentages without calibration.

## Deterministic selection

Selection can be deterministic when backed by exact declared mappings, runner-native dependency data, runtime test-to-code maps, project graphs, or explicit dependency closure. When only heuristic impact is available, use it to prioritize, not to prove unaffectedness.

## Semantic audit

Oracle strength and semantic duplication may require inference. Assertiva should explain the evidence and uncertainty instead of pretending these are syntactic facts.
