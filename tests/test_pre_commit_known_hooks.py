"""Remote pre-commit hooks whose id differs from the tool they run (dogfood: SotuHire 2026-11).

ruff-pre-commit's ``ruff-check``/``ruff-format`` hooks have no ``entry`` in the project
config; CI ran ``ruff check .`` and ``ruff format --check .`` and Assertiva still reported
LOCAL_CHECK_NOT_OBSERVED_IN_CI (high) because the hook kept the tool name ``ruff-check``.
"""

from assertiva.adapters.pre_commit import PreCommitAdapter
from assertiva.verification import VerificationKind, discover_surface, surface_findings
from conftest import write

RUFF_HOOKS = """\
repos:
  - repo: https://github.com/astral-sh/ruff-pre-commit
    rev: v0.16.1
    hooks:
      - id: ruff-check
        args: [--fix]
      - id: ruff-format
"""

WORKFLOW = """\
name: CI
on: [push]
jobs:
  quality:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - run: ruff check .
      - run: ruff format --check .
"""


def test_known_remote_hook_ids_map_to_their_tool(tmp_path):
    write(tmp_path / ".pre-commit-config.yaml", RUFF_HOOKS)

    checks = {c.check_id: c for c in PreCommitAdapter().discover(tmp_path)}

    assert checks["pre-commit:ruff-check"].tool == "ruff"
    assert checks["pre-commit:ruff-check"].kind is VerificationKind.LINT
    assert checks["pre-commit:ruff-format"].tool == "ruff format"
    assert checks["pre-commit:ruff-format"].kind is VerificationKind.FORMAT
    # The command was inferred, not read: it stays None and the limitation says so.
    assert checks["pre-commit:ruff-check"].command is None
    assert any("inferred from the hook id" in lim for lim in checks["pre-commit:ruff-check"].limitations)


def test_ci_running_the_same_ruff_checks_covers_the_hooks(tmp_path):
    write(tmp_path / ".pre-commit-config.yaml", RUFF_HOOKS)
    write(tmp_path / ".github" / "workflows" / "ci.yml", WORKFLOW)

    surface = discover_surface(tmp_path)

    assert not any(f.code == "LOCAL_CHECK_NOT_OBSERVED_IN_CI" for f in surface_findings(surface))


def test_ci_without_the_format_check_still_reports_it(tmp_path):
    write(tmp_path / ".pre-commit-config.yaml", RUFF_HOOKS)
    write(tmp_path / ".github" / "workflows" / "ci.yml", WORKFLOW.replace("      - run: ruff format --check .\n", ""))

    [finding] = [f for f in surface_findings(discover_surface(tmp_path)) if f.code == "LOCAL_CHECK_NOT_OBSERVED_IN_CI"]

    assert finding.evidence["checks"] == ["pre-commit:ruff-format"]


def test_a_local_hook_reusing_the_id_is_not_reattributed(tmp_path):
    write(
        tmp_path / ".pre-commit-config.yaml",
        "repos:\n  - repo: local\n    hooks:\n      - id: ruff-check\n        name: custom\n        language: system\n",
    )

    [check] = PreCommitAdapter().discover(tmp_path)

    assert check.tool == "ruff-check"
    assert check.kind is VerificationKind.UNKNOWN
