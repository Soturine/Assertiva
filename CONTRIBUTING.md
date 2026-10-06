# Contributing

Keep Assertiva provider-neutral and evidence-driven.

Before adding a rule or integration:
1. identify the failure mode/problem;
2. determine whether it is reusable;
3. separate stable semantics from mutable tool behavior;
4. keep mutable versions/tool facts in dated research/adapters;
5. add or update an eval for consequential behavioral changes;
6. do not claim executable capability without implementation and tests.

## Validation levels

Validate in proportion to the change: targeted tests for the code touched and the fast suite (`pytest -m "not integration and not artifact"`) while developing; the full suite (`pytest -n auto`) at block gates; the full self-dogfood (CI `workflow_dispatch` or a `v*` tag) when closing a milestone or changing how qualification itself works.

CI tool versions are pinned in `constraints.txt`; bump them deliberately in their own commit.

## Main branch

Recommended (not configured by tooling, it is an owner decision): protect `main` by requiring the `validate` and `Python 3.11 compatibility` checks. Direct pushes by the owner keep working unless admins are included in the rule.
