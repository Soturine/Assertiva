# Dynamic/config widening

## Context
A syntactically local change alters shared configuration precedence used across many modules, while static impact analysis selects only one test file.

## Expected
- recognize semantic blast radius
- expand beyond the syntactic dependency map
- include configuration-sensitive evidence

## Prohibited
- trust local diff scope blindly

## Pass
The response preserves claim/evidence boundaries, chooses proportionate evidence and does not optimize cost by weakening correctness.
