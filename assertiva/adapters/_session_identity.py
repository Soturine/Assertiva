"""What a test process really used, observed inside it when its run ends (pytest plugin, unittest and Django runs).

Copied next to the evidence module as ``assertiva_session_identity`` and imported by it in the *target* interpreter;
it never imports project code: it only reads ``sys.modules`` as the run left it. Standard library only; it must keep
working on every supported Python. Modules imported only by a subprocess of the tests are not observed.
"""

import os

LISTED = 50  # names reported per side; every loaded module is inspected and counted whatever this is


def project_names(root):
    """Top-level modules and packages the project itself provides (at the root or under src/), tests excluded."""
    names = set()
    for base in (root, os.path.join(root, "src")):
        try:
            entries = os.listdir(base)
        except OSError:
            continue
        for entry in entries:
            path = os.path.join(base, entry)
            if entry.endswith(".py") and entry not in ("conftest.py", "setup.py", "manage.py") and not entry.startswith("test"):
                names.add(entry[:-3])
            elif os.path.isfile(os.path.join(path, "__init__.py")) and not entry.startswith(("test", ".")):
                names.add(entry)
    return names


def inside(path, root, real_root=None):
    real_root = real_root or os.path.realpath(root)
    try:
        return os.path.commonpath([os.path.realpath(path), real_root]) == real_root
    except ValueError:  # another drive
        return False


def session_record(root):
    """Where the project's own modules were imported from (the copy, or an installed copy that shadows it), the
    temporary directory tests get, and site directories borrowed from another environment."""
    import site
    import sys
    import tempfile

    root = str(root)
    # an installed-artifact run removes the project's packages from its copy: the auditor names them (the wheel's
    # top-level names) and the artifact's environment, so the observer can tell the artifact from anything else
    declared = [n for n in os.environ.get("ASSERTIVA_PROJECT_NAMES", "").split(",") if n]
    artifact_root = os.environ.get("ASSERTIVA_ARTIFACT_ROOT") or None
    names = set(declared) if declared else project_names(root)
    real_root = os.path.realpath(root)
    # every loaded module of the project's packages, not only the top level: an import hook (an editable install's
    # finder, a __path__ extension) can serve a submodule from another tree while the package itself comes from here.
    # All of them are inspected; only the names listed in the record are bounded (counts are always complete).
    found_inside, found_outside = {}, {}
    for name in sorted(n for n in list(sys.modules) if n.split(".")[0] in names):
        location = getattr(sys.modules.get(name), "__file__", None)
        if location:
            (found_inside if inside(location, root, real_root) else found_outside)[name] = location
    identity = {"loaded": len(found_inside) + len(found_outside), "inside": len(found_inside), "outside": len(found_outside),
                "inside_listed": dict(list(found_inside.items())[:LISTED]),
                "outside_listed": dict(list(found_outside.items())[:LISTED]),
                "names_truncated": len(found_inside) > LISTED or len(found_outside) > LISTED,
                "project_names": len(names), "names_from": "auditor" if declared else "project root"}
    if artifact_root:
        identity["in_artifact"] = sum(1 for location in found_outside.values() if inside(location, artifact_root))
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
    borrowed = [p for p in sites if not any(inside(p, prefix) for prefix in prefixes)
                and not (user_site and os.path.realpath(p) == os.path.realpath(user_site))]
    return {"root": root, "identity": identity, "tempdir": temp, "tempdir_writable": writable,
            "python": sys.executable, "prefix": sys.prefix, "borrowed_site_dirs": borrowed,
            "user_site": user_site if user_site in sys.path else None}
