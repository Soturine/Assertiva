"""Failure intelligence from the evidence a runner reports: where a failure came from and which failures share a cause.

Both are inferred from the failure text a runner gives (the end of a traceback or stack, with its file:line frames),
so each carries its basis and stays UNKNOWN when the text cannot decide:

- ``origin``: INFRASTRUCTURE (the environment: a connection, a missing executable or module, resources, a timeout of
  the run), TEST (the test's own code raised something other than an assertion: a typo, a broken fixture), PRODUCT
  (the code under test raised), or UNKNOWN. An assertion that did not hold is UNKNOWN on purpose: the product's
  behavior or the test's expectation changed, and only reading both decides.
- ``clusters``: failures raised at the same place with the same exception type, whatever their messages say, so ten
  failures of one defect read as one lead. Grouping by text similarity alone is not done.
"""

from __future__ import annotations

import re
from collections import defaultdict

INFRASTRUCTURE = "INFRASTRUCTURE"
TEST = "TEST"
PRODUCT = "PRODUCT"
UNKNOWN = "UNKNOWN"

_ENVIRONMENT = re.compile(
    r"ConnectionRefused|ECONNREFUSED|ECONNRESET|ENOTFOUND|EAI_AGAIN|Connection refused|could not connect to server|"
    r"No space left on device|ENOSPC|MemoryError|OutOfMemoryError|Too many open files|EMFILE|"
    r"Executable doesn't exist|browserType\.launch|command not found|is not recognized as an internal or external command|"
    r"Could not resolve host|Temporary failure in name resolution|SSL(?:Error|: CERTIFICATE)|"
    r"Unable to access jarfile|Could not find or load main class|Could not resolve dependencies|"
    r"service .{0,40}(?:unavailable|not available)|Docker daemon|Cannot connect to the Docker", re.I)
_ASSERTION = re.compile(
    r"\bAssertionError\b|\bAssertionFailedError\b|\bComparisonFailure\b|\bAssertionFailure\b|expect\(received\)|"
    r"\bExpected\b[^\n]{0,80}\bReceived\b|\bexpected:?\s*<|\bto (?:be|equal|have|contain)\b|\bMismatch\b|"
    r"\bassert\s+.{0,120}==|\bAssert\.\w+ failed|org\.opentest4j\.", re.S)
_TEST_CODE_ERROR = re.compile(r"\b(?:NameError|SyntaxError|IndentationError|ImportError|ModuleNotFoundError|ReferenceError|"
                              r"fixture '[^']+' not found|NoSuchMethodError|ClassNotFoundException)\b")
_TYPE = re.compile(r"\b([A-Z][A-Za-z0-9_.]*(?:Error|Exception|Failure|Exit|Timeout))\b")
_FRAME = re.compile(r"([\w./\\-]+\.(?:py|js|cjs|mjs|ts|tsx|jsx|java|kt)):(\d+)")
_JVM_FRAME = re.compile(r"\bat [\w.$]+\(([\w$]+\.(?:java|kt)):(\d+)\)")


def _test_file(path: str, test_paths: set[str]) -> bool:
    norm = path.replace("\\", "/")
    # whole path components only: "tests/test_pricing.py" ends with the characters of "pricing.py", not with that file
    for test_path in (p.replace("\\", "/") for p in test_paths if p):
        if norm == test_path or norm.endswith("/" + test_path) or test_path.endswith("/" + norm):
            return True
    name = norm.rsplit("/", 1)[-1]
    return bool(re.search(r"(^test_|_test\.py$|\.(?:test|spec)\.[cm]?[jt]sx?$|Tests?\.(?:java|kt)$|IT\.(?:java|kt)$)", name)
                or "/tests/" in f"/{norm}" or "/__tests__/" in f"/{norm}" or "/src/test/" in f"/{norm}")


def raise_site(message: str | None) -> tuple[str | None, str | None]:
    """(exception type, file:line of the innermost frame the text shows), each None when not visible."""
    if not message:
        return None, None
    types = _TYPE.findall(message)
    frames = [f"{m.group(1).replace(chr(92), '/').rsplit('/', 1)[-1]}:{m.group(2)}" for m in _JVM_FRAME.finditer(message)]
    if frames:  # a JVM stack lists the innermost frame first
        return (types[0] if types else None), frames[0]
    frames = [f"{m.group(1).replace(chr(92), '/')}:{m.group(2)}" for m in _FRAME.finditer(message)]
    return (types[-1] if types else None), (frames[-1] if frames else None)


def origin(message: str | None, test_paths=()) -> tuple[str, str]:
    """(origin, why) for one failure; see the module docstring. INFERRED from the failure text."""
    if not message:
        return UNKNOWN, "the runner gave no failure text"
    if _ENVIRONMENT.search(message):
        return INFRASTRUCTURE, f"the failure names the environment ({_ENVIRONMENT.search(message).group(0)[:60]})"
    kind, site = raise_site(message)
    if _ASSERTION.search(message) and (kind is None or "Assert" in kind or "Comparison" in kind or "opentest4j" in message):
        return UNKNOWN, "an assertion did not hold: the product's behavior or the test's expectation changed; read both"
    if site is None:
        return UNKNOWN, "no source location in the failure text"
    in_test = _test_file(site.rsplit(":", 1)[0], set(test_paths))
    if in_test and _TEST_CODE_ERROR.search(message):
        return TEST, f"{kind or 'an error'} raised in test code at {site}, not by an assertion"
    if not in_test:
        return PRODUCT, f"{kind or 'an error'} raised in product code at {site}"
    return UNKNOWN, f"{kind or 'an error'} raised in test code at {site}: a broken test or a product change it relied on"


def clusters(failures: list[tuple[str, str | None]], minimum: int = 2) -> list[dict]:
    """Failures (invocation id, failure text) raised at the same site with the same exception type, largest first."""
    groups: dict[tuple[str, str], list[str]] = defaultdict(list)
    for invocation, message in failures:
        kind, site = raise_site(message)
        if site is not None:
            groups[(kind or "?", site)].append(invocation)
    return [{"exception": kind, "raised_at": site, "count": len(ids), "invocations": ids[:20],
             "basis": "INFERRED: same exception type raised at the same place"}
            for (kind, site), ids in sorted(groups.items(), key=lambda kv: -len(kv[1])) if len(ids) >= minimum]
