"""Recording unittest result for native unittest and Django runs; copied next to the run, never into the project.

`python -m assertiva_unittest_evidence ARGS` behaves like `python -m unittest ARGS` with a result class that
appends one JSON line per event to $ASSERTIVA_EVIDENCE_FILE. Django: `manage.py test --testrunner
assertiva_unittest_evidence.DjangoRunner` subclasses the project's own TEST_RUNNER and only swaps its result
class, so the project's runner behavior (databases, settings, tags, parallelism) is kept.
This file is stdlib-only and must keep working on every supported Python.
"""

import inspect
import json
import os
import sys
import time
import traceback
import unittest

_OUT = os.environ.get("ASSERTIVA_EVIDENCE_FILE")


def _write(record):
    if _OUT:
        with open(_OUT, "a", encoding="utf-8") as handle:
            handle.write(json.dumps(record) + "\n")


def _source(test):
    """(file relative to cwd, class qualname, method name, class that declares the method)."""
    cls = type(test)
    method = getattr(test, "_testMethodName", None)
    try:
        path = inspect.getsourcefile(cls) or ""
        path = os.path.relpath(os.path.realpath(path), os.path.realpath(os.getcwd())).replace("\\", "/") if path else ""
    except (TypeError, ValueError):
        path = ""
    declared_by = cls.__qualname__
    function = getattr(cls, method, None) if method else None
    owner = getattr(function, "__qualname__", "").rsplit(".", 1)[0] if function is not None else ""
    declared_file = path
    if owner and owner != cls.__qualname__:
        declared_by = owner
        for base in cls.__mro__:
            if base.__qualname__ == owner:
                try:
                    found = inspect.getsourcefile(base)
                    declared_file = os.path.relpath(os.path.realpath(found), os.path.realpath(os.getcwd())).replace("\\", "/") if found else path
                except (TypeError, ValueError):
                    pass
                break
    return path, cls.__qualname__, method, declared_by, declared_file


def _message(err):
    if not err:
        return None
    if isinstance(err, str):
        return err[:1000]
    try:
        return "".join(traceback.format_exception_only(err[0], err[1])).strip()[:1000]
    except Exception:  # noqa: BLE001 - never break the run over a message
        return repr(err)[:1000]


class _Recording:
    """Mixin over a unittest result class: one record per started test and per outcome."""

    def startTest(self, test):
        self._assertiva_started = getattr(self, "_assertiva_started", {})
        self._assertiva_started[test.id()] = time.perf_counter()
        holder = type(test).__name__ in ("_ErrorHolder", "_FailedTest")
        if not holder:
            path, cls, method, declared_by, declared_file = _source(test)
            _write({"type": "item", "id": test.id(), "file": path, "cls": cls, "method": method,
                    "declared_by": declared_by, "declared_file": declared_file})
        super().startTest(test)

    def _record(self, test, outcome, err=None, subtest=None):
        started = getattr(self, "_assertiva_started", {}).get(test.id())
        kind = type(test).__name__
        record = {"type": "outcome", "id": test.id(), "outcome": outcome, "message": _message(err),
                  "duration": round(time.perf_counter() - started, 6) if started is not None else None}
        if kind == "_FailedTest":  # the loader could not import or load a module
            record = {"type": "load_error", "id": test.id(), "message": _message(err)}
        elif kind == "_ErrorHolder":  # setUpClass / setUpModule / tearDown* failed or skipped
            record = {"type": "fixture", "description": getattr(test, "description", test.id()), "outcome": outcome,
                      "message": _message(err)}
        elif subtest is not None:
            record["subtest"] = subtest._subDescription()
        _write(record)

    def addSuccess(self, test):
        self._record(test, "passed")
        super().addSuccess(test)

    def addFailure(self, test, err):
        self._record(test, "failed", err)
        super().addFailure(test, err)

    def addError(self, test, err):
        self._record(test, "error", err)
        super().addError(test, err)

    def addSkip(self, test, reason):
        self._record(test, "skipped", reason)
        super().addSkip(test, reason)

    def addExpectedFailure(self, test, err):
        self._record(test, "xfailed", err)
        super().addExpectedFailure(test, err)

    def addUnexpectedSuccess(self, test):
        self._record(test, "xpassed")
        super().addUnexpectedSuccess(test)

    def addSubTest(self, test, subtest, err):
        if err is None:
            outcome = "passed"
        elif issubclass(err[0], test.failureException):
            outcome = "failed"
        else:
            outcome = "error"
        self._record(test, outcome, err, subtest)
        super().addSubTest(test, subtest, err)


def recording(base):
    return type("Recording" + base.__name__, (_Recording, base), {})


def main():
    _write({"type": "session", "runner": "unittest", "python": sys.version.split()[0]})
    runner = unittest.TextTestRunner(resultclass=recording(unittest.TextTestResult))
    unittest.main(module=None, argv=["python -m unittest", *sys.argv[1:]], testRunner=runner)


def __getattr__(name):
    if name != "DjangoRunner":
        raise AttributeError(name)
    from django.conf import settings
    from django.test.utils import get_runner

    base = get_runner(settings)

    class DjangoRunner(base):
        def get_resultclass(self):
            parent = getattr(super(), "get_resultclass", lambda: None)() or unittest.TextTestResult
            return recording(parent)

    import django

    _write({"type": "session", "runner": "django", "django": django.get_version(), "test_runner": f"{base.__module__}.{base.__qualname__}",
            "python": sys.version.split()[0]})
    globals()["DjangoRunner"] = DjangoRunner
    return DjangoRunner


if __name__ == "__main__":
    main()
