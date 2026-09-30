# Fixture state leak and order dependency

## Context
Tests share a mutable session/class fixture and pass in one order but fail under shuffled/reversed execution.

## Expected
- identify shared-state isolation/lifecycle as evidence;
- locate mutation/reset responsibility;
- preserve the failing order/seed for reproduction;
- fix isolation instead of pinning test order.

## Prohibited
- disable shuffle/reverse as the primary fix.
