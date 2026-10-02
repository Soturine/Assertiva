# Test Identity and Discovery

## Identity hierarchy

A portable model separates declaration, materialization, invocation and attempt:

~~~text
suite
 -> test declaration / definition
     -> materialization / composed concrete test
         -> invocation / data / matrix case
             -> attempt / retry
                 -> result
~~~

A direct test may have no separate materialization record. Composition becomes explicit when inheritance, interfaces, traits, mixins, shared-test factories, generic fixtures or generated suites create concrete runnable tests from shared declarations.

## Why materialization matters

Source declaration count is not the same as runner-visible test count.

One shared declaration can materialize into many concrete suites. A derived suite can also override a shared test and suppress an inherited materialization. The concrete cases may be valuable because they exercise different implementations, configurations, platforms or types, but they do not automatically represent independent oracle logic.

Preserve:
- declaration identity and source;
- concrete materialization identity/context;
- relation such as INHERITS_FROM, COMPOSES, MATERIALIZES_IN, OVERRIDES, PARAMETERIZES or GENERATES;
- invocation/data/matrix identity;
- attempt/retry identity.

## Stable identity

Prefer runner-native stable IDs. Preserve display name separately from machine identity.

An invocation record may include:
- definition_id;
- materialization_id when composition exists;
- invocation_id;
- parameter_case_id or normalized parameter hash;
- display_name;
- source location;
- runner/framework;
- matrix/environment dimensions;
- dynamic/generated flag;
- discovery stage;
- attempt number.

Sensitive parameter values should be redacted while preserving a stable non-secret case identity.

## Discovery

Preferred order:
1. runner-native list/collect/discovery API;
2. structured report from an authoritative prior/current run;
3. project-declared manifest;
4. deterministic static adapter parsing;
5. heuristic/LLM discovery only as advisory.

Static inheritance/composition analysis is useful for provenance and impact, but native collection remains authoritative for what actually materializes.

Unknown runners must not be silently treated as having zero tests.

## Dynamic tests

Some tests are only fully enumerable at runtime. Mark discovery as PARTIAL/DYNAMIC and preserve the executed invocation set. Do not claim repository-wide inventory completeness from static files alone.

## Lifecycle inheritance

Setup/teardown, fixtures, shared context and inherited lifecycle hooks can change a materialized test without changing its test body. Impact analysis must therefore include lifecycle/composition dependencies, not only the file that contains the assertion.
