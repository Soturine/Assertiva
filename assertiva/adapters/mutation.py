"""Mutation-tool report adapters. Assertiva ingests existing tools; it is not a mutation engine.

Supported (see research/2026-10-05-mutation-report-formats.md):
- mutation-testing-elements JSON (Stryker family and other producers of that schema): per mutant;
- PIT ``mutations.xml``: per mutant;
- mutmut ``mutmut-cicd-stats.json``: aggregate counts only;
- Cosmic Ray ``cosmic-ray dump`` (JSON lines): per mutant, no killing tests. Its ``cr-xml`` stays unsupported: it
  cannot distinguish pending from killed (research/2026-10-19-competitive/mutation.md).

``run_mutation_tool`` runs one native tool on a copy of a state, chosen by capability (``mutation_tools``): Cosmic Ray
for Python tests under the declared runner, StrykerJS for Jest/Vitest projects. The run is tied to that state by the
sources and tests it saw.
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
_BAIL = ("the report does not show that every detecting test was recorded (tools stop at the first failing test unless "
         "told otherwise): a mutant's named killers are a lower bound, not exclusive detection")


def _counted(run: MutationRun) -> MutationRun:
    run.counts = dict(Counter(m.status.value for m in run.mutants))
    return run


def _mutation_testing_elements(data: dict, run: MutationRun) -> MutationRun:
    framework = data.get("framework") or {}
    run.tool, run.tool_version = framework.get("name"), framework.get("version")
    config = data.get("config") if isinstance(data.get("config"), dict) else None  # StrykerJS writes its options here
    if config is not None and "disableBail" in config:
        run.killers_complete = config["disableBail"] is True
    if config is not None and "incremental" in config:
        run.incremental = config["incremental"] is True
    for path, result in (data.get("testFiles") or {}).items():  # test ids named in killedBy -> their file
        if isinstance((result or {}).get("source"), str):
            run.test_sources[path] = result["source"]
        for test in (result or {}).get("tests") or []:
            if isinstance(test, dict) and test.get("id") is not None:
                run.test_locations[str(test["id"])] = path
                if test.get("name"):
                    run.test_names[str(test["id"])] = str(test["name"])
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
                    duration_ms=item.get("duration"), status_reason=item.get("statusReason"),
                    stable_id=f"{path}:{start.get('line')}:{start.get('column')}:{item.get('mutatorName')}:{item.get('replacement')}",
                )
            )
    run.reused = sum(1 for m in run.mutants if (m.status_reason or "").startswith("Result based on previous run"))
    if run.reused:
        run.limitations.append(f"{run.reused} mutant result(s) were carried over from an earlier run, not executed in this one")
    if run.incremental:
        run.limitations.append("the tool ran incrementally: results of unchanged mutants may be carried over without a marker")
    if run.killers_complete is not True:
        run.limitations.append(_BAIL)
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
        for killer in (killers or "").split("|"):  # "pkg.ClassTest.method(...)" or "pkg.ClassTest.[engine:...]": its class path
            owner = killer.split("(", 1)[0].split(".[", 1)[0]
            parts = owner.split(".")
            if killer and len(parts) > 1:
                run.test_locations[killer] = "/".join(parts[:-1] if parts[-1][:1].islower() else parts)
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
    # `killingTests` is written only with the full mutation matrix; `killingTest` names the first detector only
    if any(node.find("killingTests") is not None for node in root.iter("mutation")):
        run.killers_complete = True
    elif any(node.find("killingTest") is not None for node in root.iter("mutation")):
        run.killers_complete = False
    if run.killers_complete is not True:
        run.limitations.append(_BAIL)
    return _counted(run)


def cosmic_ray_dump(text: str) -> list[MutantRecord]:
    """Mutants from ``cosmic-ray dump`` (one ``[work_item, result]`` JSON array per line; ``result`` is null while
    pending). The identity is the file, operator and occurrence, so the same mutant has the same id in two runs."""
    out = []
    for line in text.splitlines():
        if not line.strip():
            continue
        item, result = json.loads(line)
        for mutation in item.get("mutations") or []:
            path, operator, occurrence = str(mutation.get("module_path", "")).replace("\\", "/"), mutation.get("operator_name"), mutation.get("occurrence")
            if result is None:
                status, native = S.UNKNOWN, "pending"
            elif result.get("worker_outcome") != "normal":
                native = str(result.get("worker_outcome"))
                status = {"no-test": S.NO_COVERAGE, "skipped": S.IGNORED}.get(native, S.ERROR)
            else:
                native = str(result.get("test_outcome"))
                status = {"killed": S.TIMEOUT if result.get("output") == "timeout" else S.KILLED,
                          "survived": S.SURVIVED, "incompetent": S.ERROR}.get(native, S.UNKNOWN)
            start = mutation.get("start_pos") or [None]
            identity = f"{path}:{operator}:{occurrence}"
            out.append(MutantRecord(mutant_id=identity, status=status, native_status=native, path=path, stable_id=identity,
                                    line=start[0], operator=operator, description=mutation.get("definition_name")))
    return out


def _cosmic_ray(text: str, run: MutationRun) -> MutationRun:
    run.tool = "Cosmic Ray"
    run.mutants = cosmic_ray_dump(text)
    run.limitations += ["Cosmic Ray runs the whole test command for each mutant and records no killing test: per-test contribution is unknown",
                        _NO_REVISION]
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
        first = text.lstrip().split("\n", 1)[0]
        if first.startswith("[") and '"job_id"' in first:  # `cosmic-ray dump`: one JSON array per line
            return _cosmic_ray(text, run)
        data = json.loads(text)
        if isinstance(data, dict) and "schemaVersion" in data and isinstance(data.get("files"), dict):
            return _mutation_testing_elements(data, run)
        if isinstance(data, dict) and {"killed", "survived", "total"} <= set(data):
            return _mutmut_stats(data, run)
        raise ValueError("unsupported mutation report format")
    except (OSError, ValueError, KeyError, TypeError, AttributeError, ET.ParseError) as exc:
        return MutationRun(source=str(path), error=f"{type(exc).__name__}: {exc}"[:300])


_PYTHON_RUNNERS = ("pytest-native", "unittest", "django")


def mutation_tools(root: str | Path, python: str, origin: str | Path | None = None) -> list[dict]:
    """Each integrated mutation tool and whether it applies to this project (language, test runner, build) and, when it
    does, whether it can run here and why not. Chosen by capability, never by project name; ``origin`` is the project
    whose installed dependencies a copy of ``root`` would use."""
    from assertiva.adapters import cosmic_ray, runner_adapters, stryker
    from assertiva.adapters.python_discovery import test_files
    from assertiva.process import module_available

    root, origin = Path(root), Path(origin or root)
    runners = [a.adapter_id for a in runner_adapters(root, python) if a.adapter_id in _PYTHON_RUNNERS] if test_files(root) else []
    blocked = None
    if len(runners) > 1:
        blocked = (f"the project declares several Python runners ({', '.join(runners)}); keep the one to mutate with in "
                   ".assertiva.toml [tests] runners")
    elif runners and not module_available(python, "cosmic_ray"):
        blocked = f"{cosmic_ray.TOOL} is not installed in {python}; Assertiva does not install it"
    js_runner = stryker.test_runner(root)
    js = stryker.applies(root)
    return [
        {"tool": "cosmic-ray", "name": cosmic_ray.TOOL, "applies": bool(runners), "blocked": blocked,
         "runner": runners[0] if len(runners) == 1 else None,
         "why": f"Python tests run by {', '.join(runners)}" if runners else "no Python tests under a supported runner"},
        {"tool": "stryker", "name": stryker.TOOL, "applies": js, "runner": js_runner,
         "blocked": stryker.availability(origin) if js else None,
         "why": f"package.json declares {js_runner}" if js else "no Jest or Vitest project"},
    ]


def run_mutation_tool(state_root: str | Path, python: str, targets: list[str], tool: str | None = None,
                      origin: str | Path | None = None) -> MutationRun:
    """Run one native mutation tool on a copy of ``state_root``: the one the user names, otherwise the only one that
    applies. Several applicable tools need the user's choice; a tool that does not apply or cannot run gives an
    explained error, never a result. Tools are never all run, and a missing tool is never a pass."""
    from assertiva.adapters import cosmic_ray, stryker

    options = mutation_tools(state_root, python, origin)
    known = [o["tool"] for o in options]
    if tool is not None and tool not in known:
        return MutationRun(source="mutation tool", error=f"unknown mutation tool {tool!r}; integrated: {', '.join(known)}")
    named = [o for o in options if tool is None or o["tool"] == tool]
    applicable = [o for o in named if o["applies"]]
    if not applicable:
        why = "; ".join(f"{o['name']}: {o['why']}" for o in named)
        return MutationRun(source="mutation tool", error=f"no integrated mutation tool applies to this project ({why}); "
                                                        "import a report with --mutation-report")
    if len(applicable) > 1:
        return MutationRun(source="mutation tool", error="several mutation tools apply ("
                           + "; ".join(f"{o['tool']}: {o['why']}" for o in applicable) + "); choose one with --mutation-tool")
    chosen = applicable[0]
    if chosen["blocked"]:
        return MutationRun(source="mutation tool", tool=chosen["name"], error=chosen["blocked"])
    try:
        if chosen["tool"] == "cosmic-ray":
            run = cosmic_ray.run(state_root, python, targets, test_paths=[], runner=chosen["runner"])
        else:
            run = stryker.run(state_root, targets, origin=origin)
    except OSError as exc:  # the copy could not be made or read (a path too long, a file in use): nothing was concluded
        return MutationRun(source="mutation tool", tool=chosen["name"], orchestrated=True, targets=tuple(targets),
                           error=f"the run could not use a copy of this state ({type(exc).__name__}: {exc})"[:300])
    run.config = {**run.config, "selected": chosen["tool"],
                  "selected_because": chosen["why"] + (" (named by the user)" if tool else "")}
    return run


def unsafe_target(root: Path, target: str, suffixes: tuple[str, ...]) -> str | None:
    """Why a mutation tool must not rewrite ``target`` under ``root``, or None. Tools rewrite files in place, so every
    component from the root to the file must be a real directory or file (no symlink or junction: a link in a copy can
    point back outside it, and a write through it changes the outside), and the resolved file must lie under the
    resolved root. Adapters check it on the project and again on the copy the tool runs in."""
    from assertiva.workspace import is_link

    rel = Path(target)
    if rel.is_absolute() or ".." in rel.parts or not rel.parts or rel.suffix not in suffixes:
        return f"not a {'/'.join(suffixes)} file path relative to the project"
    current = Path(root)
    for part in rel.parts:
        current = current / part
        if is_link(current):
            return f"{current.relative_to(root).as_posix()} is a link: a write through it can reach outside the copy"
    if not current.is_file():
        return "not a file in the project"
    try:
        current.resolve().relative_to(Path(root).resolve())
    except ValueError:
        return "resolves outside the project"
    return None
