# Agent Testing Skills and MCP Architecture Benchmark — 2026-09-30

Status: dated research evidence. This compares architecture, not product rankings.

## Chisel

Repo: https://github.com/IronAdamant/Chisel

Structure observed:
- compact agent SKILL.md;
- CLI plus HTTP/stdio MCP around one engine;
- JSON tool schemas/dispatch separated from transport;
- persistent per-project SQLite analysis;
- source/test/import/Git relations, incremental updates and result history;
- explicit heuristic trust order and dynamic-code blind-spot warnings;
- benchmark/tests across several languages.

Advantages:
- real executable impact intelligence;
- stateful graph/history;
- CLI and MCP offer different integration surfaces;
- staleness/working-tree concerns are surfaced.

Disadvantages/limits for Assertiva:
- primarily impact/risk intelligence rather than complete semantic test assurance;
- dynamic/reflection/runtime relationships remain blind spots;
- ranked/heuristic edges require claim limits;
- persistent analysis introduces cache/index lifecycle complexity.

Adopt: split core engine from CLI/MCP, persistent revision-aware store, explicit evidence source/trust, long-analysis jobs, compact SKILL.md.

## dotnet/skills and TestFX test skills

Repo: https://github.com/dotnet/skills and microsoft/testfx ecosystem.

Structure observed:
- orchestrator agents plus focused skills for assertion quality, gap analysis, smells, anti-patterns, coverage, test execution, generation and migration;
- per-language extension files act as lookup data for discovery/assertion/setup/tag syntax;
- fixture-based eval directories and rubric/output graders;
- experimental mock analysis traces setups through production execution paths.

Advantages:
- strong modularity and activation boundaries;
- polyglot semantics separated from framework lookup tables;
- rich eval fixtures including good/weak calibration cases;
- dedicated assertion and behavior-gap analysis.

Disadvantages/risks:
- many small skills increase routing/discovery complexity;
- some modules retain ecosystem-specific bias;
- assertion diversity or smell metrics can become vanity scores if detached from behavior/claim;
- audit modules do not by themselves solve adaptive execution, E2E localization or persistent evidence history.

Adopt: extensions as data, focused analysis modules, fixture-based adversarial evals, production-code tracing for mock/gap findings. Avoid arbitrary score worship.

## Cypress AI Toolkit

Repo: https://github.com/cypress-io/ai-toolkit

Structure observed:
- separate author, explain, docs, tap and cloud-cli skills;
- author routes task -> subskill -> reference rules;
- tap skill controls a live session and uses strict fresh-verdict identity, bounded polling, reporter/command drill-down and small context reads;
- large JSON is redirected to files rather than injected wholesale.

Advantages:
- excellent progressive disclosure;
- authoring and execution/debugging responsibilities are separate;
- precise live-run freshness protocol prevents stale-result false confidence;
- version and session capability checks are explicit.

Disadvantages:
- vendor/runtime-specific;
- live session state adds lifecycle complexity;
- detailed procedural rules can be brittle across versions.

Adopt: fresh-run identity, bounded polling, artifact-first large payloads, task routing, version-aware capabilities.

## Android official skills

Repo: https://github.com/android/skills

Structure observed:
- narrow skills target fast-moving areas with reference trees;
- testing setup skill explicitly inventories JUnit, DI, mocking, Robolectric, Compose/Views, screenshots, instrumented tests and E2E;
- guidance distinguishes fake/mock/device/runtime fidelity.

Advantages:
- deep domain calibration and progressive references;
- avoids teaching everything when the model already knows stable concepts.

Disadvantages:
- fast-moving framework defaults need maintenance;
- opinionated library choices should not become cross-project policy.

Adopt: capability discovery and load domain/version references only when needed.

## Playwright CLI and MCP

Sources:
- https://github.com/microsoft/playwright-mcp
- https://github.com/microsoft/playwright-cli

Current guidance explicitly distinguishes CLI+Skills as token-efficient for coding agents from MCP as useful for persistent exploratory state.

Advantages of CLI:
- compact context;
- simple scripting/CI;
- easy file artifacts.

Advantages of MCP:
- typed tools;
- persistent browser/project state;
- rich interactive exploration.

Tradeoff: MCP schemas/snapshots cost tokens and server lifecycle/security complexity.

Adopt: CLI-first for routine local coding; optional MCP for persistent graph/history/artifact queries and long agentic loops.

## Anthropic skill-creator and MCP-builder patterns

Repo: https://github.com/anthropics/skills

Observed patterns:
- SKILL.md + scripts + references with progressive disclosure;
- deterministic/repetitive operations moved to scripts;
- with-skill vs baseline eval loops measure pass quality, tokens and time;
- MCP guidance emphasizes atomic focused tools, precise schemas, pagination, input validation, transport choice and security.

Adopt: keep Assertiva SKILL compact, benchmark against baselines, deterministic scripts for parsing, atomic MCP tools, pagination and resource/artifact references.

## Current MCP direction

Sources:
- https://skills.extensions.modelcontextprotocol.io/specification/stable/skills
- https://tasks.extensions.modelcontextprotocol.io/specification/draft/tasks

The 2026-07-28 MCP ecosystem supports publishing skills alongside tools/resources/prompts through the skills extension. The tasks extension defines durable/pollable long-running work.

Assertiva should not require these extensions for basic operation, but can use them when clients support them.

## Recommended Assertiva composition

~~~text
SKILL.md: policy + routing
references/docs: domain and framework semantics
deterministic core: discovery/parsing/normalization/selection primitives
CLI: default coding-agent interface
MCP: optional persistent graph/history/artifact/job interface
adapters: capability translation
project store: revision-aware evidence/history
eval fixtures: adversarial cross-stack behavior
~~~

The key differentiator remains composition of suite quality + impact + evidence + failure localization + refactor confidence + cost/context management, not copying any single tool.
