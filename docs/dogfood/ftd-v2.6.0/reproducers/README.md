# Synthetic reproducers

Self-contained, stdlib-only projects. Copy one to a temporary directory, initialize git (Assertiva records the
revision), then run the commands. Observed results are Assertiva 1.1.0 (tag `v1.1.0`), Cosmic Ray 8.9.0,
CPython 3.12.10 on Windows 11. These folders are not collected by Assertiva's own suite (`testpaths = ["tests"]`).

## sibling-helper — AXF-FTD-01

`tests/test_calc.py` imports `tests/helper.py` by its bare name, which works under `unittest discover -s tests`
(the start directory is put on `sys.path`) and nowhere else.

```text
python -m unittest discover -s tests          # OK, 2 tests
python -m unittest tests.test_calc            # ImportError: No module named 'helper'
assertiva audit . --execute --mutate calc.py --mutate-tests tests/test_calc.py --mutation-tool cosmic-ray
    -> MUTATION_RUN_NOT_COMPLETED: the selected tests do not pass on this state before mutation; no mutant was run
assertiva audit . --execute --mutate calc.py --mutate-tests tests --mutation-tool cosmic-ray      (control)
    -> unittest discover --failfast -s tests; 42 mutants: 36 killed, 6 survived
```

## helper-fakes — AXF-FTD-02 and AXF-FTD-03

`tests/test_history.py` defines `HistoryTransport(FakeTransport)`, a test double whose base is a plain class
imported from `tests/test_transport.py`, with a transport method named `test_case_history`. `make_big.py`
writes a module whose single function plans thousands of mutants.

```text
python make_big.py
python -m unittest discover -s tests -v       # 2 tests; HistoryTransport is not collected
assertiva audit . --execute --mutate big.py --mutate-tests tests --mutation-tool cosmic-ray
    -> TEST_CLASS_COLLECTION_UNKNOWN: tests/test_history.py::HistoryTransport   (native run: 2 invocations)
    -> MUTATION_RUN_NOT_COMPLETED: 7082 mutants planned exceed the budget of 300 test-suite runs
```

Region selection proof of concept (Cosmic Ray only, no Assertiva change):

```toml
[cosmic-ray]
module-path = "big.py"
timeout = 30.0
excluded-modules = []
test-command = "python -m unittest discover -s tests"

[cosmic-ray.distributor]
name = "local"

[cosmic-ray.filters.line-filter]
lines = { "big.py" = ["3-6"] }
```

```text
cosmic-ray init cr.toml s.sqlite        # 7082 work items
cr-filter-lines --config cr.toml s.sqlite
                                        # 236 left to run, the rest recorded as skipped
```
