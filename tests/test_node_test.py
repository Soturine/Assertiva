"""TCC-A03: Node's built-in test runner, run for real (the machine's Node; nothing installed)."""

import json
import os
import shutil

import pytest

from assertiva.adapters.ci_common import command_check
from assertiva.adapters.node_test import NodeTestAdapter, node_test_args
from assertiva.verification import GateMode, SupportLevel

from conftest import write

TESTS = """const test = require('node:test');
const assert = require('node:assert');
const { total } = require('../src/cart.js');

test('totals the cart', () => { assert.strictEqual(total([1, 2]), 3); });
test('rejects strings', () => { assert.throws(() => total(['x']), TypeError); });
test('rounds half up', () => { assert.strictEqual(total([0.5]), 1); });
test('not yet', { skip: 'pending rounding rule' }, () => {});
"""


def project(root, script="node --test", tests=TESTS):
    write(root / "package.json", json.dumps({"name": "cart", "scripts": {"test": script}}))
    write(root / "src" / "cart.js", "exports.total = (xs) => xs.reduce((a, b) => {\n"
                                    "  if (typeof b !== 'number') throw new TypeError('not a number');\n  return a + b;\n}, 0);\n")
    if tests:
        write(root / "test" / "cart.test.js", tests)
    return root


def test_the_runner_is_recognized_from_the_script_and_never_over_jest(tmp_path):
    assert NodeTestAdapter().supports(project(tmp_path / "a")) is SupportLevel.SUPPORTED
    jest = project(tmp_path / "b", script="jest")
    assert NodeTestAdapter().supports(jest) is SupportLevel.UNSUPPORTED
    both = project(tmp_path / "c")
    data = json.loads((both / "package.json").read_text())
    data["devDependencies"] = {"jest": "29"}
    (both / "package.json").write_text(json.dumps(data))
    assert NodeTestAdapter().supports(both) is SupportLevel.UNSUPPORTED


def test_ci_steps_and_script_arguments_are_read():
    check = command_check("gha", "c1", "node --test --test-name-pattern=cart test/", "ci.yml", GateMode.UNKNOWN, {})
    assert check.kind.value == "TEST" and check.tool == "node --test"
    assert NodeTestAdapter().reproduction_args(check) == ["--test-name-pattern=cart", "test/"]
    assert node_test_args("node --test --test-reporter=spec test/") == ["test/"]
    assert node_test_args("jest --ci") is None


needs_node = pytest.mark.skipif(not (os.environ.get("ASSERTIVA_NODE") or shutil.which("node")), reason="needs Node.js")


@pytest.mark.integration
@needs_node
def test_a_real_run_reports_each_outcome(tmp_path):
    run = NodeTestAdapter().run(project(tmp_path / "p"))
    outcomes = {inv.invocation_id.rsplit("::", 1)[-1]: inv.outcome.value for inv in run.invocations}
    assert outcomes["totals the cart"] == "PASSED" and outcomes["rejects strings"] == "PASSED"
    assert outcomes["rounds half up"] == "FAILED" and outcomes["not yet"] == "SKIPPED"
    assert run.status.value == "FAIL" and run.exit_code != 0 and run.metadata["provenance"] == "ENGINE_EXECUTED"
    failing = next(inv for inv in run.invocations if inv.invocation_id.endswith("rounds half up"))
    assert failing.message and "1" in failing.message


@pytest.mark.integration
@needs_node
def test_a_run_that_finds_no_tests_is_unknown_not_pass(tmp_path):
    run = NodeTestAdapter().run(project(tmp_path / "p", tests=None))
    assert run.status.value in ("UNKNOWN", "BLOCKED") and run.status.value != "PASS"
