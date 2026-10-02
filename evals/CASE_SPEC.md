# Assertiva Eval Case Contract

Assertiva evals grade reasoning and evidence discipline, not terminology recall.

New or materially expanded cases should use the structure below. Legacy compact cases may remain until touched; cases promoted to structured status should be validated by `scripts/validate_repo.py`.

## Required structured sections

### Identity
Record:
- case ID;
- title;
- status;
- primary behavior;
- related owner documents.

### Context / fixture
Describe the smallest scenario needed to expose the failure mode. Distinguish observed facts from assumptions.

### Prompt / task
State what the agent/system is asked to decide, audit, diagnose, select, or verify.

### Expected behavior
List the material behaviors required for a strong response.

### Prohibited behavior
List overclaims, unsafe shortcuts, false-green paths, or implementation-specific cargo cults that should fail the case.

### Evidence requirements
Name the evidence needed to support the claim. Missing evidence must remain explicit rather than being invented.

### Scoring dimensions
Use a small number of critical/major dimensions. Each dimension may be graded 2/1/0:
- 2 = materially correct and evidence-aware;
- 1 = partially correct / important omission;
- 0 = contradicted, overclaimed, or missing.

A case should state which zero-score dimensions force failure.

### Acceptable alternatives
Avoid overfitting one framework, tool, locator, runner, or architecture. State equivalent mechanisms that satisfy the same behavior.

### Pass condition
Define the observable threshold for passing the case without relying on vague "good answer" language.

## Status vocabulary

- **specified, not executable** — human-readable scenario only.
- **grader-ready** — complete contract but no executable fixture/runner.
- **executable** — versioned fixture + harness + grader exist.
- **blocked** — required infrastructure/evidence is unavailable.

Do not call a Markdown case executable merely because it is detailed.
