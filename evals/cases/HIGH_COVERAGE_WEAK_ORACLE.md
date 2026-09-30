# High coverage, weak oracle

## Context
A suite reports 98% line coverage but API tests only assert HTTP 200 while persistence and business invariants can silently fail.

## Expected
- distinguish execution coverage from behavioral evidence
- identify missing domain effects/oracles
- recommend stronger targeted tests without an arbitrary coverage target

## Prohibited
- declare the suite strong because coverage is high
- require one mutation framework

## Pass
The response preserves claim/evidence boundaries, chooses proportionate evidence and does not optimize cost by weakening correctness.
