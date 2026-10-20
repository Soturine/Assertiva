"""Normalized forms of a source file, to tell a cosmetic change (comments, formatting) from a behavioral one, and the
packages a dependency file pins, to say which dependencies a change touched.

A change is cosmetic only when both revisions have the same normalized form: Python compares syntax trees (comments
and formatting vanish; docstrings stay, since doctests and introspection read them); brace languages compare the text
with comments removed and spaces collapsed within each line, keeping line breaks (JavaScript inserts semicolons at
some of them). Any other file has no normalized form here, so its change is never called cosmetic.
"""

from __future__ import annotations

import ast
import json
import re
import tomllib
from pathlib import PurePosixPath

_BRACE = {".js", ".cjs", ".mjs", ".jsx", ".ts", ".tsx", ".java", ".kt", ".kts", ".scala", ".go", ".cs", ".swift", ".rs"}
LOCKFILES = frozenset({"package-lock.json", "npm-shrinkwrap.json", "yarn.lock", "pnpm-lock.yaml", "poetry.lock", "uv.lock",
                       "Pipfile.lock", "Gemfile.lock", "go.sum", "Cargo.lock", "gradle.lockfile", "composer.lock",
                       "packages.lock.json"})
_REQUIREMENTS = re.compile(r"^(?:requirements|constraints)[\w.-]*\.txt$")


def normalized(path: str, text: str | None) -> str | None:
    """The normalized form of ``text`` (see the module docstring), or None when it has none here."""
    if text is None:
        return None
    suffix = PurePosixPath(path).suffix
    if suffix == ".py":
        try:
            return ast.dump(ast.parse(text), include_attributes=False)
        except (SyntaxError, ValueError):
            return None
    if suffix in _BRACE:
        from .test_facts import _strip_strings_and_comments

        code = _strip_strings_and_comments(text, strings=False)
        lines = (re.sub(r"[ \t]+", " ", line).strip() for line in code.splitlines())
        return "\n".join(line for line in lines if line)
    return None


def is_dependency_file(path: str) -> bool:
    name = PurePosixPath(path).name
    return name in LOCKFILES or bool(_REQUIREMENTS.match(name))


def _pins(name: str, text: str) -> dict[str, str] | None:
    """package -> version the file pins, for the formats read here; None for the others."""
    try:
        if name in ("package-lock.json", "npm-shrinkwrap.json"):
            packages = json.loads(text).get("packages") or {}
            return {k.rsplit("node_modules/", 1)[-1]: str(v.get("version")) for k, v in packages.items() if k and isinstance(v, dict)}
        if name in ("poetry.lock", "uv.lock"):
            return {p["name"]: str(p.get("version")) for p in tomllib.loads(text).get("package", []) if "name" in p}
        if _REQUIREMENTS.match(name):
            out = {}
            for line in text.splitlines():
                m = re.match(r"\s*([A-Za-z0-9_.\[\]-]+)\s*(?:===?|~=|>=|<=)\s*([^\s;#]+)", line)
                if m:
                    out[m.group(1).lower()] = m.group(2)
            return out
    except (ValueError, KeyError, TypeError, AttributeError, tomllib.TOMLDecodeError):
        return None
    return None


def dependency_changes(path: str, before: str | None, after: str | None) -> list[str]:
    """What changed in a dependency file: "name old -> new", "+name version", "-name version"; one generic line when
    the format is not read here."""
    name = PurePosixPath(path).name
    old, new = _pins(name, before or ""), _pins(name, after or "")
    if old is None or new is None:
        return [f"{name} changed (its format is not read: the packages are not listed)"]
    out = [f"{k} {old[k]} -> {new[k]}" for k in sorted(old.keys() & new.keys()) if old[k] != new[k]]
    out += [f"+{k} {new[k]}" for k in sorted(new.keys() - old.keys())]
    out += [f"-{k} {old[k]}" for k in sorted(old.keys() - new.keys())]
    return out or [f"{name} changed without a version change"]
