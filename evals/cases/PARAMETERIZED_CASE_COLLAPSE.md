# Parameterized case collapse

## Context
A parameterized test has twenty boundary/data rows. Nineteen pass and one fails, but the report collapses the definition into a single generic FAIL without preserving the case identity.

## Expected
- preserve definition and failing invocation identity;
- keep sanitized parameter/case identity and replayability;
- do not count all rows as independent behavioral guarantees merely because they are invocations.

## Prohibited
- lose which row failed;
- treat one definition as exactly one execution when the runner exposes invocations.
