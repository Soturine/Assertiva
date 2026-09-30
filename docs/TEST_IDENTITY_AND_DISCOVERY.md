# Test Identity and Discovery

## Identity hierarchy

A portable model separates:

~~~text
suite
 -> test definition
     -> invocation / data case
         -> attempt / retry
             -> result
~~~

Examples of invocations include parameter rows, theories, table-driven cases, generated/dynamic tests, property runs and device/browser matrix cases.

## Stable identity

Prefer runner-native stable IDs. Preserve display name separately from machine identity.

An invocation record may include:
- definition_id;
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

Unknown runners must not be silently treated as having zero tests.

## Dynamic tests

Some tests are only fully enumerable at runtime. Mark discovery as PARTIAL/DYNAMIC and preserve the executed invocation set. Do not claim repository-wide inventory completeness from static files alone.
