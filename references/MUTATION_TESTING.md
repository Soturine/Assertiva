# Mutation Testing

Mutation testing intentionally changes production code and checks whether tests detect the change.

Useful outcomes include killed, survived, no coverage, and tool-specific timeout/error/equivalent states.

## Good uses
- boundaries;
- conditionals;
- arithmetic/comparison logic;
- critical domain rules;
- regression hardening;
- cases where line coverage is high but oracle strength is uncertain.

## Limits
A survivor may be equivalent, unreachable or irrelevant to the material claim. Interpret rather than blindly optimize a score.

Use targeted mutation when a full campaign is too expensive.
