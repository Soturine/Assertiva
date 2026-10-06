"""`assertiva audit`: read-only assurance audit over the Verification Surface.

Read-only is enforced, not promised: the whole audit runs inside ``read_only_guard``,
which fails if any project file (including caches and ignored files) changed. Executing
tests is opt-in and always happens in a disposable copy of the project.
"""

from __future__ import annotations

from pathlib import Path

from .adapters import runner_adapters
from .adapters.junit import load_junit
from .adapters.mutation import load_mutation_report
from .evidence import StateEvidence, attach_mutation, measure, mutant_label
from .candidate import StageStatus
from .models import BudgetDecision, Finding, MutantStatus, Outcome
from .report import audit_model, execution_budget
from .verification import discover_surface, surface_findings
from .workspace import capture_baseline, read_only_guard


def _native_findings(current: StateEvidence, static_total: int) -> list[Finding]:
    findings = []
    invocations = [inv for run in current.runs for inv in run.invocations]
    errors = [e for run in current.runs for e in run.collection_errors]
    if errors:
        findings.append(Finding("NATIVE_COLLECTION_ERRORS", "The native runner could not collect some tests.", {"errors": errors[:20]}))
    failing = [inv.invocation_id for inv in invocations if inv.outcome in (Outcome.FAILED, Outcome.ERROR)]
    if failing:
        findings.append(Finding("NATIVE_TESTS_FAILING", "Some tests fail or error in the current state.", {"count": len(failing), "tests": failing[:20]}))
    executed = [inv for run in current.runs if run.mode == "execute" for inv in run.invocations]
    if executed and static_total and len(executed) != static_total:
        findings.append(
            Finding(
                "STATIC_INVENTORY_DIVERGES_FROM_NATIVE",
                "Native collection differs from static inventory; native collection is authoritative for what runs.",
                {
                    "static_definitions_and_materializations": static_total,
                    "native_invocations": len(executed),
                    "native_declarations": len({inv.declaration_id for inv in executed}),
                    "inherited_materializations": sum(inv.inherited for inv in executed),
                    "parameterized_invocations": sum(inv.parameters_id is not None for inv in executed),
                },
            )
        )
    return findings


def _artifact_findings(current: StateEvidence) -> list[Finding]:
    findings = []
    for a in current.artifacts:
        if a.status is not StageStatus.PASS:
            failed = [c for c in a.checks if c.status is not StageStatus.PASS]
            findings.append(
                Finding(
                    "ARTIFACT_QUALIFICATION_FAILED" if a.status is StageStatus.FAIL else "ARTIFACT_QUALIFICATION_INCOMPLETE",
                    "The built artifact was not verified as working; source-tree results do not cover it.",
                    {"artifact": a.artifact, "status": a.status.value, "checks": [f"{c.name}: {c.status.value}: {c.detail}" for c in failed]},
                )
            )
        if a.omitted_files:
            findings.append(
                Finding("ARTIFACT_OMITS_SOURCE_FILES", "Files inside packaged directories are not in the artifact (they may be intentionally excluded).",
                        {"artifact": a.artifact, "files": a.omitted_files[:30]})
            )
    return findings


def _mutation_findings(current: StateEvidence) -> list[Finding]:
    findings = []
    for run in current.mutation:
        if run.error:
            findings.append(Finding("MUTATION_REPORT_UNREADABLE", "A mutation report could not be read; it provides no evidence.", {"source": run.source, "error": run.error}))
        elif run.matches_state is False:
            findings.append(Finding("MUTATION_REPORT_SOURCE_MISMATCH", "A mutation report was produced for different source than the audited project.", {"source": run.source, "limitations": run.limitations}))
        elif run.count(MutantStatus.SURVIVED) or run.count(MutantStatus.NO_COVERAGE):
            findings.append(
                Finding(
                    "MUTATION_SURVIVORS",
                    "Deliberate defects went undetected; a high mutation score does not cover these behaviors.",
                    {
                        "tool": run.tool, "source": run.source,
                        "survived": run.count(MutantStatus.SURVIVED), "no_coverage": run.count(MutantStatus.NO_COVERAGE),
                        "evaluated": run.evaluated, "survivors": [mutant_label(m) for m in run.survivors()[:20]],
                    },
                )
            )
    return findings


def run_audit(
    root: str | Path,
    coverage_json: str | Path | None = None,
    execute: bool = False,
    python: str | None = None,
    mutation_reports: list[str | Path] | tuple = (),
    junit_reports: list[str | Path] | tuple = (),
) -> dict:
    root = Path(root).resolve()
    findings: list[Finding] = []
    limitations: list[str] = []
    with read_only_guard(root):
        baseline = capture_baseline(root)
        surface = discover_surface(root)
        adapters = runner_adapters(root, python)
        if not adapters:
            findings.append(
                Finding(
                    "NO_EXECUTABLE_TEST_ADAPTER_RECOGNIZED",
                    "No executable test adapter recognized this project. Assertiva does not infer that it has zero tests.",
                )
            )
            limitations.append("test evidence is UNKNOWN for this toolchain until an adapter or portable report is available")
        static_total = 0
        for adapter in adapters:
            static = adapter.static_audit(root, coverage_json)
            findings.extend(static.findings)
            static_total += len(static.tests) + len(static.materializations)
            limitations.append(f"{adapter.adapter_id}: static inventory is bounded AST analysis, not native collection")
        if execute and adapters:
            current = measure(root, "current", "isolated-project-copy", python, reason="requested: audit --execute")
        else:
            current = StateEvidence("current", "static-analysis")
            not_requested = "not requested: fast static feedback; audit --execute runs tests and artifact checks"
            current.budget += [BudgetDecision("tests", "NOT_RUN", not_requested), BudgetDecision("artifact", "NOT_RUN", not_requested)]
            for adapter in adapters:
                current.static.update(adapter.static_signals(root))
            if adapters:
                limitations.append("tests were not executed; --execute collects native evidence by running project code in an isolated copy")
        current.runs.extend(load_junit(report) for report in junit_reports)
        if current.runs:
            findings.extend(_native_findings(current, static_total))
        for report in mutation_reports:
            attach_mutation(current, load_mutation_report(report), root)
        findings.extend(_mutation_findings(current))
        findings.extend(_artifact_findings(current))
        findings.extend(surface_findings(surface))
    status = "UNKNOWN" if not adapters and not current.runs else ("FINDINGS" if findings else "NO_FINDINGS_IN_SCOPE")
    for run in current.runs:
        limitations.extend(f"{run.adapter_id}: {item}" for item in run.limitations)
    report = audit_model(root, baseline, findings, current, surface, limitations, [a.adapter_id for a in adapters], status)
    report["execution_budget"] = execution_budget("execute" if execute and adapters else "static", current.budget)
    return report
