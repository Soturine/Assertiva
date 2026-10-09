"""Language extractors for test effectiveness: each turns its language's tests into the shared ``TestFacts``.

Python reads the AST (the same analysis as the weak-oracle signals, so helpers, guards and interaction checks count).
JavaScript/TypeScript (Jest, Vitest, Testing Library, Playwright, Cypress) and Kotlin/Java (JUnit 4/5, kotlin.test,
Kotest, Espresso, Compose UI test, MockK/Mockito) are read lexically: test blocks are found by their declaration and
brace matching, assertions by their matcher names. A lexical reading does not resolve imports, helpers in other files
or macros; that limit is stated with the results and the agent reads the code when it matters.
"""

from __future__ import annotations

import ast
import os
import re
from pathlib import Path

from assertiva.effectiveness import TestFacts

_MANIFESTS = ("package.json", "pyproject.toml", "setup.py", "settings.gradle", "settings.gradle.kts", "build.gradle",
              "build.gradle.kts", "pom.xml", "manage.py", "go.mod", "Cargo.toml")
_SKIP_DIRS = {"node_modules", ".git", "build", "dist", ".gradle", "venv", ".venv", "__pycache__", "target", "coverage"}
_LEVEL_WORDS = (("e2e", "E2E"), ("end-to-end", "E2E"), ("integration", "INTEGRATION"), ("integrationtest", "INTEGRATION"),
                ("functional", "FUNCTIONAL"), ("contract", "CONTRACT"), ("unit", "UNIT"))
LIMITS = {
    "python": ["Python tests are read from their syntax tree: helpers in other modules, fixtures and plugins are not followed"],
    "javascript": ["JavaScript/TypeScript tests are read lexically: imported helpers, custom matchers and macros are not followed"],
    "jvm": ["Kotlin/Java tests are read lexically: helpers in other files, custom matchers and inherited setup are not followed"],
}


def _walk(root: Path, predicate) -> list[Path]:
    out = []
    for current, dirs, files in os.walk(root):
        dirs[:] = [d for d in dirs if d not in _SKIP_DIRS and not d.startswith(".")]
        out += [Path(current) / f for f in files if predicate(Path(current) / f)]
    return sorted(out)


def _level(rel: str, extra: str = "") -> str | None:
    text = (rel + " " + extra).lower().replace("\\", "/")
    for word, level in _LEVEL_WORDS:
        if re.search(rf"(^|[/_\-. @(\"']){word}([/_\-. )\"']|$)", text):
            return level
    return None


_TIME_SUBJECT = re.compile(r"time_?out|expir|deadline|\bttl\b|_ttl|ttl_|debounce|throttl|elapsed|backoff|stale|clock|"
                           r"Timeout(Error|Exception|CancellationException)|TimeoutError", re.I)


def _time_is_subject(test_id: str, body: str) -> bool:
    """Whether time itself is what the test checks (timeouts, expiry, debounce): then a sleep or wait is the stimulus."""
    body = re.sub(r"\b(setTimeout|waitForTimeout|clearTimeout)\b", " ", body)  # the waiting call itself is not the subject
    return bool(_TIME_SUBJECT.search(test_id) or _TIME_SUBJECT.search(body))


def _norm(text: str) -> str:
    return re.sub(r"\s+", " ", text).strip()


# --- shared lexical helpers --------------------------------------------------------------------

def _strip_strings_and_comments(text: str) -> str:
    """Same length, with string contents and comments blanked, so braces inside them are not counted."""
    out, i, n = list(text), 0, len(text)
    while i < n:
        c = text[i]
        if text.startswith("//", i):
            j = text.find("\n", i)
            j = n if j < 0 else j
            out[i:j] = " " * (j - i)
            i = j
        elif text.startswith("/*", i):
            j = text.find("*/", i + 2)
            j = n if j < 0 else j + 2
            out[i:j] = [ch if ch == "\n" else " " for ch in text[i:j]]
            i = j
        elif c in "\"'`":
            j = i + 1
            while j < n and text[j] != c:
                j += 2 if text[j] == "\\" else 1
            out[i + 1:j] = " " * max(0, j - i - 1)
            i = j + 1
        else:
            i += 1
    return "".join(out)


def _block(clean: str, start: int) -> tuple[int, int] | None:
    """Span of the brace block opening at or after ``start``."""
    open_at = clean.find("{", start)
    if open_at < 0:
        return None
    depth = 0
    for i in range(open_at, len(clean)):
        if clean[i] == "{":
            depth += 1
        elif clean[i] == "}":
            depth -= 1
            if depth == 0:
                return open_at, i + 1
    return None


def _swallowed(clean_body: str, assertion: re.Pattern) -> bool:
    """An empty catch after a try that holds an assertion, or when no assertion is outside any try."""
    hits = [m.start() for m in assertion.finditer(clean_body)]
    for m in re.finditer(r"\btry\s*\{", clean_body):
        span = _block(clean_body, m.end() - 1)
        if span is None:
            continue
        handler = re.match(r"\s*catch\s*(\([^)]*\))?\s*\{\s*\}", clean_body[span[1]:])
        if handler and (any(span[0] <= h < span[1] for h in hits) or not any(not (span[0] <= h < span[1]) for h in hits)):
            return True
    return False


def _conditional_only(clean_body: str, assertion: re.Pattern) -> bool:
    """Every assertion of the body lies inside an `if` block."""
    hits = [m.start() for m in assertion.finditer(clean_body)]
    if not hits:
        return False
    spans = []
    for m in re.finditer(r"\bif\s*\(", clean_body):
        span = _block(clean_body, m.end())
        if span is None:
            continue
        other = re.match(r"\s*else\s*\{", clean_body[span[1]:])
        if other:  # an else branch that also checks (or fails) leaves no path without a check
            branch = _block(clean_body, span[1] + other.end() - 1)
            if branch and (any(branch[0] <= h < branch[1] for h in hits) or re.search(r"\b(fail|throw)\b", clean_body[branch[0]:branch[1]])):
                continue
        spans.append(span)
    return all(any(a <= h < b for a, b in spans) for h in hits)


# --- Python -----------------------------------------------------------------------------------

_PY_ORACLES = {"BEHAVIORAL_ASSERTION": "VALUE", "EXISTENCE_ONLY": "EXISTENCE", "HTTP_STATUS_ONLY": "STATUS_ONLY",
               "ERROR_STATUS_ONLY": "STATUS_ONLY", "BROAD_ERROR_EXPECTATION": "BROAD_ERROR", "EXPECTED_ERROR_CONTRACT": "SPECIFIC_ERROR",
               "INTERACTION_ASSERTION": "INTERACTION", "FORBIDDEN_CALL_GUARD": "GUARD", "HELPER_ASSERTION": "HELPER",
               "EXPLICIT_FAIL": "VALUE", "EXPECTED_WARNING": "SPECIFIC_ERROR"}
_PY_NETWORK = ("requests", "httpx", "urllib", "urlopen", "socket", "smtplib", "boto", "aiohttp", "http.client")
_PY_DB = (".objects", "session", "cursor", "database", ".db.", "repository")


def _python_facts(root: Path) -> list[TestFacts]:
    from assertiva.adapters.python_test_classes import classify_classes
    from assertiva.pytest_audit import _test_files, assertion_helpers

    out = []
    for path in _test_files(root):
        try:
            tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        except (SyntaxError, UnicodeDecodeError, OSError):
            continue
        rel = path.relative_to(root).as_posix()
        helpers = assertion_helpers(tree)
        kinds = classify_classes(tree)
        functions = []
        for node in tree.body:
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) and node.name.startswith("test"):
                functions.append((f"{rel}::{node.name}", node, helpers[None]))
            elif isinstance(node, ast.ClassDef) and kinds.get(node.name) is not None and kinds[node.name].value != "NOT_COLLECTED":
                for child in node.body:
                    if isinstance(child, (ast.FunctionDef, ast.AsyncFunctionDef)) and child.name.startswith("test"):
                        functions.append((f"{rel}::{node.name}::{child.name}", child, helpers.get(node.name, helpers[None])))
        for test_id, node, scope in functions:
            out.append(_python_test(test_id, rel, node, scope))
    return out


def _python_test(test_id: str, rel: str, node, helpers) -> TestFacts:
    from assertiva.pytest_audit import _function_assertions, _expr_name, negative_path_evidence

    kinds = [k for k in _function_assertions(node, helpers) if k != "NO_ASSERTION"]
    oracles = tuple(dict.fromkeys(_PY_ORACLES.get(k, "VALUE") for k in kinds))
    parents = {child: parent for parent in ast.walk(node) for child in ast.iter_child_nodes(parent)}
    asserts, signature, doubles, smells = [], [], [], []
    boundaries, simulated, surfaces = set(), set(), set()
    for item in ast.walk(node):
        if isinstance(item, ast.Assert):
            asserts.append(item)
            signature.append(ast.unparse(item.test))
            if isinstance(item.test, ast.Constant) and item.test.value:
                smells.append("TAUTOLOGY")
            if isinstance(item.test, ast.Compare) and len(item.test.comparators) == 1 and ast.dump(item.test.left) == ast.dump(item.test.comparators[0]):
                smells.append("TAUTOLOGY")
        elif isinstance(item, ast.Call):
            name = _expr_name(item.func) or ""
            leaf = name.split(".")[-1]
            if leaf.startswith("assert") and name.startswith("self."):
                asserts.append(item)
                signature.append(ast.unparse(item))
                if len(item.args) == 2 and ast.dump(item.args[0]) == ast.dump(item.args[1]):
                    smells.append("TAUTOLOGY")
                if leaf in ("assertTrue",) and item.args and isinstance(item.args[0], ast.Constant):
                    smells.append("TAUTOLOGY")
            if name in ("time.sleep", "sleep", "asyncio.sleep") and not _time_is_subject(test_id, ast.unparse(node)):
                smells.append("SLEEP")
            if leaf in ("patch", "object", "setattr") or name.endswith(("mock.patch", "mocker.patch")):
                target = ast.unparse(item.args[0]) if item.args else name
                doubles.append(target.strip("'\""))
            lowered = name.lower()
            if re.search(r"(^|\.)(client|async_client|api_client)\.(get|post|put|patch|delete|head|options)$", lowered):
                boundaries.add("HTTP")
            if lowered.startswith(_PY_NETWORK):
                boundaries.add("NETWORK")
            if any(k in "." + lowered + "." for k in _PY_DB) or leaf in ("save", "refresh_from_db", "commit", "execute"):
                boundaries.add("DATABASE")
            if lowered.startswith(("page.", "driver.", "browser.", "self.selenium.")):
                boundaries.add("BROWSER")
            if lowered.startswith("subprocess."):
                boundaries.add("PROCESS")
            if leaf in ("open", "write_text", "read_text", "write_bytes", "mkdtemp"):
                boundaries.add("FILESYSTEM")
    for target in doubles:
        low = target.lower()
        if any(k in low for k in _PY_NETWORK) or "http" in low or "api" in low or "gateway" in low or "client" in low:
            simulated.add("NETWORK")
            boundaries.add("NETWORK")
        if any(k.strip(".") in low for k in _PY_DB):
            simulated.add("DATABASE")
            boundaries.add("DATABASE")
    for deco in getattr(node, "decorator_list", []):
        text = ast.unparse(deco)
        if "patch" in text:
            doubles.append(text)
        if re.search(r"responses\.activate|respx\.mock", text):
            simulated.add("NETWORK")
            boundaries.add("NETWORK")
    for item in asserts:
        text = ast.unparse(item)
        if "status_code" in text or ".status" in text:
            surfaces.add("RESPONSE_STATUS")
        if re.search(r"\.json\(\)|\.content|\.data\b|\.text\b|\.context", text):
            surfaces.add("RESPONSE_BODY")
        if re.search(r"refresh_from_db|\.objects\.|\.exists\(\)|\.count\(\)", text):
            surfaces.add("PERSISTENCE")
        if "assert_called" in text or "assert_not_called" in text:
            surfaces.add("INTERACTION")
    if "SPECIFIC_ERROR" in oracles or "BROAD_ERROR" in oracles:
        surfaces.add("EXCEPTION")
    if asserts and not surfaces:
        surfaces.add("RETURN")
    for item in ast.walk(node):  # an exception caught and ignored where it hides the behavior, not in cleanup
        if not isinstance(item, ast.Try) or any(isinstance(a, ast.Try) and _within(item, a.finalbody) for a in _ancestors(item, parents, node)):
            continue
        guarded = {id(n) for n in ast.walk(ast.Module(body=item.body, type_ignores=[]))}
        inside = any(id(a) in guarded for a in asserts)
        outside = any(id(a) not in guarded for a in asserts)
        for handler in item.handlers:
            ignores = all(isinstance(s, (ast.Pass, ast.Continue)) or (isinstance(s, ast.Expr) and isinstance(s.value, ast.Constant))
                          for s in handler.body)
            if ignores and (inside or not outside):
                smells.append("SWALLOWED_EXCEPTION")
    if asserts and all(any(isinstance(p, ast.If) and not _checks(p.orelse) for p in _ancestors(a, parents, node)) for a in asserts):
        smells.append("CONDITIONAL_ASSERTION")
    _, _, unobserved = negative_path_evidence(node)
    if unobserved:
        smells.append("UNAWAITED_ASYNC")
    if len([d for d in doubles if "patch" in d or d]) >= 4:
        smells.append("EXCESSIVE_MOCKING")
    if oracles == ("SNAPSHOT",):
        smells.append("SNAPSHOT_ONLY")
    if not oracles and "BROWSER" in boundaries and re.search(r"\.click\(", ast.unparse(node)):
        smells.append("ACTION_WITHOUT_CHECK")
    markers = " ".join(ast.unparse(d) for d in getattr(node, "decorator_list", []))
    parameters = []
    for deco in getattr(node, "decorator_list", []):
        if isinstance(deco, ast.Call) and (_expr_name(deco.func) or "").endswith("parametrize") and len(deco.args) >= 2:
            values = deco.args[1]
            if isinstance(values, (ast.List, ast.Tuple)):
                parameters += [ast.unparse(v) for v in values.elts]
    return TestFacts(test_id=test_id, path=rel, language="python", oracles=oracles, assertions=len(asserts), doubles=tuple(doubles),
                     boundaries=tuple(sorted(boundaries)), simulated=tuple(sorted(simulated)), surfaces=tuple(sorted(surfaces)),
                     smells=tuple(dict.fromkeys(smells)), declared_level=_level(rel, markers),
                     oracle_signature=" ; ".join(sorted(_norm(s) for s in signature)), parameters=tuple(parameters),
                     body_signature=_python_body(node))


def _checks(statements) -> bool:
    """Whether a branch asserts, fails or raises on every visit (so the condition does not skip checking)."""
    from assertiva.pytest_audit import _expr_name

    for statement in statements:
        for item in ast.walk(statement):
            if isinstance(item, (ast.Assert, ast.Raise)):
                return True
            if isinstance(item, ast.Call):
                name = _expr_name(item.func) or ""
                leaf = name.split(".")[-1]
                if leaf.startswith(("assert", "fail")) or leaf in ("raises", "warns") or name in ("pytest.skip", "self.skipTest"):
                    return True
    return False


def _python_body(node) -> str:
    body = node.body[1:] if node.body and isinstance(node.body[0], ast.Expr) and isinstance(node.body[0].value, ast.Constant) else node.body
    return ast.dump(ast.Module(body=body, type_ignores=[]), annotate_fields=False)


def _within(node, statements) -> bool:
    return any(node is n for s in statements for n in ast.walk(s))


def _ancestors(node, parents, stop):
    while node in parents and node is not stop:
        node = parents[node]
        yield node


# --- JavaScript / TypeScript -------------------------------------------------------------------

_JS_FILE = re.compile(r"(\.(test|spec)\.[cm]?[jt]sx?$)|(/__tests__/.+\.[cm]?[jt]sx?$)|(/(e2e|cypress)/.+\.(cy\.)?[cm]?[jt]sx?$)")
_JS_TEST = re.compile(r"\b(?:test|it)(?:\.(?:only|concurrent|fails))?\s*\(\s*([\"'`])(?P<name>(?:(?!\1).)*)\1\s*,", re.S)
_JS_EACH = re.compile(r"\b(?:test|it)\.each\s*\(\s*\[", re.S)
_JS_BODY = re.compile(r"=>\s*\{|\bfunction\b[^{]*\{")
_JS_EXPECT = re.compile(r"\bexpect\s*\((?P<arg>[^;]*?)\)\s*(?:\.\s*(?:not|resolves|rejects|soft))*\s*\.\s*(?P<matcher>\w+)\s*\((?P<expected>[^;\n]*)")
_JS_ASSERTION = re.compile(r"\bexpect\s*\(|\bassert(?:\.\w+)?\s*\(|\bcy\.\w+\([^)]*\)\.should\(")
_JS_ORACLES = {
    "toBeDefined": "EXISTENCE", "toBeTruthy": "TRUTHY", "toBeFalsy": "TRUTHY", "toBeInTheDocument": "EXISTENCE", "toBeVisible": "EXISTENCE",
    "toBeAttached": "EXISTENCE", "toExist": "EXISTENCE", "toMatchSnapshot": "SNAPSHOT", "toMatchInlineSnapshot": "SNAPSHOT",
    "toHaveScreenshot": "SNAPSHOT", "toThrowErrorMatchingSnapshot": "SNAPSHOT", "toHaveBeenCalled": "INTERACTION",
    "toHaveBeenCalledWith": "INTERACTION", "toHaveBeenCalledTimes": "INTERACTION", "toHaveBeenLastCalledWith": "INTERACTION",
    "toHaveBeenNthCalledWith": "INTERACTION",
}


def _js_files(root: Path) -> list[Path]:
    return _walk(root, lambda p: bool(_JS_FILE.search("/" + p.relative_to(root).as_posix())))


def _js_oracle(arg: str, matcher: str, expected: str) -> str:
    if matcher in _JS_ORACLES:
        return _JS_ORACLES[matcher]
    if matcher in ("toThrow", "toThrowError"):
        return "SPECIFIC_ERROR" if expected.strip(" )") else "BROAD_ERROR"
    if matcher == "not" or matcher in ("toBeNull", "toBeUndefined"):
        return "VALUE"
    if re.search(r"\.status(Code)?\s*(\(\))?\s*$", arg.strip()) and matcher in ("toBe", "toEqual", "toStrictEqual"):
        return "STATUS_ONLY"
    if matcher in ("toBeGreaterThan", "toBeGreaterThanOrEqual", "toBeLessThan") and expected.strip(" )") in ("0", "-1"):
        return "EXISTENCE"
    return "VALUE"


def _javascript_facts(root: Path) -> list[TestFacts]:
    out = []
    for path in _js_files(root):
        try:
            text = path.read_text(encoding="utf-8", errors="replace")
        except OSError:
            continue
        rel = path.relative_to(root).as_posix()
        clean = _strip_strings_and_comments(text)
        file_doubles = re.findall(r"\b(?:vi|jest)\.mock\(\s*[\"'`]([^\"'`]+)", text)
        file_level = _level(rel, "e2e" if re.search(r"@playwright/test|\bcy\.", text) else "")
        msw = bool(re.search(r"setupServer\(|setupWorker\(|from [\"']msw[\"']", text))
        retries = bool(re.search(r"retries\s*:\s*[1-9]|retryTimes\(|\.retry\(", text))
        for match in _JS_TEST.finditer(clean):
            name = text[match.start("name"):match.end("name")]
            header = _JS_BODY.search(clean, match.end(), match.end() + 400)  # `=> {` or `function (...) {`, not `({ page })`
            if header is None:
                continue
            span = _block(clean, header.end() - 1)
            if span is None:
                continue
            body, body_clean = text[span[0]:span[1]], clean[span[0]:span[1]]
            out.append(_js_test(f"{rel} › {name}", rel, body, body_clean, file_doubles, file_level, msw, retries))
        for match in _JS_EACH.finditer(clean):  # literal rows of test.each([...])
            start = match.end() - 1
            depth, end = 0, None
            for i in range(start, len(clean)):
                depth += {"[": 1, "]": -1}.get(clean[i], 0)
                if depth == 0:
                    end = i
                    break
            if end is None:
                continue
            rows = [_norm(r) for r in re.findall(r"\[[^\[\]]*\]|\{[^{}]*\}", text[start + 1:end])]
            if rows:
                out.append(TestFacts(test_id=f"{rel} › each@{text.count(chr(10), 0, start) + 1}", path=rel, language="javascript",
                                     oracles=("VALUE",), parameters=tuple(rows), declared_level=file_level))
    return out


def _js_test(test_id, rel, body, body_clean, file_doubles, level, msw, retries) -> TestFacts:
    oracles, signature, smells = [], [], []
    for m in _JS_EXPECT.finditer(body):
        oracle = _js_oracle(m.group("arg"), m.group("matcher"), m.group("expected"))
        oracles.append(oracle)
        signature.append(_norm(m.group(0)))
        if re.fullmatch(r"\s*(true|false|\d+|[\"'][^\"']*[\"'])\s*", m.group("arg")) and m.group("matcher") in ("toBe", "toEqual"):
            smells.append("TAUTOLOGY")
    if re.search(r"\bgetBy\w+\(|\bfindBy\w+\(", body):
        oracles.append("EXISTENCE")  # Testing Library queries throw when the element is missing
    if re.search(r"\.should\(\s*[\"'](have\.text|contain|have\.value|eq|equal)", body):
        oracles.append("VALUE")
    elif re.search(r"\.should\(\s*[\"'](exist|be\.visible)", body):
        oracles.append("EXISTENCE")
    doubles = list(file_doubles) + re.findall(r"\b(?:vi|jest)\.spyOn\(\s*([\w.]+)\s*,\s*[\"'`](\w+)", body)
    doubles = [d if isinstance(d, str) else ".".join(d) for d in doubles]
    boundaries, simulated, surfaces = set(), set(), set()
    if re.search(r"\bpage\.|\bcy\.|\bbrowser\.", body):
        boundaries.add("BROWSER")
    if re.search(r"\brender\(|\bmount\(", body):
        boundaries.add("BROWSER")
        simulated.add("BROWSER")  # a simulated DOM (jsdom/happy-dom), not a real browser
    if re.search(r"\bfetch\(|\baxios\.|\brequest\(\s*app|\bsupertest|\brequest\.(get|post|put|patch|delete)\(", body):
        boundaries.add("HTTP")
    if re.search(r"\bpage\.route\(|\bcy\.intercept\([^)]*,", body) or msw or any(re.search(r"api|http|fetch|client|axios", d, re.I) for d in doubles):
        boundaries.add("HTTP")
        simulated.add("HTTP")
    for m in _JS_EXPECT.finditer(body):
        arg = m.group("arg")
        if re.search(r"\.status(Code)?\b", arg):
            surfaces.add("RESPONSE_STATUS")
        elif re.search(r"\.body\b|\.json\(\)|\.data\b", arg):
            surfaces.add("RESPONSE_BODY")
        elif re.search(r"\bpage\b|locator|getBy|screen\.", arg):
            surfaces.add("UI")
        elif m.group("matcher").startswith("toHaveBeenCalled"):
            surfaces.add("INTERACTION")
        else:
            surfaces.add("RETURN")
    if _swallowed(body_clean, _JS_ASSERTION):
        smells.append("SWALLOWED_EXCEPTION")
    if re.search(r"waitForTimeout\(|new Promise\(\s*\(?\w*\)?\s*=>\s*setTimeout", body) and not _time_is_subject(test_id, body):
        smells.append("FIXED_WAIT")
    if _conditional_only(body_clean, _JS_ASSERTION):
        smells.append("CONDITIONAL_ASSERTION")
    for line in body.splitlines():
        if re.search(r"\.(resolves|rejects)\.", line) and not re.search(r"\b(await|return)\b", line):
            smells.append("UNAWAITED_ASYNC")
    if not oracles and re.search(r"\.(click|fill|press|type|check|tap)\(", body):
        smells.append("ACTION_WITHOUT_CHECK")
    if oracles and set(oracles) == {"SNAPSHOT"}:
        smells.append("SNAPSHOT_ONLY")
    if retries:
        smells.append("RETRY")
    if len(doubles) >= 4:
        smells.append("EXCESSIVE_MOCKING")
    return TestFacts(test_id=test_id, path=rel, language="javascript", oracles=tuple(dict.fromkeys(oracles)), assertions=len(signature),
                     doubles=tuple(doubles), boundaries=tuple(sorted(boundaries)), simulated=tuple(sorted(simulated)),
                     surfaces=tuple(sorted(surfaces)), smells=tuple(dict.fromkeys(smells)), declared_level=level,
                     oracle_signature=" ; ".join(sorted(signature)), body_signature=_norm(body))


# --- Kotlin / Java -----------------------------------------------------------------------------

_JVM_FILE = re.compile(r"/src/[A-Za-z]*[Tt]est[A-Za-z]*/.+\.(kt|java)$")
_JVM_TEST = re.compile(r"@(?:Test|ParameterizedTest|RepeatedTest|TestFactory)\b(?:\([^)]*\))?[\s\S]*?\b(?:fun|void)\s+`?(?P<name>[^\s(`]+)`?\s*\(", re.M)
_KOTEST = re.compile(r"""(?:\b(?:test|should|it|scenario|then)\(\s*"(?P<a>[^"]+)"\s*\)|^\s*"(?P<b>[^"]+)"\s*)\s*\{""", re.M)
_JVM_ASSERT = re.compile(r"\b(assert\w*|should\w*|verify|coVerify|fail|check|expectThat|expect|isEqualTo|containsExactly)\b\s*[({<]")
_JVM_ORACLES = [
    (re.compile(r"\bassertThrows\s*<\s*(?:java\.lang\.)?(Exception|Throwable|RuntimeException)\s*>|assertFailsWith\s*<\s*(Exception|Throwable)\s*>|"
                r"assertThrows\(\s*(Exception|Throwable|RuntimeException)(::class\.java|\.class)|shouldThrow\s*<\s*(Exception|Throwable)\s*>"), "BROAD_ERROR"),
    (re.compile(r"\bassertThrows\b|\bassertFailsWith\b|\bshouldThrow\b|expected\s*="), "SPECIFIC_ERROR"),
    (re.compile(r"\b(verify|coVerify|verifyNoInteractions|verifyNoMoreInteractions|confirmVerified)\b"), "INTERACTION"),
    (re.compile(r"\bassertEquals\s*\(\s*\d{3}\s*,\s*[\w.()]*status\w*(\(\))?\s*\)|\bstatus\(\)\s*\.\s*is\w+\(\s*\)|"
                r"status(Code)?(\(\))?\s*\)?\s*\.isEqualTo\(\s*\d{3}\s*\)|status(Code)?\s+shouldBe\s+\d{3}"), "STATUS_ONLY"),
    (re.compile(r"\bassertNotNull\b|\.isNotNull\(\)|shouldNotBeNull|assertExists\(\)|assertIsDisplayed\(\)|matches\(\s*isDisplayed\(\)\)"), "EXISTENCE"),
    (re.compile(r"\bassert(True|False)\s*\([^)]*(!=|==)\s*null|\bassert(True|False)\s*\(\s*null\s*(!=|==)"), "EXISTENCE"),
    # a predicate's boolean result checked exactly (assertTrue(accepts(x))) pins a value, like `assert accepts(x)`
    (re.compile(r"\bassert(True|False)\b|\.is(True|False)\(\)|shouldBe(True|False)"), "VALUE"),
    (re.compile(r"\bassert(Equals|Same|ArrayEquals|ContentEquals|Null|NotEquals|Contains|LinesMatch|IterableEquals)\b|\.isEqualTo\(|containsExactly|"
                r"\.hasSize\(|\bshould(Be|Contain|HaveSize|Equal)\b|assertText(Equals|Contains)|withText\(|\bfail\("), "VALUE"),
]


def _jvm_files(root: Path) -> list[Path]:
    return _walk(root, lambda p: p.suffix in (".kt", ".java") and bool(_JVM_FILE.search("/" + p.relative_to(root).as_posix())))


def _jvm_facts(root: Path) -> list[TestFacts]:
    out = []
    for path in _jvm_files(root):
        try:
            text = path.read_text(encoding="utf-8", errors="replace")
        except OSError:
            continue
        rel = path.relative_to(root).as_posix()
        clean = _strip_strings_and_comments(text)
        instrumented = "/src/androidTest/" in "/" + rel
        level = "E2E" if instrumented else _level(rel, " ".join(re.findall(r"@Tag\(\s*\"(\w+)\"", text))) or (
            "INTEGRATION" if re.search(r"@SpringBootTest|@DataJpaTest|@Testcontainers", text) else None)
        class_doubles = re.findall(r"@(?:Mock|MockK|RelaxedMockK|SpyK|MockBean)\b[\s\S]{0,80}?\b(?:lateinit\s+var|val|var|private|[A-Z]\w*)\s+(\w+)", text)
        robolectric = "RobolectricTestRunner" in text or "@Config(" in text
        found = []
        for m in _JVM_TEST.finditer(clean):
            name = text[m.start("name"):m.end("name")]
            depth, close = 1, None  # the parameter list, balanced; then `= expression` (Kotlin) or `{ block }`
            for i in range(m.end(), len(clean)):
                depth += {"(": 1, ")": -1}.get(clean[i], 0)
                if depth == 0:
                    close = i
                    break
            if close is None:
                continue
            rest = re.match(r"\s*(?::\s*[\w.<>?, ]+)?\s*(?:throws\s+[\w., ]+)?\s*(?P<open>[={])", clean[close + 1:])
            if rest is None:
                continue
            opener = close + 1 + rest.start("open")
            if clean[opener] == "=":
                end = clean.find("\n", opener)
                end = len(clean) if end < 0 else end
                body, body_clean = text[opener + 1:end], clean[opener + 1:end]
            else:
                span = _block(clean, opener)
                if span is None:
                    continue
                body, body_clean = text[span[0]:span[1]], clean[span[0]:span[1]]
            params = re.findall(r"@CsvSource\(\s*\{?([^)}]*)", text[m.start():m.end()])  # only this test's own annotations
            rows = tuple(_norm(r) for group in params for r in re.findall(r"\"([^\"]*)\"", group))
            found.append((f"{rel}::{name}", body, body_clean, rows))
        if "io.kotest" in text:
            for m in _KOTEST.finditer(clean):
                label = (m.group("a") or m.group("b") or "").strip()
                span = _block(clean, m.end() - 1)
                if span is None or not label:
                    continue
                found.append((f"{rel}::{label}", text[span[0]:span[1]], clean[span[0]:span[1]], ()))
        for test_id, body, body_clean, rows in found:
            out.append(_jvm_test(test_id, rel, body, body_clean, rows, class_doubles, level, instrumented, robolectric))
    return out


def _jvm_test(test_id, rel, body, body_clean, rows, class_doubles, level, instrumented, robolectric) -> TestFacts:
    oracles, signature, smells = [], [], []
    for statement in re.findall(r"[^\n;]*(?:assert|should|verify|check\(|isEqualTo|containsExactly|fail\(|andExpect)[^\n;]*", body):
        for pattern, oracle in _JVM_ORACLES:
            if pattern.search(statement):
                oracles.append(oracle)
                signature.append(_norm(statement))
                break
        if re.search(r"assertTrue\(\s*true\s*\)|assertEquals\(\s*(\w+)\s*,\s*\1\s*\)", statement):
            smells.append("TAUTOLOGY")
    doubles = [*class_doubles, *re.findall(r"\bmockk<(\w+)>|\bmock\(\s*(\w+)(?:::class|\.class)", body)]
    doubles = [d if isinstance(d, str) else next(x for x in d if x) for d in doubles]
    boundaries, simulated, surfaces = set(), set(), set()
    if instrumented:
        boundaries.add("DEVICE")
    if robolectric:
        boundaries.add("DEVICE")
        simulated.add("DEVICE")  # Robolectric simulates the Android framework on the JVM
    if re.search(r"onNode|composeTestRule|onView\(", body):
        boundaries.add("BROWSER" if False else "DEVICE")
        if not instrumented:
            simulated.add("DEVICE")
    if re.search(r"MockWebServer|WireMock|MockEngine", body):
        boundaries.add("HTTP")
        simulated.add("HTTP")
    if re.search(r"\bmockMvc\.|webTestClient|TestRestTemplate|\.exchange\(", body):
        boundaries.add("HTTP")
    if re.search(r"inMemoryDatabaseBuilder|Repository|EntityManager|jdbcTemplate|\.save\(", body):
        boundaries.add("DATABASE")
    if any(re.search(r"repo|dao|api|client|service|gateway", d, re.I) for d in doubles):
        simulated.update(b for b in ("HTTP", "DATABASE") if any(re.search(k, d, re.I) for d in doubles for k in ((r"api|client|gateway",) if b == "HTTP" else (r"repo|dao",))))
        boundaries.update(simulated)
    for statement in signature:
        if re.search(r"status|isOk\(\)|is4xx|is5xx", statement):
            surfaces.add("RESPONSE_STATUS")
        elif re.search(r"verify|coVerify", statement):
            surfaces.add("INTERACTION")
        elif re.search(r"onNode|onView|assertIsDisplayed|assertText", statement):
            surfaces.add("UI")
        else:
            surfaces.add("RETURN")
    if "SPECIFIC_ERROR" in oracles or "BROAD_ERROR" in oracles:
        surfaces.add("EXCEPTION")
    if _swallowed(body_clean, _JVM_ASSERT):
        smells.append("SWALLOWED_EXCEPTION")
    if re.search(r"Thread\.sleep\(|SystemClock\.sleep\(", body) and not _time_is_subject(test_id, body):
        smells.append("SLEEP")
    if _conditional_only(body_clean, _JVM_ASSERT):
        smells.append("CONDITIONAL_ASSERTION")
    if re.search(r"GlobalScope\.launch|\blaunch\s*\{", body) and not re.search(r"\.join\(\)|advanceUntilIdle|runCurrent|awaitItem|\.await\(", body):
        smells.append("UNAWAITED_ASYNC")
    if not oracles and re.search(r"performClick\(\)|perform\(\s*click\(\)", body):
        smells.append("ACTION_WITHOUT_CHECK")
    if len(doubles) >= 4:
        smells.append("EXCESSIVE_MOCKING")
    return TestFacts(test_id=test_id, path=rel, language="jvm", oracles=tuple(dict.fromkeys(oracles)), assertions=len(signature),
                     doubles=tuple(doubles), boundaries=tuple(sorted(boundaries)), simulated=tuple(sorted(simulated)),
                     surfaces=tuple(sorted(surfaces)), smells=tuple(dict.fromkeys(smells)), declared_level=level,
                     oracle_signature=" ; ".join(sorted(signature)), parameters=rows, body_signature=_norm(body))


def collect(root: str | Path) -> tuple[list[TestFacts], dict[str, list[str]]]:
    """Facts for every language with tests in the project, and each extractor's limits."""
    from dataclasses import replace

    root = Path(root)
    facts, limits = [], {}
    for language, extractor in (("python", _python_facts), ("javascript", _javascript_facts), ("jvm", _jvm_facts)):
        found = extractor(root)
        if found:
            facts += found
            limits[language] = LIMITS[language]
    components: dict[str, str] = {}

    def component(rel: str) -> str:
        folder = (root / rel).parent
        key = folder.as_posix()
        if key not in components:
            here = folder
            while here != root and here != here.parent and not any((here / m).is_file() for m in _MANIFESTS):
                here = here.parent
            components[key] = here.relative_to(root).as_posix() if here != root else "."
        return components[key]

    return [replace(f, component=component(f.path)) for f in facts], limits
