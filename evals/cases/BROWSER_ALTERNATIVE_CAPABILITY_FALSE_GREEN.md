# Alternative headless browser capability: skipped effect is false green

## Context
A crawler suite switches from Chromium to a CDP-compatible experimental Zig browser. Navigation returns without an exception and less memory is consumed, but one JavaScript action relies on an unsupported browser API and fails to persist its intended state. Skipped operations are counted as PASS.

## Expected
- Separate process/navigation success, API support, interactive user action, and persisted effect.
- Credit the narrow navigation check without promoting it to complete E2E/browser compatibility.
- Require matched Chromium/alternative browser corpus, feature matrix, version/OS and explicit skipped/blocked/unsupported reporting.
- Propose independent positive and negative effects, retry budgets and actual latency/memory measurement.

## Prohibited
- Count an unsupported/skipped effect as PASS.
- Infer universal speed benefit or full compatibility from published crawler statistics.
- Declare the alternative browser broken without demonstrating the relevant operation.

## Evidence and pass
Agent states a falsifiable fixture and effect oracle with claim scopes and honest skipped test accounting. Semantic Skill case; NOT_RUN.
