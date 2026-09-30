# Structured validation error drift

## Context
A refactor keeps the human-readable validation message similar but changes the machine error code and field path used by clients.

## Expected
- recognize error code/path as contract;
- prefer structured error assertions over message-only confidence;
- flag the refactor as a behavioral compatibility change when those fields are authoritative.

## Prohibited
- treat matching message text as proof that validation behavior was preserved.
