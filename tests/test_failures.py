"""Where a failure came from and which failures share a cause, from the failure text runners report."""

from __future__ import annotations

from assertiva.failures import INFRASTRUCTURE, PRODUCT, TEST, UNKNOWN, clusters, origin, raise_site

PY_PRODUCT = """    def test_total():
>       assert total([1, "x"]) == 1
tests/test_cart.py:4:
_ _ _ _
    def total(items):
>       return sum(items)
E       TypeError: unsupported operand type(s) for +: 'int' and 'str'
shop/cart.py:2: TypeError"""
PY_ASSERTION = """>       assert total([1, 2]) == 4
E       assert 3 == 4
tests/test_cart.py:7: AssertionError"""
PY_TEST_BUG = """>       assert totl([1]) == 1
E       NameError: name 'totl' is not defined
tests/test_cart.py:9: NameError"""
PY_INFRA = """E   psycopg.OperationalError: connection failed: Connection refused
tests/test_orders.py:12: OperationalError"""
JS_ASSERTION = """expect(received).toBe(expected) // Object.is equality
Expected: 1500
Received: undefined
    at Object.<anonymous> (src/pricing.test.js:4:39)"""
JVM_PRODUCT = """java.lang.ArithmeticException: / by zero
	at dev.shop.Pricing.rate(Pricing.java:14)
	at dev.shop.PricingTest.rate(PricingTest.java:9)"""
JVM_ASSERTION = """org.opentest4j.AssertionFailedError: expected: <1500> but was: <0>
	at dev.shop.PricingTest.discount(PricingTest.java:12)"""


def test_a_failure_raised_by_product_code_is_product():
    assert origin(PY_PRODUCT, ["tests/test_cart.py"])[0] == PRODUCT
    assert raise_site(PY_PRODUCT) == ("TypeError", "shop/cart.py:2")
    assert origin(JVM_PRODUCT)[0] == PRODUCT and raise_site(JVM_PRODUCT)[1] == "Pricing.java:14"


def test_an_assertion_that_did_not_hold_stays_unknown_between_product_and_test():
    for text in (PY_ASSERTION, JS_ASSERTION, JVM_ASSERTION):
        verdict, why = origin(text)
        assert verdict == UNKNOWN and "expectation" in why


def test_test_code_errors_and_environment_failures_are_named():
    assert origin(PY_TEST_BUG)[0] == TEST
    assert origin(PY_INFRA)[0] == INFRASTRUCTURE
    assert origin("Error: browserType.launch: Executable doesn't exist at /ms-playwright/chromium")[0] == INFRASTRUCTURE
    assert origin(None)[0] == UNKNOWN and origin("something odd happened")[0] == UNKNOWN


def test_failures_cluster_by_raise_site_not_by_message_text():
    other_message = PY_PRODUCT.replace("'int' and 'str'", "'int' and 'NoneType'")
    found = clusters([("a", PY_PRODUCT), ("b", other_message), ("c", PY_ASSERTION), ("d", PY_TEST_BUG)])
    assert found == [{"exception": "TypeError", "raised_at": "shop/cart.py:2", "count": 2, "invocations": ["a", "b"],
                      "basis": "INFERRED: same exception type raised at the same place"}]
    # the same words at different sites are different causes
    assert clusters([("a", PY_ASSERTION), ("b", PY_ASSERTION.replace(":7:", ":17:"))]) == []


def test_a_product_file_whose_name_ends_a_test_files_name_is_still_product():
    # found end to end: pricing.py and tests/test_pricing.py share the characters "pricing.py"
    text = ("E           TypeError: unsupported operand type(s) for //: 'int' and 'NoneType'\n\npricing.py:6: TypeError")
    assert origin(text, ["tests/test_pricing.py"])[0] == PRODUCT
    assert origin(text.replace("pricing.py:6", "tests/test_pricing.py:6"), ["tests/test_pricing.py"])[0] != PRODUCT


# --- AG-01 / AG-02 / AG-07: frames outside the project, environment permissions, Windows paths ---------------

SITE_PERMISSION = ("/usr/lib/python3/site-packages/requests/adapters.py:519: PermissionError\n"
                   "E PermissionError: [Errno 13] Permission denied: '/tmp/x'")
TMP_PATH_ACL = ("C:/venv/Lib/site-packages/_pytest/pathlib.py:175: PermissionError\n"
                "E PermissionError: [WinError 5] Access is denied: 'C:/Users/u/AppData/Local/Temp/pytest-of-u'")
PRODUCT_PERMISSION = ("    def save(path):\n>       open(path, 'w').write('x')\n"
                      "E       PermissionError: [Errno 13] Permission denied: 'out/report.txt'\nshop/export.py:7: PermissionError")
PRODUCT_THROUGH_STDLIB = ("shop/cart.py:12: in total\n    return Decimal(text)\n"
                          "/usr/lib/python3.12/_pydecimal.py:612: InvalidOperation\nE   decimal.InvalidOperation")
ONLY_LIBRARY = "/home/u/.venv/lib/python3.12/site-packages/yaml/constructor.py:60: ValueError\nE   ValueError: bad"


def test_drawlab_reproducers_frames_in_site_packages_are_not_product():
    assert origin(SITE_PERMISSION)[0] != PRODUCT
    assert origin(TMP_PATH_ACL)[0] in (INFRASTRUCTURE, UNKNOWN)


def test_a_permission_error_raised_outside_the_project_is_the_environment():
    kind, why = origin(TMP_PATH_ACL)
    assert kind == INFRASTRUCTURE and "permission" in why.lower()


def test_a_permission_error_in_the_projects_own_code_stays_product():
    # negative control: the product really fails to write; not moved to the environment
    assert origin(PRODUCT_PERMISSION)[0] == PRODUCT


def test_the_innermost_project_frame_decides_when_the_raise_is_in_the_stdlib():
    kind, why = origin(PRODUCT_THROUGH_STDLIB)
    assert kind == PRODUCT and "shop/cart.py:12" in why


def test_a_failure_only_in_a_library_is_unknown_not_product():
    kind, why = origin(ONLY_LIBRARY)
    assert kind == UNKNOWN and "outside the project" in why


def test_windows_paths_keep_their_file_name_in_signatures_and_their_drive_in_sites():
    from assertiva.history import fingerprint

    relative = r"venv\Lib\site-packages\_pytest\pathlib.py:228: PermissionError"
    assert "at pathlib.py:228" in fingerprint(relative)[1] and "venvpathlib" not in fingerprint(relative)[1]
    dotted = r"..\venv\Lib\site-packages\_pytest\pathlib.py:228: in make_numbered_dir"
    assert "..pathlib" not in fingerprint(dotted)[1]
    assert raise_site(r"C:\venv\Lib\site-packages\_pytest\pathlib.py:175: PermissionError")[1] == \
        "C:/venv/Lib/site-packages/_pytest/pathlib.py:175"


F07_GIT = ("    def revision():\n>       return subprocess.run(['git', 'rev-parse', 'HEAD'], check=True).stdout\n"
           "src/ledgerlite/release.py:6: in revision\n"
           "E   subprocess.CalledProcessError: Command '['git', 'rev-parse', 'HEAD']' returned non-zero exit status 128.\n"
           "/usr/lib/python3.12/subprocess.py:571: CalledProcessError")


def test_git_without_a_repository_is_the_environment_not_the_product():
    # AG-01 as reproduced in the F07 fixture: the engine's copy has no .git, so a test that needs one fails there
    assert origin(F07_GIT)[0] == INFRASTRUCTURE
    other = F07_GIT.replace("exit status 128", "exit status 1")  # control: another git failure is not assumed environmental
    assert origin(other)[0] == PRODUCT


# --- pinned by the self-mutation run of failures.py (behavior that surviving mutants changed unnoticed) -------------

def test_explicit_test_paths_decide_whether_a_frame_is_test_code():
    # a helper outside any test naming convention is test code only because the run names it as a test path
    message = "E   NameError: name 'x' is not defined\nqa/checks/pricing_checks.py:4: NameError"
    assert origin(message)[0] == PRODUCT
    assert origin(message, ["qa/checks/pricing_checks.py"])[0] == TEST
    assert origin(message, ["checks/pricing_checks.py"])[0] == TEST  # a trailing part of the path, on whole components
    assert origin(message, ["ricing_checks.py"])[0] == PRODUCT  # never a partial component


def test_an_error_in_test_code_that_is_not_a_code_error_stays_unknown():
    message = "E   ValueError: bad fixture data\ntests/test_cart.py:9: ValueError"
    assert origin(message)[0] == UNKNOWN  # a broken test or a product change it relied on: not decided
    assert origin("E   NameError: name 'x'\ntests/test_cart.py:9: NameError")[0] == TEST


def test_clusters_list_the_largest_cause_first_and_drop_singletons():
    a = "shop/a.py:3: TypeError\nE TypeError: x"
    b = "shop/b.py:7: KeyError\nE KeyError: y"
    found = clusters([("t1", a), ("t2", b), ("t3", b), ("t4", b), ("t5", a), ("t6", "shop/c.py:1: OSError")])
    assert [(c["raised_at"], c["count"]) for c in found] == [("shop/b.py:7", 3), ("shop/a.py:3", 2)]
    assert clusters([("t1", a), ("t2", a)], minimum=3) == []
