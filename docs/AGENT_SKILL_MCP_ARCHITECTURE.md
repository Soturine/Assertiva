# Agent Skill, CLI, and MCP Architecture

Assertiva should separate policy, deterministic execution, persistent intelligence and raw evidence.

## Recommended layers

~~~text
Agent / CI / human
      |
   SKILL.md
      |
workflow routing + claim policy
      |
deterministic Assertiva core
      |
CLI -------- optional MCP server
 |                |
runner adapters   persistent graph/history/artifacts/jobs
      \           /
       evidence store
~~~

Implemented today: `SKILL.md`, the deterministic core, the CLI and the runner adapters. An MCP server is not implemented; it is optional and planned for M3 (ROADMAP.md), and the Skill + CLI path is complete without it.

## Skill layer

SKILL.md should stay compact and route to references only when relevant. Stable assurance policy belongs in the skill/core; framework lookup tables and fast-moving version facts belong in adapters/references/research.

Advantages:
- low setup and portable across coding agents;
- progressive disclosure reduces token cost;
- policy remains readable/reviewable.

Disadvantages:
- instructions alone cannot guarantee deterministic discovery/parsing/execution;
- large monolithic skills become context-heavy and drift across providers.

## CLI layer

CLI is the preferred high-throughput interface for local coding agents.

Advantages:
- concise invocations and outputs;
- easy scripting/CI integration;
- avoids loading a large MCP tool schema into context;
- natural fit for raw artifact files.

Disadvantages:
- weaker persistent interactive state unless the CLI uses a project DB/cache;
- shell/environment differences require careful quoting/path/version handling.

## MCP layer

MCP is optional and most valuable for persistent project intelligence, rich artifact retrieval, CI/cloud context, long-running analyses and interactive graph queries.

Advantages:
- structured typed tools;
- persistent server-side state;
- resources can expose artifacts without copying everything into prompts;
- long-running work can use task/job semantics where supported;
- multiple agent clients can share project/run intelligence.

Disadvantages:
- tool schemas and verbose structured results consume context;
- larger attack/input-validation surface;
- server lifecycle/state/version management;
- tool explosion can confuse routing;
- network/auth complexity for remote deployment.

Playwright's current guidance explicitly favors CLI+Skills for token-sensitive coding agents and MCP for stateful exploratory loops. Assertiva should support both rather than making MCP mandatory.

## MCP tool design

Prefer focused atomic tools such as:
- project_capabilities;
- discover_tests;
- normalize_report;
- select_tests;
- run_tests / record_run;
- failure_clusters;
- evidence_get;
- graph_query;
- suite_findings;
- refactor_readiness;
- job_start / job_status / job_cancel for expensive analysis where protocol/client support permits.

Tools should return structured compact data, pagination/cursors for large collections, exact run/revision identity and artifact references.

Do not expose a single 'analyze everything' tool as the only interface.

## Resources/artifacts

Large stdout, traces, coverage maps, screenshots, videos and full graph exports should live as files/resources/artifacts. The model receives compact summaries and asks for slices.

## State store

A local project store (for example SQLite or another embedded store) can maintain:
- source/test identity;
- revision-aware edges;
- test durations/results;
- flakes/retries;
- coverage/test-to-code mappings;
- failure fingerprints;
- adapter/version metadata.

Staleness must be explicit. Every query that depends on cached analysis should know the indexed revision and working-tree status.

## Security

For MCP/CLI:
- validate paths and prevent traversal;
- avoid command injection;
- bind local servers conservatively;
- redact secrets from logs/locals/headers;
- separate read-only from mutating/executing operations;
- bound output and resource use;
- preserve permission and user-approved project commands.

## Skill packaging

If distributed through a modern skill-capable MCP server, Assertiva can publish SKILL.md alongside tools/resources. The core should still remain usable as files + CLI without MCP.


## Product UX boundary

Internal architecture may be rich, but the ordinary user-facing workflow should remain intentionally small:

```text
assertiva audit
assertiva improve
```

`audit` is read-only with respect to project files. It may inspect and run permitted verification, but it cannot mutate the audited project.

`improve` performs the audit first, builds and verifies candidate changes outside the original project, presents evidence, and requests approval before applying anything. Temporary workspaces, Git worktrees, candidate IDs, patch staging and post-apply verification are internal mechanisms rather than extra everyday modes.

This keeps the product aligned with "less is more": simple commands on top of strict runtime guarantees.

## HTML Assurance Report

The report is a first-class interface rather than a terminal afterthought. It is always generated by the engine (never by the Skill), one canonical page per run; its layout and contract are owned by [User Experience and Reporting](USER_EXPERIENCE_AND_REPORTING.md).

It should support:
- baseline/current/candidate/applied states without conflating them;
- test definitions, materializations, invocations and attempts where available;
- pass/fail/error/blocked/skipped/xfail/xpass/not-run outcomes;
- coverage and mutation evidence;
- weak-oracle, smoke, negative-path, validation and fidelity findings;
- Verification Surface and local/CI/build/deploy parity;
- change-set summary;
- Evidence Delta;
- remaining gaps/unknowns;
- a bounded "What does green prove?" statement;
- artifact/provenance links.

Any chart must be accompanied by equivalent readable text/table data (today comparisons are before → after rows), use semantic HTML, support keyboard navigation and remain useful in light/dark themes.

Do not invent a composite quality score merely to make the dashboard look complete.

## Reasoning layer, evidence core, bounded claims

```text
Skill (semantic reasoning, may infer)
        ↓ asks for
deterministic evidence core (CLI/engine/adapters)
        ↓ produces
bounded claims (what green proves, what stays UNKNOWN)
```

The Skill may reason freely, but facts come from evidence: "this oracle looks weak" is an inference to present as such; "419 tests executed" is deterministic evidence. A language model never replaces the deterministic core. Without an installed engine the Skill runs semantic-only; with it, engine-backed (rules in [SKILL.md](../SKILL.md#execution-mode-and-the-engine)). The HTML report is always rendered by the engine.

Each layer is evaluated by its own means: the runtime by deterministic tests, CI and the on-demand runtime self-qualification; the Skill by semantic evaluation with a hidden rubric and a separate judge ([`evals/README.md`](../evals/README.md)). Neither substitutes for the other.
