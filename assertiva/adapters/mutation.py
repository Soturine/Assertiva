"""Mutation-tool report adapters. Assertiva ingests existing tools; it is not a mutation engine.

Supported (see research/2026-10-05-mutation-report-formats.md):
- mutation-testing-elements JSON (Stryker family and other producers of that schema): per mutant;
- PIT ``mutations.xml``: per mutant;
- mutmut ``mutmut-cicd-stats.json``: aggregate counts only.
Cosmic Ray's ``cr-xml`` is deliberately unsupported: it cannot distinguish pending from killed.
"""

from __future__ import annotations

import json
import xml.etree.ElementTree as ET
from collections import Counter
from pathlib import Path

from assertiva.models import MutantRecord, MutantStatus as S, MutationRun

_MTE = {
    "Killed": S.KILLED, "Survived": S.SURVIVED, "NoCoverage": S.NO_COVERAGE, "Timeout": S.TIMEOUT,
    "CompileError": S.ERROR, "RuntimeError": S.ERROR, "Ignored": S.IGNORED,
}
_PIT = {
    "KILLED": S.KILLED, "SURVIVED": S.SURVIVED, "NO_COVERAGE": S.NO_COVERAGE, "TIMED_OUT": S.TIMEOUT,
    "MEMORY_ERROR": S.ERROR, "RUN_ERROR": S.ERROR, "NON_VIABLE": S.ERROR, "EQUIVALENT": S.EQUIVALENT,
}
_MUTMUT = {
    "killed": S.KILLED, "survived": S.SURVIVED, "no_tests": S.NO_COVERAGE, "timeout": S.TIMEOUT,
    "segfault": S.ERROR, "skipped": S.IGNORED, "suspicious": S.UNKNOWN, "check_was_interrupted_by_user": S.UNKNOWN,
}
_NO_REVISION = "the report does not record which revision/source it was produced from"


def _counted(run: MutationRun) -> MutationRun:
    run.counts = dict(Counter(m.status.value for m in run.mutants))
    return run


def _mutation_testing_elements(data: dict, run: MutationRun) -> MutationRun:
    framework = data.get("framework") or {}
    run.tool, run.tool_version = framework.get("name"), framework.get("version")
    for path, result in data["files"].items():
        if isinstance(result.get("source"), str):
            run.sources[path] = result["source"]
        for item in result["mutants"]:
            native = str(item["status"])
            start = (item.get("location") or {}).get("start") or {}
            run.mutants.append(
                MutantRecord(
                    mutant_id=str(item["id"]), status=_MTE.get(native, S.UNKNOWN), native_status=native, path=path,
                    line=start.get("line"), operator=item.get("mutatorName"), replacement=item.get("replacement"),
                    description=item.get("description"), killed_by=tuple(item.get("killedBy") or ()),
                    duration_ms=item.get("duration"),
                )
            )
    return _counted(run)


def _pit(root: ET.Element, run: MutationRun) -> MutationRun:
    run.tool = "PIT"
    run.limitations.append(_NO_REVISION)
    for index, node in enumerate(root.iter("mutation")):
        native = node.get("status") or ""
        text = lambda tag: (node.findtext(tag) or "").strip() or None  # noqa: E731
        cls, source_file = text("mutatedClass"), text("sourceFile")
        package = cls.rsplit(".", 1)[0].replace(".", "/") + "/" if cls and "." in cls else ""
        killers = text("killingTest") or text("killingTests")
        line = text("lineNumber")
        run.mutants.append(
            MutantRecord(
                mutant_id=f"{cls}:{text('mutatedMethod')}:{line}:{text('mutator')}:{index}", status=_PIT.get(native, S.UNKNOWN),
                native_status=native, path=f"{package}{source_file}" if source_file else None,
                line=int(line) if line and line.isdigit() else None, operator=text("mutator"),
                description=text("description"), killed_by=tuple(t for t in (killers or "").split("|") if t),
            )
        )
    if root.get("partial") == "true":
        run.limitations.append("PIT reported a partial run")
    return _counted(run)


def _mutmut_stats(data: dict, run: MutationRun) -> MutationRun:
    run.tool, run.per_mutant = "mutmut", False
    run.limitations += ["aggregate counts only: no per-mutant identity, location or killing test", _NO_REVISION]
    counts: Counter = Counter()
    for key, status in _MUTMUT.items():
        counts[status.value] += int(data.get(key) or 0)
    unaccounted = int(data.get("total") or 0) - sum(counts.values())
    if unaccounted > 0:
        counts[S.UNKNOWN.value] += unaccounted
    run.counts = {k: v for k, v in counts.items() if v}
    return run


def load_mutation_report(path: str | Path) -> MutationRun:
    path = Path(path)
    run = MutationRun(source=str(path))
    try:
        text = path.read_text(encoding="utf-8")
        if text.lstrip().startswith("<"):
            root = ET.fromstring(text)
            if root.tag != "mutations":
                raise ValueError(f"unsupported XML report root <{root.tag}>")
            return _pit(root, run)
        data = json.loads(text)
        if isinstance(data, dict) and "schemaVersion" in data and isinstance(data.get("files"), dict):
            return _mutation_testing_elements(data, run)
        if isinstance(data, dict) and {"killed", "survived", "total"} <= set(data):
            return _mutmut_stats(data, run)
        raise ValueError("unsupported mutation report format")
    except (OSError, ValueError, KeyError, TypeError, AttributeError, ET.ParseError) as exc:
        return MutationRun(source=str(path), error=f"{type(exc).__name__}: {exc}"[:300])
