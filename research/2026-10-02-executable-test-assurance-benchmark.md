# Executable Test Assurance Benchmark — 2026-10-02

Dated research that informed M0.2.

## TestSprite 2.1 / current CLI

TestSprite 2.1 emphasized autonomous agentic testing, GitHub integration, editable/rerunnable steps and MCP stability. The current public CLI is agent-first and treats structured output/exit behavior as a contract while hosted services own generation/execution.

Lesson for Assertiva: keep the skill thin and move reproducible behavior into an executable runtime.

Sources:
- https://www.testsprite.com/blog/introducing-testsprite-2-1-autonomous-agentic-testing-for-ai-native-teams
- https://www.testsprite.com/changelog
- https://github.com/TestSprite/testsprite-cli

## Playwright Test Agents

Planner → generator → healer is a useful decomposition. Assertiva adds a stricter rule: repair execution mechanics, never silently rewrite an authoritative oracle.

Source: https://playwright.dev/docs/test-agents

## Chisel

Chisel is a strong benchmark for incremental code/test graphs, working-tree impact analysis, CLI+MCP, local SQLite history, compact skills and conservative fallback/widening.

Assertiva's scope is broader: oracle strength, harness fidelity, false-green CI/CD analysis, failure diagnosis and verification.

Source: https://github.com/IronAdamant/Chisel

## pytest / coverage.py

Native pytest evidence such as collect-only, skip/xfail, markers, filters and JUnit XML is the next adapter step. coverage.py JSON is preferable to scraping terminal prose and line/branch metrics must remain distinct.

Sources:
- https://docs.pytest.org/
- https://coverage.readthedocs.io/

## Mutation testing

mutmut, Stryker and PIT are useful test-the-test evidence. Assertiva should normalize their outcomes before inventing a mutation engine of its own.

Sources:
- https://mutmut.readthedocs.io/
- https://stryker-mutator.io/
- https://pitest.org/

## Architecture decision

```text
TDD adversarial fixture
→ deterministic adapter/parser
→ evidence record
→ bounded finding
→ explicit limitation
→ expand only after the vertical slice is trustworthy
```
