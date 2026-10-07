# Determinism and Evidence Tiers

Assertiva separates two questions that are easy to conflate:

- **Provenance — how do we know?** Observed, declared, inferred or unknown.
- **Importance — how much does it matter?** The consequence for the assurance question being asked.

They are independent. "599 tests executed" can be deterministically perfect and say little about oracle strength; "these tests mock exactly the boundary they claim to prove" is an inference and can be the most important conclusion of an audit. Provenance decides how a claim is labeled and what may be built on it; it never decides its priority.

## Provenance classes

The engine records a tier on metrics and findings; the Skill and the report speak in the four user-facing classes.

| Class | Tier | Meaning | Examples |
| --- | --- | --- | --- |
| OBSERVED | E0 RAW | directly observed artifact | runner XML/JSON, coverage file, trace, source, Git diff, a command's output |
| OBSERVED | E1 DETERMINISTIC_DERIVED | reproducible transformation of observed artifacts | normalized results, exact changed files, parsed branch counts |
| DECLARED | E2 DECLARED | project-authoritative metadata or configuration | CI workflow, build plugin binding, requirement link |
| INFERRED | E3 HEURISTIC | fallible rule or statistical signal | static weak-oracle signal, co-change ranking, similarity cluster |
| INFERRED | E4 INFERRED | reasoned judgment from cited evidence | a mock hides the boundary under test; an untested recovery state |
| UNKNOWN | — | nothing available settles it | whether CI ran on this revision without run identity |

## Rules

- Never move a claim to a stronger class silently: an inference is not an execution, a declaration is not a run, a static count is not a collected test.
- E1 is reproducible, not infallible: parsers and mappings can be incomplete. E2 is authoritative only within its declared scope and freshness.
- Heuristic or inferred impact may rank and widen a test selection; it never narrows one, never suppresses a material test and never closes a qualification gate.
- An inference is a first-class finding when it cites the evidence it rests on; the auditing agent records it in an assessment (`assertiva audit --assessment`), next to engine evidence, never as engine output.
- Unknown evidence widens execution or stays UNKNOWN. Never fabricate confidence percentages without calibration.

## Deterministic selection

Selection can be deterministic when backed by exact declared mappings, runner-native dependency data, runtime test-to-code maps, project graphs, or explicit dependency closure. When only heuristic impact is available, use it to prioritize, not to prove unaffectedness.
