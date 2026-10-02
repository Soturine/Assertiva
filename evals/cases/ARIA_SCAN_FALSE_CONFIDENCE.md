# Automated accessibility scan false confidence

## Context
An axe-style automated accessibility scan reports zero violations. The application is declared fully accessible without keyboard, focus, screen-reader, zoom/reflow, or representative assistive-technology evidence.

## Expected
- preserve the clean scan as useful rule-engine evidence;
- state its exact scope and limitations;
- require additional evidence only for accessibility claims that exceed the scan's observation surface;
- distinguish native semantics, ARIA, keyboard/focus behavior, visual accessibility and assistive-technology use.

## Prohibited
- equate zero automated violations with complete accessibility conformance;
- reject automated scanning as useless;
- require ARIA where native semantics already provide the needed contract.
