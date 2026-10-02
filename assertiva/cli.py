from __future__ import annotations

import argparse
import json
from dataclasses import asdict
from pathlib import Path

from .pytest_audit import audit_pytest_project


def main() -> int:
    parser = argparse.ArgumentParser(prog="assertiva", description="Adaptive Test Intelligence & Assurance")
    sub = parser.add_subparsers(dest="command", required=True)
    audit = sub.add_parser("audit-pytest", help="Audit pytest evidence and observed GitHub Actions scope")
    audit.add_argument("root", nargs="?", default=".")
    audit.add_argument("--coverage-json")
    audit.add_argument("--output", choices=("text","json"), default="text")
    args = parser.parse_args()

    report = audit_pytest_project(Path(args.root), args.coverage_json)
    payload = {
        "root": str(report.root),
        "tests": [asdict(x) for x in report.tests],
        "ci_invocations": [asdict(x) for x in report.ci_invocations],
        "coverage": asdict(report.coverage) if report.coverage else None,
        "findings": [asdict(x) for x in report.findings],
        "summary": {"test_definitions": len(report.tests), "smoke_like": report.smoke_like_count, "smoke_ratio": report.smoke_ratio, "finding_count": len(report.findings)},
    }
    if args.output == "json":
        print(json.dumps(payload, indent=2, sort_keys=True))
    else:
        print(f"Assertiva pytest assurance: {len(report.tests)} test definitions")
        print(f"Observed GitHub Actions pytest invocations: {len(report.ci_invocations)}")
        for f in report.findings:
            print(f"[{f.code}] {f.summary}")
        if not report.findings:
            print("No findings from this bounded audit. This is not a full regression-confidence claim.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
