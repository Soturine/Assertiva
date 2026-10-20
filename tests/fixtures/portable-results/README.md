# Portable results fixtures

Produced by running real tools on `test_shop.py` (one pass, one failure, one skip, a two-row parameterized test and a
test that fails once and passes on rerun):

```
pytest -p no:cacheprovider --reruns 1 --ctrf ctrf-report.json --alluredir allure-results
```

with pytest 9.1.1, pytest-json-ctrf 0.6.1, allure-pytest 2.16.2 and pytest-rerunfailures 16.7 on 2026-10-20.
The only edits after generation: the host name was replaced by `build-host` and absolute paths by `/work/project/`.
