# Executable Assurance Core

Assertiva is moving from specification-first guidance to a test-driven executable assurance engine.

The central question is not merely **did tests pass?** It is:

> What evidence was actually produced, by which tests, under which harness/environment/artifact, and what claims does that evidence support?

## Scope

Assertiva audits existing test ecosystems directly. Functional Test Designer is optional, not a prerequisite.

The executable model grows around:

```text
repository tests
→ discovery
→ runner configuration
→ CI/CD selection
→ execution/result evidence
→ coverage/oracle/fidelity evidence
→ build/package/deploy evidence
→ findings + limitations
```

## M0.2 vertical slice

Implemented now:

- bounded static pytest definition inventory using Python AST;
- GitHub Actions pytest command/scope discovery;
- repository-test-vs-observed-CI scope comparison;
- coverage.py JSON ingestion for line/branch evidence;
- smoke-dominant and weak-oracle signals;
- high-line-coverage/weak-oracle and line-vs-branch contradiction findings;
- `assertiva audit-pytest` technical-preview CLI.

## TDD rule

Every new capability should begin with an executable fixture/reproduction of a false-green or evidence gap, then implementation.

Current tests cover discovery, CI scope gaps, full-scope pytest, smoke-dominant suites, coverage/oracle mismatch, and missing CI evidence.

## Claim boundary

Static AST inventory is not native pytest collection. It can miss dynamic tests, custom collectors/plugins, runtime parameterization and collection-time behavior.

The GitHub Actions reader is also a bounded command extractor, not a complete YAML/expression interpreter.

Therefore:

```text
static inventory found N tests != pytest would collect exactly N invocations
workflow contains pytest != that job executed successfully in a specific run
```

Findings are evidence records, not a magic quality score.
