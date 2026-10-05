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

## Modules

The core is small and tool-neutral; tool knowledge lives in `assertiva/adapters/`.

| Module | Owns |
| --- | --- |
| `workspace.py` | fingerprints, baseline, isolated candidate (worktree/copy), change set, approved apply, read-only guard, Assertiva-owned state location |
| `evidence.py` | measuring one state in a disposable copy, negative controls, direction-aware metrics and state comparison |
| `improve.py` | improve session and qualification stages |
| `audit.py` | read-only audit over runner adapters and the Verification Surface |
| `report.py` | the single Assurance Report model and its HTML rendering |
| `verification.py` | VerificationCheck/Surface and generic local-vs-delivery parity findings |
| `candidate.py`, `models.py` | stage/metric/change and runner-evidence records |
| `adapters/pytest_native.py` | native pytest collection/execution, coverage, static signals, CI-check reproduction |
| `adapters/github_actions.py`, `adapters/pre_commit.py`, `adapters/commands.py` | declared CI steps, hooks and command classification |

Adapter protocol, by capability: runner adapters expose `supports`, `run`/`collect`, `static_signals`, `static_audit` and `reproduction_args(check)`; surface adapters expose `supports` and `discover`. The core never branches on a tool name.

## TDD rule

Every new capability should begin with an executable fixture/reproduction of a false-green or evidence gap, then implementation.

Adversarial fixtures include a test that writes into its working directory (audit must stay read-only), a candidate that breaks production code and weakens the test to match (original regression must fail), a negative control the baseline suite cannot detect, stale baselines, hook checks absent from CI and CI-only validators.

## Claim boundary

Static AST inventory is not native pytest collection. It can miss dynamic tests, custom collectors/plugins, runtime parameterization and collection-time behavior.

The GitHub Actions reader is also a bounded command extractor, not a complete YAML/expression interpreter.

Therefore:

```text
static inventory found N tests != pytest would collect exactly N invocations
workflow contains pytest != that job executed successfully in a specific run
```

Findings are evidence records, not a magic quality score.
