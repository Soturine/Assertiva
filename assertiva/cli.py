from __future__ import annotations

import argparse
import json
from dataclasses import asdict
from pathlib import Path

from .pytest_audit import audit_pytest_project, has_pytest_surface


def _pytest_payload(report):
    return {
        "root": str(report.root),
        "adapter_scope": ["pytest-static", "github-actions-pytest"],
        "tests": [asdict(item) for item in report.tests],
        "materializations": [asdict(item) for item in report.materializations],
        "ci_invocations": [asdict(item) for item in report.ci_invocations],
        "coverage": asdict(report.coverage) if report.coverage else None,
        "findings": [asdict(item) for item in report.findings],
        "summary": {
            "direct_test_definitions": len(report.tests),
            "static_materializations": len(report.materializations),
            "expected_error_tests": report.expected_error_count,
            "smoke_like": report.smoke_like_count,
            "smoke_ratio": report.smoke_ratio,
            "finding_count": len(report.findings),
        },
        "limitations": [
            "static pytest inventory is not native runner collection",
            "GitHub Actions parsing is bounded and does not evaluate all workflow indirection",
        ],
    }


def _run_pytest_audit(root: Path, coverage_json: str | None, output: str) -> int:
    report = audit_pytest_project(root, coverage_json)
    payload = _pytest_payload(report)
    if output == "json":
        print(json.dumps(payload, indent=2, sort_keys=True))
        return 0

    print(f"Assertiva audit: {len(report.tests)} direct pytest test definitions")
    print(f"Static inherited/composed materializations: {len(report.materializations)}")
    print(f"Expected-error contracts observed: {report.expected_error_count}")
    print(f"Observed GitHub Actions pytest invocations: {len(report.ci_invocations)}")
    for finding in report.findings:
        print(f"[{finding.code}] {finding.summary}")
    if not report.findings:
        print("No findings from this bounded adapter set. This is not a full regression-confidence claim.")
    return 0


def _run_audit(args: argparse.Namespace) -> int:
    root = Path(args.root)
    if has_pytest_surface(root):
        return _run_pytest_audit(root, args.coverage_json, args.output)

    payload = {
        "root": str(root),
        "status": "UNKNOWN",
        "adapter_scope": [],
        "findings": [
            {
                "code": "NO_EXECUTABLE_TEST_ADAPTER_RECOGNIZED",
                "summary": "No currently executable first-party test adapter recognized this project. Assertiva does not infer that the project has zero tests.",
                "evidence": {},
            }
        ],
        "limitations": [
            "generic Verification Surface discovery is specified but not yet fully executable",
            "additional runner/framework adapters are roadmap work",
        ],
    }
    if args.output == "json":
        print(json.dumps(payload, indent=2, sort_keys=True))
    else:
        print("Assertiva audit: UNKNOWN")
        print("[NO_EXECUTABLE_TEST_ADAPTER_RECOGNIZED] No current executable test adapter recognized this project.")
        print("The project is not reported as having zero tests.")
    return 0


def _add_audit_args(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("root", nargs="?", default=".")
    parser.add_argument("--coverage-json")
    parser.add_argument("--output", choices=("text", "json"), default="text")


def main() -> int:
    parser = argparse.ArgumentParser(prog="assertiva", description="Adaptive Test Intelligence & Assurance")
    sub = parser.add_subparsers(dest="command", required=True)

    audit = sub.add_parser("audit", help="Read-only assurance audit using available executable adapters")
    _add_audit_args(audit)
    audit.set_defaults(handler=_run_audit)

    legacy = sub.add_parser("audit-pytest", help=argparse.SUPPRESS)
    _add_audit_args(legacy)
    legacy.set_defaults(
        handler=lambda args: _run_pytest_audit(Path(args.root), args.coverage_json, args.output)
    )

    args = parser.parse_args()
    return args.handler(args)


if __name__ == "__main__":
    raise SystemExit(main())
