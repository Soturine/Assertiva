# Entry audit — Assertiva 0.10.0 (Reliability, Portfolio Assurance & Continuous Dogfood)

Recorded 2026-10-30, before any engine change. Every number below names the revision it was measured at.

## Repository state

| Item | Value |
| --- | --- |
| `origin/main` | `cf5cb7d0c0893f609df970911a28f43ed0bba83d` (= `release/0.9.0`), 261 commits; not branch-protected (GitHub API: 404 "Branch not protected") |
| Published release | `v0.9.0`, GitHub Release 2026-10-20 (wheel + sdist), not PyPI; `pyproject.toml` version `0.9.0`, `requires-python >=3.11`, one runtime dependency (`PyYAML>=6.0`) |
| Implementation branch | `feature/assertiva-0.10.0-hardening`, created from `origin/main` at `cf5cb7d` |
| PR #1 | open, not draft: `docs/tcc-dogfood-evidence-20261025` at `6a375ec`, 10 commits ahead of `main`, 14 files, 513 insertions, documentation only (research, eval cases, index lines). One review: GitHub Advanced Security, 4 inline "prompt injection risk" comments on `evals/cases/*` (see SEC-EVAL-01) |
| DrawLab M10 branch | `docs/dogfood-drawlab-m10` at `5685523`, 3 commits ahead, no PR, 42 files, 1949 insertions: gap register AG-01..AG-13, agent-vs-engine notes, F07 skill-eval fixture, 8 `DRAWLAB_*` eval cases and a results folder. CI run 41082811654 on it: success |
| Issues | none |
| CI | `.github/workflows/ci.yml` only: `on: push` (every branch), `pull_request`, `workflow_dispatch`; `permissions: contents: read`; no `pull_request_target`. Seven jobs (validate, browser, java, …). `[skip ci]` in the head commit message skips `push` and `pull_request` runs of this workflow ([GitHub docs](https://docs.github.com/en/actions/how-tos/manage-workflow-runs/skip-workflow-runs)); `workflow_dispatch` is manual only |

## Baseline at `cf5cb7d` (Windows 11 Pro 10.0.26200, Python 3.12.10, pytest 9.1.1, xdist 3.8.0, Node 24.19.0)

| Suite | Command | Result | Wall time |
| --- | --- | --- | --- |
| Fast/core | `pytest -q -m "not integration and not artifact" -n auto` | **807 passed, 3 skipped** | 39.6 s |
| Integration + artifact (no browser, no JVM) | `pytest -q -n auto -m "(integration or artifact) and not browser and not jvm"` | **137 passed, 9 skipped** | 272 s |
| Browser, JVM | not run locally: no JDK on this machine (`java: command not found`); Playwright browsers not installed | NOT_RUN | — |

Docker 29.8.2 and WSL (Ubuntu 24.04) are available for Linux runs; Django and Cosmic Ray are not installed in the host interpreter (their integration tests skip unless `ASSERTIVA_REQUIRE_*` is set).

## Architecture as read (CLI → report)

`assertiva/cli.py` (`audit`, `improve`) → `audit.py` (static inventory, Verification Surface, optional `--execute` measurement in a disposable copy made by `workspace.snapshot`, read-only fingerprint guard) → adapters (`adapters/*`: runners, CI providers, packaging, mutation, imports) → `evidence.py` / `models.py` (records with provenance) → `effectiveness.py` + `adapters/test_facts.py` (cross-language test facts and candidates) → `report.py` / `report_html.py` / `report_i18n.py` (JSON + HTML, EN/PT-BR). Processes run through `process.run_command` (argument lists, own process group, tree kill on timeout, output to files, digest). No `shell=True` anywhere in `assertiva/`.

## Risks found while reading (each becomes a matrix row with a reproducer)

1. **Package closure imports project modules** (`adapters/python_package.py::_CLOSURE_PROBE`, `pkgutil.walk_packages` + `import_module`): an unguarded `__main__` or any module with import-time effects runs during artifact qualification (AX-E01). Reproduced with a canary file.
2. **Raw launch of a project's wrapper script** (`adapters/commands.py::reproduction_plan`): a CI step `./gradlew assembleDebug testDebugUnitTest` is not accepted by the Gradle adapter (not all tasks are test tasks), so it falls through to a raw launch of `./gradlew` — `[WinError 2]` on Windows (TCC-A16) and, on POSIX, execution of the committed `gradle-wrapper.jar` the Gradle adapter otherwise never runs (new ENG-01).
3. **Eval harness copies follow links** (`evals/semantic.py`: `shutil.copytree` default, `workspace_copy` with `is_file()`): a link in a fixture brings an outside file into the evaluated agent's workspace (new SEC-EVAL-02).
4. **Case text reaches the agent unframed** (`agent_context`): PR #1 review comments; the only boundary is prose in the Tools section (SEC-EVAL-01).
5. **Failure origin** (`failures.py::origin`): any non-test frame is PRODUCT, including site-packages; no permission patterns (AG-01/02).
6. **CI scope** (`ci.py::path_selected_by_ci`, `adapters/github_actions.py`): `defaults.run.working-directory` is ignored and step `working-directory` is not applied to scopes (TCC-A01).

`module_available` (`process.py`) imports only tool modules (build backends, `coverage`, `cosmic_ray`) from a scratch directory with the start directory removed from `sys.path`; it was reviewed and is not a project-code import.

## Constraints for this work

- Owner rules (persisted): no AI attribution in commits/PRs; no employer-internal names anywhere; semantic eval agent runs need the owner's budget approval first; no merge to `main`, tag or release without explicit authorization.
- Audited projects (TCC, DrawLab, Derivanta Engine and others) are not modified or re-audited here; their dogfood reports are inputs. Fixtures are synthetic.
- Intermediate pushes use `[skip ci]`; the final push does not.
