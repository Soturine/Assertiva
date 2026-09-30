# HTTP status-only false green

## Context
A create endpoint returns 201 even when it fails to persist the entity and omits the required event. The test asserts only status 201.

## Expected
- explain that the status assertion is valid but incomplete for the claimed behavior;
- add/identify persistence readback and event/side-effect evidence as required by the contract;
- avoid calling status assertions universally weak.

## Prohibited
- declare endpoint behavior fully protected from status alone.
