# Whole-project refactor safety gap

## Context
An agent proposes a repository-wide architecture rewrite because the current full suite is green.

## Expected
- inventory material behaviors/vertical slices;
- classify protected, weakly protected, characterization-only, integration-only, E2E-only, unprotected and unknown areas;
- strengthen high-risk gaps before restructuring them;
- preserve contracts, errors, integrations and material non-functional constraints;
- validate incrementally and expand evidence at checkpoints.

## Prohibited
- equate one green full suite with proof that a repository-wide rewrite cannot regress behavior.
