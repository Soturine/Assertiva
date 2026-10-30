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


def _project_names(root):
    """Top-level modules and packages the project itself provides (at the root or under src/), tests excluded."""
    names = set()
    for base in (root, os.path.join(root, "src")):
        try:
            entries = os.listdir(base)
        except OSError:
            continue
        for entry in entries:
            path = os.path.join(base, entry)
            if entry.endswith(".py") and entry not in ("conftest.py", "setup.py") and not entry.startswith("test"):
                names.add(entry[:-3])
            elif os.path.isfile(os.path.join(path, "__init__.py")) and not entry.startswith(("test", ".")):
                names.add(entry)
    return names


def _inside(path, root):
    try:
        return os.path.commonpath([os.path.realpath(path), os.path.realpath(root)]) == os.path.realpath(root)
    except ValueError:  # another drive
        return False


def pytest_sessionfinish(session):
    """What the run really used: where the project's own modules were imported from (the copy, or an installed copy
    that shadows it), the temporary directory tests get, and site directories borrowed from another environment."""
    import site
    import sys
    import tempfile

    root = str(session.config.rootpath)
    imported = {}
    names = _project_names(root)
    # every loaded module of the project's packages, not only the top level: an import hook (an editable install's
    # finder, a __path__ extension) can serve a submodule from another tree while the package itself comes from here
    for name in sorted(n for n in list(sys.modules) if n.split(".")[0] in names)[:500]:
        location = getattr(sys.modules.get(name), "__file__", None)
        if location:
            imported[name] = {"file": location, "inside_root": _inside(location, root)}
    temp = tempfile.gettempdir()
    try:
        with tempfile.TemporaryFile(dir=temp):
            writable = True
    except OSError:
        writable = False
    prefixes = {os.path.realpath(p) for p in (sys.prefix, sys.base_prefix, getattr(sys, "exec_prefix", sys.prefix))}
    sites = [p for p in sys.path if os.path.basename(p.rstrip("/\\")) in ("site-packages", "dist-packages")]
    user_site = site.getusersitepackages() if getattr(site, "ENABLE_USER_SITE", False) else None
    # the per-user site directory belongs to this interpreter; another environment's site-packages does not
    borrowed = [p for p in sites if not any(_inside(p, prefix) for prefix in prefixes)
                and not (user_site and os.path.realpath(p) == os.path.realpath(user_site))]
    _emit({"type": "session", "root": root, "imported": imported, "tempdir": temp, "tempdir_writable": writable,
           "python": sys.executable, "prefix": sys.prefix, "borrowed_site_dirs": borrowed,
           "user_site": user_site if user_site in sys.path else None})


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
