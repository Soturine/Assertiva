# Verification Surface

Assertiva models the complete set of checks that can contribute to confidence or block delivery. A test suite is one part of that surface.

## Core rule

The model is language-, framework-, test-runner-, CI-provider- and project-neutral.

Tool-specific behavior belongs in adapters. Core policy operates on normalized capabilities and evidence, never on a hardcoded project name or framework assumption.

## VerificationCheck

A check can represent, for example:

- tests or E2E suites;
- lint, formatting, static analysis or type checking;
- coverage or mutation evidence;
- build/package/artifact checks;
- schema, generated-code or migration validation;
- localization/i18n validation;
- security/dependency checks;
- pre-commit or other hook/task-runner checks;
- container build, process startup, health/readiness and deploy verification;
- any project-specific command not yet understood by a first-party adapter.

Each check preserves:
- stable check identity;
- kind;
- origin: local, hook, CI, build/package, deploy, declared/observed or unknown;
- gate semantics: blocking, advisory, allowed-failure or unknown;
- command/tool when observed;
- scope;
- source/provenance;
- adapter;
- evidence tier;
- limitations and tool-specific metadata.

## Unknown tooling

Unknown does not mean unsupported project.

If Assertiva observes a command it cannot semantically classify, it should retain it as `CUSTOM` or `UNKNOWN`, preserve the command/source, and state the limitation.

It must not:
- silently drop the check;
- guess that it is a test;
- guess that it is blocking;
- invent framework semantics;
- claim parity because an unknown check was not understood.

## Verification parity

A useful assurance question is:

```text
checks known locally / in hooks / project policy
                    vs
checks actually observed in CI/CD / delivery
```

Missing checks can produce a false-green path even when all executed tests pass.

The reverse matters too: CI may execute additional validators that developers do not run locally, making "local green" materially weaker than "pipeline-equivalent green".

## Adapter principle

```text
native tool/project syntax
        ↓
adapter
        ↓
VerificationCheck + evidence
        ↓
generic Assertiva policy
```

Adapters can be written for any ecosystem. Portable formats and generic command preservation provide fallback when there is no first-party adapter.

## Support claim

Assertiva aims to be universal at the **model and extension architecture** level. Concrete native support is incremental and must be reported honestly. "Framework-neutral" must never be used to imply that every framework is already deeply understood.
