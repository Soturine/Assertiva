# Test Impact Analysis and Selection

## Objective
Select the smallest reasonable evidence set for the current claim, not the smallest possible number of tests.

## Evidence sources
1. direct test path/symbol mapping;
2. static dependency/import graph;
3. runtime coverage/test-to-code map;
4. project/monorepo dependency graph;
5. contract/critical-journey relation;
6. Git history/co-change/failure history;
7. known regression ownership;
8. semantic analysis.

Combining independent sources can improve recall.

## Impact graph (implemented, M2)

`assertiva/impact.py` holds a tool-neutral graph. An edge reads "`source` may be affected when `target` changes" and carries source, target, relation, revision, evidence tier, provenance, limitations and (only when a tool reports one) confidence.

- Tiers: E0 runtime coverage mapping; E1/E2 relationships declared by a framework or the project; E3 static imports/dependencies; E4 heuristic inference, which may add work but is never a fact.
- Relations: IMPORTS, COVERS, DECLARES, MATERIALIZES, DEPENDS_ON_FIXTURE, USES_HELPER, USES_CONFIG, USES_ARTIFACT, TESTS.
- Revision-scoped: the revision is the content digest of the analyzed tree (the Git commit is kept as provenance). A graph refuses questions about another revision, and edges observed at another revision are kept aside, never used.
- Unprovable relations are unknowns, not edges: computed dynamic imports, unparseable files. Unresolved references are kept so a deleted or renamed file can still be traced to the files that referred to it.
- First slice, Python: imports resolved to project files (root, `src` layout, pytest's rootdir-less base directory, relative imports, parent packages, literal dynamic imports), `conftest.py` scope and pytest configuration files (E1), static declarations, base-test materialization and test helpers (E3), coverage.py dynamic contexts (E0), `test_<module>.py` naming (E4).

## Selection (implemented, M2)

`assertiva audit --changed-since REV` (no new command) reads the changes since `REV` (committed, staged, unstaged, untracked; renames kept), builds the impact graph of the working tree and selects; with `--execute` only the selected set runs and the report says it is a selected-set claim.

- A change selects the tests with a proven path to it (E0–E3); a changed test always runs; files that referred to a deleted or renamed file select their tests; known failures can be forced in.
- Widening: shared fixture/hook files widen to their scope; framework/project/build configuration, changes no adapter maps, changes with no proven path, a stale graph, unreadable changes and "nothing changed" widen to the full suite. Tests that reach an unknown relation are always added.
- E4 heuristics add tests but never narrow a run: a change related to tests only heuristically widens to the full suite.
- Confidence is a category, not a number: `PROVEN_PATHS` (every change mapped, no unknown reachable), `BOUNDED_BY_UNKNOWNS` (never complete), `FULL_SUITE`.
- Every selected test carries its reason, weakest evidence tier and proof path; every unselected test says why; widening triggers, unknown dependencies and the fallback are recorded.
- Runners select through an optional adapter capability; a runner that cannot select runs its full suite and the report says so.

## Selector output
Include selected tests, reasons, source/method, known blind spots, confidence category, and expansion triggers. Do not use fake precision unless confidence is calibrated.

## Blind spots
Be conservative around reflection, dynamic dispatch, plugins, generated code, config/flags, migrations, shared fixtures, dependency upgrades, global state, external systems, build tooling, concurrency/timing, and indirect assets/templates.

## Default execution order
1. known reproducer/failed test;
2. cheap direct affected unit/component/contract;
3. affected integrations;
4. affected E2E/critical journeys;
5. broader/full gate.

Risk and project policy can change the order.

## Claim boundary
Selected-set green means only that selected tests passed under the recorded revision/environment/configuration. It does not prove full-suite success, release qualification, selector completeness, or test quality.
