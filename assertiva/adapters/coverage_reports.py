"""Portable coverage reports: coverage.py JSON, istanbul json-summary, LCOV, Cobertura XML, JaCoCo XML.

Numerators and denominators are kept per kind (line, branch, function/method, instruction...)
whenever the format has them; a report with rates only says its denominators are unknown.
"""

from __future__ import annotations

import json
import re
import xml.etree.ElementTree as ET
from pathlib import Path

from assertiva.models import CoverageSummary

_ISTANBUL = {"lines": "line", "branches": "branch", "functions": "function", "statements": "statement"}
_JACOCO = {"LINE": "line", "BRANCH": "branch", "INSTRUCTION": "instruction", "METHOD": "method", "COMPLEXITY": "complexity", "CLASS": "class"}
_LCOV = {"LF": ("line", "total"), "LH": ("line", "covered"), "BRF": ("branch", "total"), "BRH": ("branch", "covered"),
         "FNF": ("function", "total"), "FNH": ("function", "covered")}


_TEST_DIRS = {"tests", "test", "__tests__", "spec", "specs", "androidtest", "testfixtures", "integrationtest"}
_TEST_NAME = re.compile(r"(^test_.*\.py$|_test\.(py|go)$|\.(test|spec)\.[cm]?[jt]sx?$|Tests?\.(java|kt)$|^conftest\.py$)", re.I)


def is_test_path(path: str) -> bool:
    """Whether a covered file is test code (by conventional directory or file name), not product code."""
    parts = [p for p in str(path).replace("\\", "/").split("/") if p]
    return bool(parts) and (any(p.lower() in _TEST_DIRS for p in parts[:-1]) or bool(_TEST_NAME.search(parts[-1])))


def _per_file(per_file: dict[str, dict[str, dict[str, int]]]) -> dict:
    """Product counts (test files left out) and file counts, from per-file numbers."""
    product: dict[str, dict[str, int]] = {}
    tests = 0
    for name, kinds in per_file.items():
        if is_test_path(name):
            tests += 1
            continue
        for kind, count in kinds.items():
            bucket = product.setdefault(kind, {"covered": 0, "total": 0})
            bucket["covered"] += count["covered"]
            bucket["total"] += count["total"]
    return {"product_counts": product, "files": len(per_file), "test_files": tests}


def _summary(path: Path, tool: str, counts: dict, line=None, branch=None, limitations=(), per_file=None) -> CoverageSummary:
    summary = CoverageSummary(line_percent=line, branch_percent=branch, source=str(path), counts=counts, tool=tool,
                              limitations=tuple(limitations))
    extra = _per_file(per_file) if per_file else {}
    if not per_file:
        limitations = (*limitations, "the report has no per-file numbers: coverage of product code apart from test code is unknown")
    return CoverageSummary(line_percent=summary.percent("line"), branch_percent=summary.percent("branch"),
                           source=str(path), counts=counts, tool=tool, limitations=tuple(limitations), **extra)


def _coverage_py(path: Path, data: dict) -> CoverageSummary:
    totals = data["totals"]
    counts = {}
    if "num_statements" in totals:
        counts["line"] = {"covered": int(totals["covered_lines"]), "total": int(totals["num_statements"])}
    if "num_branches" in totals:
        counts["branch"] = {"covered": int(totals["covered_branches"]), "total": int(totals["num_branches"])}
    line = totals.get("percent_covered") if "line" not in counts else None
    per_file = {}
    for name, entry in (data.get("files") or {}).items():
        s = entry.get("summary") or {}
        per_file[name] = {k: {"covered": int(s[c]), "total": int(s[t])} for k, c, t in
                          (("line", "covered_lines", "num_statements"), ("branch", "covered_branches", "num_branches")) if t in s}
    return _summary(path, "coverage.py", counts, line=line, per_file=per_file)


def _istanbul(path: Path, data: dict) -> CoverageSummary:
    counts = {kind: {"covered": int(data["total"][key]["covered"]), "total": int(data["total"][key]["total"])}
              for key, kind in _ISTANBUL.items() if key in data["total"]}
    per_file = {name: {kind: {"covered": int(entry[key]["covered"]), "total": int(entry[key]["total"])}
                       for key, kind in _ISTANBUL.items() if key in entry}
                for name, entry in data.items() if name != "total" and isinstance(entry, dict)}
    return _summary(path, "istanbul", counts, per_file=per_file)


def _lcov(path: Path, text: str) -> CoverageSummary:
    counts: dict[str, dict[str, int]] = {}
    per_file: dict[str, dict[str, dict[str, int]]] = {}
    current = None
    lines_found = lines_hit = 0
    saw_lf = False
    for raw in text.splitlines():
        key, _, value = raw.strip().partition(":")
        if key == "SF":
            current = per_file.setdefault(value, {})
        if key in _LCOV:
            kind, field_name = _LCOV[key]
            counts.setdefault(kind, {"covered": 0, "total": 0})[field_name] += int(value)
            if current is not None:
                current.setdefault(kind, {"covered": 0, "total": 0})[field_name] += int(value)
            saw_lf = saw_lf or key == "LF"
        elif key == "DA":
            lines_found += 1
            lines_hit += int(value.split(",")[1]) > 0
    if not saw_lf and lines_found:
        counts["line"] = {"covered": lines_hit, "total": lines_found}
    if not counts:
        raise ValueError("no LCOV totals found")
    return _summary(path, "lcov", counts, per_file=per_file if saw_lf else None)


def _cobertura(path: Path, root: ET.Element) -> CoverageSummary:
    counts, limitations = {}, []
    for kind, covered, total in (("line", "lines-covered", "lines-valid"), ("branch", "branches-covered", "branches-valid")):
        if root.get(covered) is not None and root.get(total) is not None:
            counts[kind] = {"covered": int(root.get(covered)), "total": int(root.get(total))}
    line = branch = None
    if not counts:
        line = float(root.get("line-rate")) * 100 if root.get("line-rate") is not None else None
        branch = float(root.get("branch-rate")) * 100 if root.get("branch-rate") is not None else None
        limitations.append("the Cobertura report has rates but no counts: its denominators are unknown")
    return _summary(path, "cobertura", counts, line=line, branch=branch, limitations=limitations)


def _jacoco(path: Path, root: ET.Element) -> CoverageSummary:
    counts = {
        _JACOCO[counter.get("type")]: {"covered": int(counter.get("covered")), "total": int(counter.get("covered")) + int(counter.get("missed"))}
        for counter in root.findall("counter") if counter.get("type") in _JACOCO
    }
    if not counts:
        raise ValueError("no report-level JaCoCo counters")
    per_file = {}
    for package in root.iter("package"):
        for source in package.findall("sourcefile"):
            name = f"{package.get('name', '')}/{source.get('name', '')}"
            per_file[name] = {_JACOCO[c.get("type")]: {"covered": int(c.get("covered")), "total": int(c.get("covered")) + int(c.get("missed"))}
                              for c in source.findall("counter") if c.get("type") in _JACOCO}
    return _summary(path, "jacoco", counts, per_file=per_file)


def load_coverage_report(path: str | Path) -> CoverageSummary:
    """Detect the format and normalize; unreadable or unknown reports carry an error, never numbers."""
    path = Path(path)
    try:
        text = path.read_text(encoding="utf-8")
        stripped = text.lstrip()
        if stripped.startswith("<"):
            root = ET.fromstring(stripped)
            if root.tag == "coverage":
                return _cobertura(path, root)
            if root.tag == "report":
                return _jacoco(path, root)
            raise ValueError(f"unsupported XML coverage report <{root.tag}>")
        if stripped.startswith("{"):
            data = json.loads(text)
            if isinstance(data.get("totals"), dict):
                return _coverage_py(path, data)
            if isinstance(data.get("total"), dict):
                return _istanbul(path, data)
            raise ValueError("unsupported JSON coverage report")
        if "SF:" in text or "end_of_record" in text:
            return _lcov(path, text)
        raise ValueError("unsupported coverage report format")
    except (OSError, ValueError, KeyError, TypeError, IndexError, ET.ParseError) as exc:
        return CoverageSummary(source=str(path), error=f"{type(exc).__name__}: {exc}"[:300])
