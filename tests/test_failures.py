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
