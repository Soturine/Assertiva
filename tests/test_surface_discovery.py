"""Verification Surface discovery: every check, not only tests; unknown stays UNKNOWN."""

from assertiva.verification import GateMode, VerificationKind, VerificationOrigin, discover_surface, surface_findings

from conftest import write

WORKFLOW = """
name: CI
on: [push]
jobs:
  test:
    runs-on: ${{ matrix.os }}
    strategy:
      matrix:
        os: [ubuntu-latest, windows-latest]
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
      - run: python -m pip install -r requirements.txt
      - name: Unit tests
        run: pytest tests/unit -q
      - name: Lint
        run: ruff check .
      - name: Types
        run: mypy src
        continue-on-error: true
      - name: Package
        if: github.ref == 'refs/heads/main'
        run: |
          python -m build --wheel
          twine check dist/*
      - name: Project verification
        run: ./scripts/project-verify --strict
      - uses: example-org/compliance-action@v2
"""


def checks_by_command(root):
    return {check.command: check for check in discover_surface(root).checks if check.command}


def test_ci_steps_become_verification_checks_beyond_tests(tmp_path):
    write(tmp_path / ".github" / "workflows" / "ci.yml", WORKFLOW)
    checks = checks_by_command(tmp_path)
    assert checks["pytest tests/unit -q"].kind is VerificationKind.TEST
    assert checks["ruff check ."].kind is VerificationKind.LINT
    assert checks["mypy src"].kind is VerificationKind.TYPECHECK
    assert checks["python -m build --wheel\ntwine check dist/*"].kind is VerificationKind.PACKAGE
    assert all(check.origin is VerificationOrigin.CI for check in checks.values())


def test_setup_steps_are_not_counted_as_verification(tmp_path):
    write(tmp_path / ".github" / "workflows" / "ci.yml", WORKFLOW)
    commands = set(checks_by_command(tmp_path))
    assert "python -m pip install -r requirements.txt" not in commands
    tools = {check.tool for check in discover_surface(tmp_path).checks}
    assert "actions/checkout" not in tools


def test_unknown_custom_tooling_is_preserved_as_unknown(tmp_path):
    write(tmp_path / ".github" / "workflows" / "ci.yml", WORKFLOW)
    custom = checks_by_command(tmp_path)["./scripts/project-verify --strict"]
    assert custom.kind is VerificationKind.UNKNOWN
    assert custom.limitations
    action = next(c for c in discover_surface(tmp_path).checks if c.tool == "example-org/compliance-action")
    assert action.kind is VerificationKind.UNKNOWN


def test_gate_conditions_and_matrix_are_preserved(tmp_path):
    write(tmp_path / ".github" / "workflows" / "ci.yml", WORKFLOW)
    checks = checks_by_command(tmp_path)
    assert checks["mypy src"].gate is GateMode.ALLOWED_FAILURE
    assert checks["ruff check ."].gate is GateMode.UNKNOWN  # branch protection is not observable here
    package = checks["python -m build --wheel\ntwine check dist/*"]
    assert package.metadata["condition"] == "github.ref == 'refs/heads/main'"
    assert checks["pytest tests/unit -q"].metadata["matrix"] == {"os": ["ubuntu-latest", "windows-latest"]}


def test_hidden_hook_validation_failure(tmp_path):
    """A local hook validates something CI never runs: CI green does not cover it."""
    write(
        tmp_path / ".pre-commit-config.yaml",
        "repos:\n"
        "  - repo: local\n"
        "    hooks:\n"
        "      - id: check-translations\n"
        "        name: check translations\n"
        "        entry: python scripts/check_translations.py\n"
        "        language: system\n"
        "  - repo: https://github.com/astral-sh/ruff-pre-commit\n"
        "    rev: v0.6.0\n"
        "    hooks:\n"
        "      - id: ruff\n",
    )
    write(tmp_path / ".github" / "workflows" / "ci.yml", "on: [push]\njobs:\n  t:\n    steps:\n      - run: pytest -q\n      - run: ruff check .\n")
    surface = discover_surface(tmp_path)
    hooks = {c.check_id: c for c in surface.by_origin(VerificationOrigin.HOOK)}
    assert set(hooks) == {"pre-commit:check-translations", "pre-commit:ruff"}
    finding = next(f for f in surface_findings(surface) if f.code == "LOCAL_CHECK_NOT_OBSERVED_IN_CI")
    assert finding.evidence["checks"] == ["pre-commit:check-translations"]


def test_ci_running_pre_commit_covers_hooks(tmp_path):
    write(tmp_path / ".pre-commit-config.yaml", "repos:\n  - repo: local\n    hooks:\n      - id: custom-check\n        entry: ./custom\n        language: system\n")
    write(tmp_path / ".github" / "workflows" / "ci.yml", "on: [push]\njobs:\n  t:\n    steps:\n      - run: pre-commit run --all-files\n")
    codes = {f.code for f in surface_findings(discover_surface(tmp_path))}
    assert "LOCAL_CHECK_NOT_OBSERVED_IN_CI" not in codes


def test_ci_extra_validation(tmp_path):
    """CI runs a validator developers do not run locally: local green is weaker than CI green."""
    write(tmp_path / ".pre-commit-config.yaml", "repos:\n  - repo: https://github.com/astral-sh/ruff-pre-commit\n    rev: v0.6.0\n    hooks:\n      - id: ruff\n")
    write(
        tmp_path / ".github" / "workflows" / "ci.yml",
        "on: [push]\njobs:\n  t:\n    steps:\n      - run: ruff check .\n      - run: python scripts/validate_schemas.py\n",
    )
    finding = next(f for f in surface_findings(discover_surface(tmp_path)) if f.code == "CI_ONLY_CHECK")
    assert finding.evidence["checks"] == ["python scripts/validate_schemas.py"]


def test_interpreter_paths_are_normalized_before_wrappers():
    """Found by dogfooding: `.venv/bin/python -m pip install` was reported as unknown verification."""
    from assertiva.adapters.commands import classify_command

    assert classify_command(".venv/bin/python -m pip install dist/x.whl").setup_only
    tested = classify_command("venv/Scripts/python.exe -m pytest -q")
    assert (tested.kind, tested.tool) == (VerificationKind.TEST, "pytest")


def test_interpreter_options_before_dash_m_are_unwrapped():
    """Found by dogfooding: `python -X utf8 -m unittest discover -s tests` was an unknown command."""
    from assertiva.adapters.commands import classify_command

    tested = classify_command("python -X utf8 -m unittest discover -s tests")
    assert (tested.kind, tested.tool, tested.runner_args) == (VerificationKind.TEST, "unittest", ("discover", "-s", "tests"))
    assert classify_command("python3.12 -u -W error -m pytest -q").tool == "pytest"
    assert classify_command('python -c "import x"').kind is VerificationKind.UNKNOWN


def test_unparseable_workflow_is_unknown_not_silently_empty(tmp_path):
    write(tmp_path / ".github" / "workflows" / "broken.yml", "jobs: [unclosed\n")
    surface = discover_surface(tmp_path)
    [check] = surface.checks
    assert check.kind is VerificationKind.UNKNOWN
    assert "could not be parsed" in check.limitations[0]


def test_no_delivery_configuration_is_reported_not_assumed(tmp_path):
    write(tmp_path / "src" / "app.py", "X = 1\n")
    codes = {f.code for f in surface_findings(discover_surface(tmp_path))}
    assert "NO_DELIVERY_PIPELINE_OBSERVED" in codes
