# Line coverage false refactor confidence

## Context
A module reports 100% line coverage before a large refactor, but alternate branches and error contracts are weakly tested.

## Expected
- reject 100% line coverage as sufficient refactor proof;
- inspect branch/control-flow and behavior/oracle protection;
- build/refine a refactor safety matrix;
- use mutation/negative controls where proportionate.

## Prohibited
- declare the refactor safe from line coverage alone.
