# Status

## Current milestone: M0

State: usable specification-first Agent Skill with small deterministic utilities.

### Implemented
- canonical SKILL.md;
- architecture and evidence model;
- AUDIT / SELECT / RUN / DIAGNOSE / VERIFY semantics;
- progressive diagnostics D0–D4;
- Test Evidence Graph semantics;
- E2E decomposition and selector blind-spot rules;
- token-aware evidence contract;
- benchmark/research record;
- human-readable eval cases;
- schemas/examples;
- JUnit XML compact summarizer;
- repository/spec validator;
- deterministic utility tests and CI.

### Specified, not implemented
- universal test discovery;
- static/runtime Test Impact Analysis engine;
- automatic dependency/Test Evidence Graph builder;
- cross-run history and flake/runtime model;
- mutation orchestration;
- pytest/Jest/Vitest/Playwright/JUnit/Gradle/.NET adapters;
- automatic E2E stage mapping;
- CLI/MCP server;
- executable multi-agent benchmark harness.

### Claim boundary
Assertiva can guide a capable coding agent now. It does not yet guarantee deterministic cross-language test selection or universal automated auditing.
