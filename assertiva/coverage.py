from __future__ import annotations

import json
from pathlib import Path

from .models import CoverageSummary


def _percent(covered, total):
    if covered is None or total in (None, 0):
        return None
    return round(float(covered) * 100.0 / float(total), 4)


def load_coverage_json(path: str | Path) -> CoverageSummary:
    report_path = Path(path)
    data = json.loads(report_path.read_text(encoding="utf-8"))
    totals = data.get("totals", {})
    line = totals.get("percent_covered")
    if line is None:
        line = _percent(totals.get("covered_lines"), totals.get("num_statements"))
    branch = totals.get("percent_covered_branches")
    if branch is None:
        branch = _percent(totals.get("covered_branches"), totals.get("num_branches"))
    return CoverageSummary(
        line_percent=float(line) if line is not None else None,
        branch_percent=float(branch) if branch is not None else None,
        source=str(report_path),
    )
