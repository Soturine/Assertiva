# Test Composition, Inheritance, and Materialization

Test source code and executed tests are not always one-to-one.

Assertiva uses a framework-neutral composition model so mixins, base classes, interfaces/default methods, traits/modules, shared-test factories, generic fixtures and generated suites can be represented without hardcoding one language.

## Identity

```text
declaration
    ↓
materialization
    ↓
invocation / parameter / matrix case
    ↓
attempt / retry
```

A shared declaration can materialize into many concrete suites. A derived suite can also override the shared test and suppress one materialization.

Do not collapse these layers into one count.

## Relations

Useful relations include:
- INHERITS_FROM;
- COMPOSES;
- MATERIALIZES_IN;
- OVERRIDES;
- EXTENDS;
- PARAMETERIZES;
- GENERATES.

## Why it matters

Composition affects:
- inventory completeness;
- duplicate/redundancy analysis;
- oracle independence;
- setup/fixture provenance;
- change-impact selection;
- failure localization;
- platform/type/configuration matrix coverage.

Many materialized tests from one shared declaration are not automatically duplicates. They may exercise different implementations or configurations. Preserve shared provenance before judging distinct evidence.

## Lifecycle composition

Inherited setup/teardown, fixtures, shared contexts and helper layers can change a test without changing its body. Impact analysis should traverse those dependencies too.

## Authority

Static composition analysis is useful for provenance and impact, but native runner collection is authoritative for the concrete runnable set when available.

Static analysis must not invent framework-specific precedence, MRO, trait resolution, plugin behavior or runtime-generated classes it cannot prove.

## Current executable slice

The Python reference adapter can detect bounded same-file inherited test materializations and overrides. Cross-module inheritance, plugins, metaclasses, generated classes and full native collection remain roadmap work.
