"""pytest plugin loaded by Assertiva into the *target* pytest process.

It is copied outside the project and loaded with ``-p``. It only records native
collection/execution facts as JSON lines in ``ASSERTIVA_EVIDENCE_FILE``; it never
changes test behavior. Standard library only: it runs in the project's interpreter.
"""

import inspect
import json
import os

_OUT = os.environ.get("ASSERTIVA_EVIDENCE_FILE")


def _emit(record):
    if _OUT:
        with open(_OUT, "a", encoding="utf-8") as handle:
            handle.write(json.dumps(record) + "\n")


def _relative(path, root):
    try:
        return os.path.relpath(path, root).replace(os.sep, "/")
    except ValueError:
        return str(path).replace(os.sep, "/")


def pytest_collectreport(report):
    if report.failed:
        _emit({"type": "collect_error", "nodeid": report.nodeid, "message": str(report.longrepr)[-2000:]})


def pytest_deselected(items):
    for item in items:
        _emit({"type": "deselected", "nodeid": item.nodeid})


def pytest_collection_finish(session):
    root = str(session.config.rootpath)
    for item in session.items:
        function = getattr(item, "function", None)
        declared_file = qualname = None
        if function is not None:
            qualname = getattr(function, "__qualname__", None)
            try:
                declared_file = _relative(inspect.getsourcefile(function), root)
            except (TypeError, OSError):
                declared_file = None
        callspec = getattr(item, "callspec", None)
        cls = getattr(item, "cls", None)
        _emit(
            {
                "type": "item",
                "nodeid": item.nodeid,
                "qualname": qualname,
                "declared_file": declared_file,
                "cls": cls.__qualname__ if cls is not None else None,
                "params_id": callspec.id if callspec is not None else None,
                "markers": sorted({mark.name for mark in item.iter_markers()}),
            }
        )


def pytest_runtest_logreport(report):
    _emit(
        {
            "type": "report",
            "nodeid": report.nodeid,
            "when": report.when,
            "outcome": report.outcome,
            "wasxfail": hasattr(report, "wasxfail"),
            "duration": report.duration,
            "message": str(report.longrepr)[-1000:] if report.failed else None,
        }
    )
