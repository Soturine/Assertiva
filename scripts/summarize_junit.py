#!/usr/bin/env python3
"""Compact JUnit XML summary for agent context (uses Assertiva's JUnit adapter)."""
import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from assertiva.adapters.junit import load_junit  # noqa: E402
from assertiva.models import Outcome  # noqa: E402


def summarize(path: Path):
    run = load_junit(path)
    failing = [inv for inv in run.invocations if inv.outcome in (Outcome.FAILED, Outcome.ERROR)]
    return {
        'status': run.status.value,
        'executed': len(run.invocations),
        'passed': sum(inv.outcome is Outcome.PASSED for inv in run.invocations),
        'failed': len(failing),
        'skipped': sum(inv.outcome is Outcome.SKIPPED for inv in run.invocations),
        'duration_seconds': run.wall_clock_s or 0.0,
        'failures': [
            {'id': inv.invocation_id, 'status': inv.outcome.value.lower(), 'time': inv.duration_s, 'detail': inv.message}
            for inv in failing
        ],
        'limitations': run.limitations,
    }


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('junit_xml')
    ap.add_argument('--pretty', action='store_true')
    args = ap.parse_args()
    print(json.dumps(summarize(Path(args.junit_xml)), indent=2 if args.pretty else None, ensure_ascii=False))


if __name__ == '__main__':
    main()
