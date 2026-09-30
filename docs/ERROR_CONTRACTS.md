# Error and Validation Contracts

Invalid input and failure behavior are part of the product contract.

## Portable error model

Where observable, normalize:
- category/domain;
- concrete type/class;
- stable machine code;
- path/location/field;
- HTTP/RPC/protocol status;
- context/constraint parameters;
- sanitized offending input or input class;
- message policy;
- nested/multiple errors;
- cause/chain when material.

## Assertion guidance

Prefer stable semantic fields over brittle message-only equality unless exact wording/localization is itself required.

Test:
- correct error for each invalid class;
- boundary vs invalid distinction;
- nested field/path attribution;
- multiple simultaneous violations when supported;
- precedence when several validators could fail;
- strict/coercion behavior;
- serialization/API mapping;
- no sensitive-data leakage.

## Framework examples

Pydantic ValidationError is one adapter-specific form with structured error details. Equivalent concepts exist in validation frameworks, API problem formats, GraphQL errors, typed Result/Error values and domain exceptions.

Core policy must not depend on Pydantic.

## Error changes during refactor

Changing error class, code, path, status, or serialization can be a breaking behavioral change even when success-path output is identical.
