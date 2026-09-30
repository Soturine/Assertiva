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
