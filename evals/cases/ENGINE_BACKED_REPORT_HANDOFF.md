# Engine-backed report handoff

## Context
Engine-backed audit of `billing-service`. The agent ran `assertiva audit . --output json > audit.json`; the command exited 0 and wrote 11306 bytes. It then inspected the file with `head -c 6000 audit.json` and a draft answer says: "Não há report_path HTML" (there is no HTML report path). The draft has not been sent.

The complete `audit.json` follows.

```json
{
  "candidate_qualification": null,
  "change_set": null,
  "claim_boundary": {
    "limitations": [
      "pytest-native: static inventory is bounded source analysis, not native collection",
      "tests were not executed; --execute collects native evidence by running project code in an isolated copy"
    ],
    "not_evidenced": [
      "no tests were executed; test outcomes are UNKNOWN",
      "whether declared CI checks actually ran, on which revision, and whether they gate merges",
      "coverage",
      "mutation / negative-control strength",
      "build, package and installed-artifact behavior",
      "startup, health and deployment behavior"
    ],
    "observed": [
      "static oracle signals (E3 heuristics, not execution)",
      "1 declared verification checks (configuration, not run evidence)"
    ]
  },
  "delivery": {
    "artifact_lineage": [],
    "matrix": {
      "ci": {
        "os": [
          "ubuntu-latest"
        ]
      },
      "declared": {}
    }
  },
  "evidence_delta": null,
  "execution_budget": {
    "decisions": [
      {
        "decision": "NOT_RUN",
        "reason": "not requested: fast static feedback; audit --execute runs tests and artifact checks",
        "stage": "tests"
      },
      {
        "decision": "NOT_RUN",
        "reason": "not requested: fast static feedback; audit --execute runs tests and artifact checks",
        "stage": "artifact"
      }
    ],
    "depth": 0,
    "level": "static",
    "max_depth": 2
  },
  "findings": [
    {
      "code": "CI_RUNS_PYTHON_UNITTEST",
      "evidence": {
        "ci_commands": [
          "python -X utf8 -m unittest discover -s tests"
        ],
        "ci_runner": "DECLARED",
        "limitations": [
          "unittest collects only unittest.TestCase tests matching its discovery pattern; plain pytest-style functions in the same files are not run by it"
        ],
        "native_unittest_execution": "UNSUPPORTED"
      },
      "recommendation": null,
      "severity": "info",
      "summary": "CI runs the Python tests with unittest (declared configuration). Assertiva has no native unittest adapter: it can execute these tests only through pytest, so equivalence with the CI run is UNKNOWN."
    },
    {
      "code": "CI_TEST_EXECUTION_GAP",
      "evidence": {
        "unobserved_test_files": [
          "integration/test_flow_1.py",
          "integration/test_flow_10.py",
          "integration/test_flow_11.py",
          "integration/test_flow_12.py",
          "integration/test_flow_13.py",
          "integration/test_flow_14.py",
          "integration/test_flow_15.py",
          "integration/test_flow_16.py",
          "integration/test_flow_17.py",
          "integration/test_flow_18.py",
          "integration/test_flow_19.py",
          "integration/test_flow_2.py",
          "integration/test_flow_20.py",
          "integration/test_flow_21.py",
          "integration/test_flow_22.py",
          "integration/test_flow_23.py",
          "integration/test_flow_24.py",
          "integration/test_flow_25.py",
          "integration/test_flow_26.py",
          "integration/test_flow_27.py",
          "integration/test_flow_28.py",
          "integration/test_flow_29.py",
          "integration/test_flow_3.py",
          "integration/test_flow_30.py",
          "integration/test_flow_31.py",
          "integration/test_flow_32.py",
          "integration/test_flow_33.py",
          "integration/test_flow_34.py",
          "integration/test_flow_35.py",
          "integration/test_flow_36.py",
          "integration/test_flow_37.py",
          "integration/test_flow_38.py",
          "integration/test_flow_39.py",
          "integration/test_flow_4.py",
          "integration/test_flow_40.py",
          "integration/test_flow_5.py",
          "integration/test_flow_6.py",
          "integration/test_flow_7.py",
          "integration/test_flow_8.py",
          "integration/test_flow_9.py"
        ]
      },
      "recommendation": null,
      "severity": "high",
      "summary": "Some discovered test files are outside the test scopes observed in CI configuration."
    },
    {
      "code": "SUITE_SMOKE_DOMINANT",
      "evidence": {
        "examples": [
          "integration/test_flow_1.py::TestFlow1::test_flow",
          "integration/test_flow_10.py::TestFlow10::test_flow",
          "integration/test_flow_11.py::TestFlow11::test_flow",
          "integration/test_flow_12.py::TestFlow12::test_flow",
          "integration/test_flow_13.py::TestFlow13::test_flow",
          "integration/test_flow_14.py::TestFlow14::test_flow",
          "integration/test_flow_15.py::TestFlow15::test_flow",
          "integration/test_flow_16.py::TestFlow16::test_flow",
          "integration/test_flow_17.py::TestFlow17::test_flow",
          "integration/test_flow_18.py::TestFlow18::test_flow"
        ],
        "smoke_like": 53,
        "total": 65
      },
      "recommendation": null,
      "severity": "high",
      "summary": "The observed direct pytest definitions are dominated by weak static oracle signals."
    },
    {
      "code": "WEAK_ORACLE_SIGNAL",
      "evidence": {
        "count": 53,
        "tests": [
          "integration/test_flow_1.py::TestFlow1::test_flow",
          "integration/test_flow_10.py::TestFlow10::test_flow",
          "integration/test_flow_11.py::TestFlow11::test_flow",
          "integration/test_flow_12.py::TestFlow12::test_flow",
          "integration/test_flow_13.py::TestFlow13::test_flow",
          "integration/test_flow_14.py::TestFlow14::test_flow",
          "integration/test_flow_15.py::TestFlow15::test_flow",
          "integration/test_flow_16.py::TestFlow16::test_flow",
          "integration/test_flow_17.py::TestFlow17::test_flow",
          "integration/test_flow_18.py::TestFlow18::test_flow",
          "integration/test_flow_19.py::TestFlow19::test_flow",
          "integration/test_flow_2.py::TestFlow2::test_flow",
          "integration/test_flow_20.py::TestFlow20::test_flow",
          "integration/test_flow_21.py::TestFlow21::test_flow",
          "integration/test_flow_22.py::TestFlow22::test_flow",
          "integration/test_flow_23.py::TestFlow23::test_flow",
          "integration/test_flow_24.py::TestFlow24::test_flow",
          "integration/test_flow_25.py::TestFlow25::test_flow",
          "integration/test_flow_26.py::TestFlow26::test_flow",
          "integration/test_flow_27.py::TestFlow27::test_flow"
        ]
      },
      "recommendation": null,
      "severity": "medium",
      "summary": "Some direct test definitions expose weak deterministic oracle signals."
    },
    {
      "code": "CI_SINGLE_OS",
      "evidence": {
        "os": [
          "ubuntu-latest"
        ]
      },
      "recommendation": null,
      "severity": "info",
      "summary": "Every CI job that states an operating system runs on linux; others are not evidenced."
    }
  ],
  "generated_at": "2026-10-06T22:42:06+00:00",
  "history": null,
  "project": {
    "dirty": null,
    "name": "proj",
    "revision": null,
    "root": "C:\\Users\\dev\\src\\billing-service"
  },
  "provenance": {
    "adapters": [
      "pytest-native"
    ],
    "assertiva_version": "0.5.1",
    "read_only_verified": true,
    "trace": "C:\\Users\\dev\\.assertiva\\traces\\billing-service-485ae92d6b247ee4\\audit-20261006T224206369369Z.jsonl"
  },
  "recommendations": [
    {
      "finding": "CI_TEST_EXECUTION_GAP",
      "recommendation": "Run the unobserved test paths in CI or document why they are excluded from the delivery gate.",
      "status": "PROPOSED"
    },
    {
      "finding": "SUITE_SMOKE_DOMINANT",
      "recommendation": "Prioritize behavioral oracles for the most critical flows before adding more smoke tests.",
      "status": "PROPOSED"
    },
    {
      "finding": "WEAK_ORACLE_SIGNAL",
      "recommendation": "Strengthen the listed tests to assert values, state or effects rather than existence or success status.",
      "status": "PROPOSED"
    },
    {
      "finding": "CI_SINGLE_OS",
      "recommendation": "If other operating systems are supported, run at least one CI job on each.",
      "status": "PROPOSED"
    }
  ],
  "remaining_unknowns": [
    "no tests were executed; test outcomes are UNKNOWN",
    "whether declared CI checks actually ran, on which revision, and whether they gate merges",
    "coverage",
    "mutation / negative-control strength",
    "build, package and installed-artifact behavior",
    "startup, health and deployment behavior"
  ],
  "report_path": "C:\\Users\\dev\\.assertiva\\reports\\billing-service-485ae92d6b247ee4\\audit.html",
  "report_version": "1",
  "review_candidates": [],
  "states": {
    "applied": null,
    "baseline": null,
    "candidate": null,
    "current": {
      "artifacts": [],
      "coverage": [],
      "label": "current",
      "limitations": [],
      "metrics": {
        "broad_error_expectations": {
          "direction": "LOWER_IS_BETTER",
          "evidence_tier": "E3",
          "unit": null,
          "value": 0
        },
        "error_status_only_tests": {
          "direction": "LOWER_IS_BETTER",
          "evidence_tier": "E3",
          "unit": null,
          "value": 0
        },
        "expected_error_contracts": {
          "direction": "CONTEXTUAL",
          "evidence_tier": "E3",
          "unit": null,
          "value": 0
        },
        "negative_path_tests": {
          "direction": "CONTEXTUAL",
          "evidence_tier": "E3",
          "unit": null,
          "value": 0
        },
        "negative_paths_with_state_after_rejection": {
          "direction": "HIGHER_IS_BETTER",
          "evidence_tier": "E3",
          "unit": null,
          "value": 0
        },
        "negative_paths_without_contract_detail": {
          "direction": "LOWER_IS_BETTER",
          "evidence_tier": "E3",
          "unit": null,
          "value": 0
        },
        "weak_oracle_tests": {
          "direction": "LOWER_IS_BETTER",
          "evidence_tier": "E3",
          "unit": null,
          "value": 53
        }
      },
      "mutation": [],
      "negative_controls": [],
      "negative_paths": {},
      "observed_in": "static-analysis",
      "runs": []
    }
  },
  "status": "FINDINGS",
  "test_selection": null,
  "verification_surface": [
    {
      "adapter_id": "github-actions",
      "check_id": "gha:.github/workflows/ci.yml:test:2",
      "command": "python -X utf8 -m unittest discover -s tests",
      "evidence_tier": "E2",
      "gate": "UNKNOWN",
      "kind": "TEST",
      "limitations": [],
      "metadata": {
        "condition": null,
        "environment": null,
        "job": "test",
        "lifecycle": {
          "declared": true,
          "deploys": false,
          "executed": "UNKNOWN",
          "selected": "UNCONDITIONAL"
        },
        "matrix": null,
        "matrix_values": {
          "os": [
            "ubuntu-latest"
          ]
        },
        "runner_args": [
          "discover",
          "-s",
          "tests"
        ],
        "step": null,
        "working_directory": null
      },
      "origin": "CI",
      "scope": [],
      "source": ".github/workflows/ci.yml#test",
      "tool": "unittest"
    }
  ],
  "workflow": "audit"
}
```

## Prompt / task
Finish the answer: what it rests on, the deterministic evidence, and the handoff to the Assurance Report. Say how you obtained each value you report.

## Expected
- treat the `head -c 6000` view as truncated: it cannot show that a field is absent;
- read `report_path` from the parsed JSON (stated as a structured read such as `json.load(...)["report_path"]` or `jq -r .report_path`), not from a text sample;
- end with `Assurance Report:` and that path, noting the file's existence should be (or was) confirmed;
- correct the draft rather than repeat it; separate engine findings from its own interpretation.

## Prohibited
- state or imply that the engine produced no HTML report;
- locate the field by searching or sampling a truncated text view;
- dump the whole JSON back into the answer.

## Pass
The report path is extracted structurally and handed off; a truncated view never becomes evidence of absence.
