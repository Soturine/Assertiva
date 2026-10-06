# Dependency reproducibility for a library

## Context
The project is a Python library published to PyPI and installed by other projects. `pyproject.toml` declares `requires-python = ">=3.10"` and dependencies as ranges (`httpx>=0.25,<1`, `pydantic>=2.4,<3`). There is no lockfile. CI installs with `pip install -e .[test]` on Python 3.12 only, so every run resolves the newest compatible versions.

## Prompt / task
Recommend how to improve dependency reproducibility and the evidence CI provides about supported dependency versions.

## Expected
- justify recommendations from the library's consumption model (consumers resolve the declared ranges);
- consider declared compatible ranges together with constrained/reproducible CI environments, minimum-supported and latest-compatible dependency runs, and the declared Python floor;
- if a lockfile is mentioned, scope it to development/CI reproducibility and explain why it does not represent what consumers install.

## Prohibited
- recommend committing a lockfile as the universal or primary fix;
- recommend pinning the published dependency ranges to exact versions.

## Pass
Recommendations follow from how the project is delivered and consumed, not from a generic checklist.
