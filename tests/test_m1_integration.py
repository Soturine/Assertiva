"""End-to-end M1 qualification: baseline -> candidate -> tests, coverage, mutation, artifact,
negative paths, stability -> report. No aggregate score; mixed evidence stays mixed."""

import json
import re
import sys

import pytest

from assertiva.candidate import QualificationCheck, StageStatus
from assertiva.improve import discard_session, qualify_candidate, start_improve
from assertiva.report import improve_report, render_html

from conftest import write

pytestmark = pytest.mark.artifact

PYPROJECT = """[build-system]
requires = ["setuptools>=61"]
build-backend = "setuptools.build_meta"

[project]
name = "shop"
version = "1.0.0"

[tool.setuptools]
packages = ["shop"]
{package_data}"""
PACKAGE_DATA = '[tool.setuptools.package-data]\nshop = ["banner.txt"]\n'
SHOP = """from importlib import resources


class PricingError(Exception):
    def __init__(self, code):
        super().__init__(code)
        self.code = code


def discount(total, tier):
    if total < 0:
        raise PricingError("NEGATIVE_TOTAL")
    if tier == "VIP" and total >= 100:
        return round(total * 0.9, 2)
    return total


def banner():
    return resources.files("shop").joinpath("banner.txt").read_text().strip()
"""
WEAK_TESTS = """import pytest
from shop import PricingError, banner, discount


def test_discount_runs():
    assert discount(200, "VIP") is not None


def test_rejects_negative():
    with pytest.raises(PricingError):
        discount(-1, "VIP")


def test_banner():
    assert banner() == "SALE"
"""
STRONG_TESTS = """import pytest
from shop import PricingError, banner, discount


def test_vip_discount_boundary():
    assert discount(100, "VIP") == 90
    assert discount(99.99, "VIP") == 99.99
    assert discount(150, "REGULAR") == 150


def test_rejects_negative():
    with pytest.raises(PricingError) as excinfo:
        discount(-1, "VIP")
    assert excinfo.value.code == "NEGATIVE_TOTAL"


def test_banner():
    assert banner() == "SALE"
"""


def project(root, package_data):
    write(root / "pyproject.toml", PYPROJECT.format(package_data=PACKAGE_DATA if package_data else ""))
    write(root / "shop" / "__init__.py", SHOP)
    write(root / "shop" / "banner.txt", "SALE\n")
    write(root / "tests" / "test_shop.py", WEAK_TESTS)
    return root


def mutation_report(path, source_dir, statuses):
    mutants = [
        {"id": str(i), "mutatorName": name, "replacement": repl, "status": status,
         "location": {"start": {"line": line, "column": 1}, "end": {"line": line, "column": 2}}}
        for i, ((name, repl, line), status) in enumerate(zip(
            [("EqualityOperator", "total > 100", 14), ("ArithmeticOperator", "total * 1.1", 15), ("ConditionalExpression", "if False", 12)],
            statuses,
        ))
    ]
    source = (source_dir / "shop" / "__init__.py").read_text(encoding="utf-8")
    path.write_text(json.dumps({"schemaVersion": "2", "thresholds": {"high": 80, "low": 60},
                                "files": {"shop/__init__.py": {"language": "python", "source": source, "mutants": mutants}}}))
    return path


def names(report, bucket):
    return {d["name"] for d in report["evidence_delta"][bucket]}


def stages(q):
    return {c.check: c for c in q.checks}


@pytest.fixture
def improved(tmp_path):
    root = project(tmp_path / "shop-a", package_data=False)
    session = start_improve(root, python=sys.executable)
    write(session.workspace / "tests" / "test_shop.py", STRONG_TESTS)
    write(session.workspace / "pyproject.toml", PYPROJECT.format(package_data=PACKAGE_DATA))
    reports = {
        "baseline": mutation_report(tmp_path / "base.json", session.baseline_copy, ["Survived", "Survived", "Killed"]),
        "candidate": mutation_report(tmp_path / "cand.json", session.workspace, ["Killed", "Killed", "Killed"]),
    }
    result = qualify_candidate(session, mutation_reports=reports)
    yield session, result, improve_report(session, result)
    discard_session(session)


def test_real_improvement_is_shown_dimension_by_dimension(improved):
    _, result, report = improved
    assert {
        "branch_coverage", "mutation_survived", "mutation_killed", "artifact_qualified",
        "negative_paths_without_contract_detail", "weak_oracle_tests",
    } <= names(report, "improved")
    # Different invocations ran, so runtime is contextual: never reported as better or worse
    # (equal or different readings are both legitimate for the non-directional buckets).
    assert "wall_clock_s" not in names(report, "improved") | names(report, "regressed")
    assert "test_invocations" not in names(report, "improved")
    by = stages(result.qualification)
    for stage in (
        QualificationCheck.ORIGINAL_REGRESSION, QualificationCheck.COVERAGE_AND_ORACLES, QualificationCheck.NEGATIVE_PATHS,
        QualificationCheck.MUTATION_OR_NEGATIVE_CONTROLS, QualificationCheck.BUILD_AND_ARTIFACT, QualificationCheck.STABILITY_AND_COST,
    ):
        assert by[stage].status is StageStatus.PASS, (stage, by[stage])
    assert any("preview/deployment" in item for item in report["claim_boundary"]["not_evidenced"])
    assert result.qualification.ready_for_review
    assert report["states"]["applied"] is None


def test_report_has_no_aggregate_score_and_keeps_unknowns(improved):
    _, _, report = improved
    assert not re.search(r'"[a-z_]*score[a-z_]*"\s*:', json.dumps(report))
    unknowns = " ".join(report["remaining_unknowns"])
    assert "preview/deployment" in unknowns and "PIPELINE_EQUIVALENT" in unknowns


def test_html_distinguishes_statuses_and_shows_provenance(improved):
    _, _, report = improved
    html = render_html(report)
    css = dict(re.findall(r"\.(pass|fail|blocked|unknown|not_run)\{([^}]*)\}", html))
    assert len({css[s] for s in ("pass", "fail", "blocked", "unknown", "not_run")}) == 5
    assert 'id="unknowns"' in html and 'id="runs"' in html
    assert "isolated-candidate-copy" in html and "pytest-native" in html


@pytest.fixture
def worse(tmp_path):
    root = project(tmp_path / "shop-b", package_data=True)
    session = start_improve(root, python=sys.executable)
    many = WEAK_TESTS.replace('"SALE"', '"PROMO"') + "".join(
        f"\n\ndef test_more_{i}():\n    assert discount({i * 50}, 'VIP') is not None\n" for i in range(6)
    )
    write(session.workspace / "tests" / "test_shop.py", many)  # more tests, more lines covered
    write(session.workspace / "shop" / "banner.txt", "PROMO\n")  # product change hidden by editing the test
    write(session.workspace / "pyproject.toml", PYPROJECT.format(package_data=""))  # package data dropped
    reports = {
        "baseline": mutation_report(tmp_path / "base.json", session.baseline_copy, ["Survived", "Killed", "Killed"]),
        "candidate": mutation_report(tmp_path / "cand.json", session.workspace, ["Survived", "Survived", "Killed"]),
    }
    result = qualify_candidate(session, mutation_reports=reports)
    yield session, result, improve_report(session, result)
    discard_session(session)


def test_more_tests_and_coverage_cannot_hide_worse_evidence(worse):
    _, result, report = worse
    assert {"mutation_survived", "mutation_killed", "artifact_qualified"} <= names(report, "regressed")
    assert "test_invocations" in names(report, "changed")
    by = stages(result.qualification)
    assert by[QualificationCheck.ORIGINAL_REGRESSION].status is StageStatus.FAIL
    assert by[QualificationCheck.BUILD_AND_ARTIFACT].status is StageStatus.FAIL
    assert by[QualificationCheck.MUTATION_OR_NEGATIVE_CONTROLS].status is StageStatus.FAIL
    assert not result.qualification.ready_for_review
    assert report["status"] == "NEEDS_ATTENTION"
