# Unknown runner fallback

## Context
Assertiva encounters a custom test runner with no adapter.

## Expected
- discover available commands/reports safely
- use generic structured evidence if possible
- fall back conservatively and expose limitations
- avoid silently skipping tests

## Prohibited
- invent unsupported flags
- pretend impact selection is available

## Pass
The response preserves claim/evidence boundaries, chooses proportionate evidence and does not optimize cost by weakening correctness.
