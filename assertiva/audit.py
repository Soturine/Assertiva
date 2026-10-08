"""`assertiva audit`: read-only assurance audit over the Verification Surface.

Read-only is enforced, not promised: the whole audit runs inside ``read_only_guard``,
which fails if any project file (including caches and ignored files) changed. Executing
tests is opt-in and always happens in a disposable copy of the project.
"""

from __future__ import annotations

from pathlib import Path

from .adapters import artifact_adapters, runner_adapters, static_providers
from .adapters.coverage_reports import load_coverage_report
from .adapters.junit import load_junit
from .adapters.mutation import load_mutation_report
from .config import ProjectConfig, load_config
from .evidence import StateEvidence, attach_mutation, measure, mutant_label, runnable_copy
from .candidate import StageStatus
from .models import BudgetDecision, Finding, MutantStatus, Outcome
from contextlib import ExitStack

from . import environment
from .adapters.provisioning import plan, prepare
from .process import passthrough, scoped, traced_stage, withheld_variables
from .reproduction import reproduce_check
from .history import record_state
from .adapters.ci_runs import green, identity, load_ci_run
from .report import audit_model, execution_budget, execution_manifest, selection_summary
from .selection import select_changes
from .verification import GateMode, VerificationKind, artifact_lineage, delivery_matrix, discover_surface, matrix_findings, surface_findings
from .workspace import boundary_report, capture_baseline, read_only_guard, remove_tree


def _native_findings(current: StateEvidence, static_total: int, reported: tuple = ()) -> list[Finding]:
    """``reported``: runs whose failures a declared-check finding already reports (one cause, one finding)."""
    findings = []
    own = [run for run in current.runs if not any(run is r for r in reported)]
    invocations = [inv for run in own for inv in run.invocations]
    errors = [e for run in own for e in run.collection_errors]
    if errors:
        findings.append(Finding("NATIVE_COLLECTION_ERRORS", "The native runner could not collect some tests.", {"errors": errors[:20]}))
    failing = [inv.invocation_id for inv in invocations if inv.outcome in (Outcome.FAILED, Outcome.ERROR)]
    if failing:
        findings.append(Finding("NATIVE_TESTS_FAILING", "Some tests fail or error in the current state.", {"count": len(failing), "tests": failing[:20]}))
    executed = [inv for run in current.runs if run.mode == "execute" for inv in run.invocations]
    # The static inventory counts runnable nodes (definitions + inherited/composed materializations) and never expands
    # parameters; the comparable native unit is the materialization, not the invocation (one per parameter case).
    materializations = {inv.materialization_id for inv in executed}
    if executed and static_total and len(materializations) != static_total:
        findings.append(
            Finding(
                "STATIC_INVENTORY_DIVERGES_FROM_NATIVE",
                "Native collection differs from static inventory; native collection is authoritative for what runs.",
                {
                    "static_definitions_and_materializations": static_total,
                    "native_materializations": len(materializations),
                    "native_invocations": len(executed),
                    "native_declarations": len({inv.declaration_id for inv in executed}),
                    "inherited_materializations": sum(inv.inherited for inv in executed),
                    "parameterized_invocations": sum(inv.parameters_id is not None for inv in executed),
                },
            )
        )
    return findings


def _prepare(root: Path, python: str | None, consented: bool) -> environment.Prepared:
    """A run workspace, the plan for this project and, with consent, its preparation (removed when the run ends)."""
    home = environment.assertiva_home()
    if home == root or root in home.parents:  # a workspace there would be written into the project
        prepared = environment.Prepared()
        prepared.steps = plan(root, python, prepared)
        for step in prepared.steps:
            if step.status == "PLANNED":
                step.status, step.detail = "BLOCKED", "ASSERTIVA_HOME is inside the project: nothing is prepared there"
        return prepared
    workspace = environment.new_workspace()
    prepared = environment.Prepared(workspace=workspace)
    prepared.cleanups.append(lambda: remove_tree(workspace))  # runs last: services stop before their data goes
    with traced_stage("environment:prepare"):
        prepared.steps = plan(root, python, prepared)
        prepare(root, prepared.steps, prepared, consented)
    environment.write_manifest(prepared, {"project": str(root), "consented": consented})
    return prepared


def environment_summary(prepared: environment.Prepared, executed: bool) -> dict:
    return {
        "isolation": environment.ISOLATION_COPY if executed else environment.ISOLATION_STATIC,
        "isolation_limits": ["a disposable copy and a virtual environment are not a security sandbox: project code runs as the user, with network access"]
        if executed else [],
        "requirements": prepared.requirements, "steps": [step.__dict__ for step in prepared.steps], "services": prepared.services,
        "tools": prepared.tools, "interpreter": prepared.python,
        "workspace": {"path": str(prepared.workspace), "removed_at_end": True} if prepared.workspace else None,
    }


def _effectiveness(root: Path, current: StateEvidence) -> dict:
    """What the tests prove, per language, from the same facts and rules for every language (never a score)."""
    from .adapters.test_facts import collect
    from .effectiveness import summarize

    facts, limits = collect(root)
    return summarize(facts, limits, current.mutation)


def _effectiveness_findings(summary: dict) -> list[Finding]:
    """One finding per candidate: a lead for the agent to confirm, contextualize or reject in its assessment (with
    per-test subjects), never a conclusion. The Python weak-oracle signal already comes from the static inventory."""
    findings = []
    for candidate in summary.get("candidates", []):
        if candidate["kind"] == "WEAK_ORACLE":
            if candidate["language"] != "python":
                findings.append(Finding("WEAK_ORACLE_SIGNAL", "Some direct test definitions expose weak deterministic oracle signals.",
                                        {"language": candidate["language"], "count": candidate["count"], "tests": candidate["tests"],
                                         "signals": candidate["detail"].get("oracles", {})}))
            continue
        kind, evidence = candidate["kind"], {key: candidate[key] for key in ("language", "count", "tests", "shows", "why", "resolve_with", "basis", "detail")}
        if kind == "FALSE_GREEN":
            findings.append(Finding("FALSE_GREEN_CANDIDATE", "Some tests can pass while the behavior they protect is broken (static pattern, to be confirmed).",
                                    evidence, severity="medium", recommendation=candidate["recommendation"]))
        elif kind == "FIDELITY_MISMATCH":
            findings.append(Finding("TEST_FIDELITY_MISMATCH", "Some tests declared integration or end-to-end replace every boundary they cross.",
                                    evidence, severity="medium", recommendation=candidate["recommendation"]))
        elif kind in ("REDUNDANCY", "DUPLICATE_CASES"):
            findings.append(Finding("REDUNDANCY_CANDIDATE", "Some tests appear to repeat the same evidence; review before consolidating anything.",
                                    evidence, severity="info", recommendation=candidate["recommendation"]))
        elif kind == "SMELL":
            findings.append(Finding("TEST_SMELL_SIGNALS", "Some tests show maintenance or determinism smells; they are leads, not verdicts.",
                                    evidence, severity="info", recommendation=candidate["recommendation"]))
    return findings


def _now() -> str:
    from datetime import datetime, timezone

    return datetime.now(timezone.utc).isoformat(timespec="milliseconds")


def _observed_ci(paths, baseline) -> tuple[list[dict], list[Finding]]:
    """Provider runs the caller exported, each tied (or not) to the audited revision."""
    runs, findings = [], []
    for path in paths:
        run = load_ci_run(path)
        run["identity"] = identity(run, baseline.revision, baseline.dirty)
        run["provenance"] = "EXTERNAL_VERIFIED" if run["identity"] == "SAME_REVISION" else "EXTERNAL_UNVERIFIED"
        runs.append(run)
        if run.get("error"):
            findings.append(Finding("CI_RUN_UNREADABLE", "A CI run export could not be read; it provides no evidence.", {"source": run["source"], "error": run["error"]}))
        elif run["identity"] == "OTHER_REVISION":
            findings.append(Finding("CI_RUN_FOR_ANOTHER_REVISION", "The CI run provided is for another commit; it says nothing about the audited revision.",
                                    {"run": run.get("url") or run.get("id"), "run_sha": run["head_sha"], "audited_revision": baseline.revision}, severity="medium"))
        elif run["identity"] == "SAME_REVISION" and not green(run):
            findings.append(Finding("CI_RUN_NOT_GREEN", "The provider reports the CI run for this revision as not successful.",
                                    {"run": run.get("url") or run.get("id"), "conclusion": run["conclusion"],
                                     "failed_jobs": [j["name"] for j in run["jobs"] if j["conclusion"] not in ("success", "skipped", "neutral", None)]},
                                    severity="high"))
    return runs, findings


def _boundary_findings(report: dict) -> list[Finding]:
    findings = []
    if report["external_links"]:
        kinds = report.get("external_link_kinds") or {}
        tooling_only = all(kinds.get(link) == "AGENT_TOOL" for link in report["external_links"])
        findings.append(Finding(
            "PROJECT_LINK_ESCAPES_ROOT",
            "Project links point outside the project root; they are not followed or copied, but executions can reach their targets.",
            {"links": report["external_links"][:30], "kinds": {link: kinds.get(link, "UNKNOWN") for link in report["external_links"][:30]}},
            # an agent's or editor's own tool install is a fact worth stating, not a risk of the product
            severity="info" if tooling_only else None,
        ))
    if report["broken_links"]:
        findings.append(Finding("BROKEN_PROJECT_LINK", "Some project links point to nothing.", {"links": report["broken_links"][:30]}))
    if report["nested_repositories"]:
        findings.append(Finding(
            "NESTED_REPOSITORY",
            "Nested repositories or submodules are included from the working tree; their own history is not inspected.",
            {"paths": report["nested_repositories"][:30]},
        ))
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


def _declared_checks(root: Path, surface, requested, adapters, python: str | None, budget: list, revision: dict,
                     config: ProjectConfig, reusable: list) -> tuple[list[dict], list[Finding], list, list]:
    """Reproduce the discovered checks the caller named, in one disposable copy (never in the project).

    Naming a check selects it; test runners and side-effect-free checks run, other kinds need the project
    owner's authorization (`.assertiva.toml`), deploy/publish and compound shell steps never run."""
    by_id = {c.check_id: c for c in surface.checks}
    unknown = [c for c in requested if c not in by_id]
    if unknown:
        raise ValueError(f"no discovered check {', '.join(unknown)}; discovered check ids are listed in verification_surface")
    results, findings, runs, copies, runs_reported = [], [], [], [], []

    def copy() -> Path:
        if not copies:
            copies.append(runnable_copy(root, adapters, root))
        return copies[0]

    try:
        for check_id in dict.fromkeys(requested):
            check = by_id[check_id]
            done = reproduce_check(check, copy, adapters, python, revision, config.authorizes, reusable,
                                   authorize_hint=" (the exact command in <ASSERTIVA_HOME>/consent.toml)")
            results.append(done.record)
            budget.extend(done.budget)
            if done.run is not None and done.run not in reusable:
                done.run.metadata["reproduces_check"] = check_id
                runs.append(done.run)
            if done.status is StageStatus.FAIL:
                allowed = check.gate in (GateMode.ALLOWED_FAILURE, GateMode.ADVISORY)
                evidence = {"check_id": check_id, "command": check.command, "detail": done.record["detail"], "gate": check.gate.value}
                if done.run is not None:  # per-test evidence: the failing tests belong to this finding, not to a second one
                    evidence["failing_tests"] = [i.invocation_id for i in done.run.invocations if i.outcome in (Outcome.FAILED, Outcome.ERROR)][:20]
                    evidence["collection_errors"] = done.run.collection_errors[:20]
                    runs_reported.append(done.run)
                findings.append(Finding("DECLARED_CHECK_FAILED", "A declared verification check failed when reproduced in an isolated copy.",
                                        evidence, severity="info" if allowed else "high"))
    finally:
        for path in copies:
            remove_tree(path)
    return results, findings, runs, runs_reported


@scoped
def run_audit(
    root: str | Path,
    coverage_json: str | Path | None = None,
    execute: bool = False,
    python: str | None = None,
    mutation_reports: list[str | Path] | tuple = (),
    junit_reports: list[str | Path] | tuple = (),
    coverage_reports: list[str | Path] | tuple = (),
    changed_since: str | None = None,
    run_checks: list[str] | tuple = (),
    ci_runs: list[str | Path] | tuple = (),
    provision: bool = False,
) -> dict:
    root = Path(root).resolve()
    started = _now()
    selection = None
    findings: list[Finding] = []
    limitations: list[str] = []
    config = load_config(root)
    limitations += [f"configuration ({config.source}): {problem}" for problem in config.problems]
    with read_only_guard(root), passthrough(config.env), ExitStack() as stack:
        baseline = capture_baseline(root)
        surface = discover_surface(root)
        # What execution needs, prepared outside the project (only with the user's consent), before any runner exists.
        prepared = environment.Prepared()
        if execute:
            prepared = stack.enter_context(environment.active(_prepare(root, python, provision or config.provision)))
            python = prepared.python or python
        else:
            with traced_stage("environment:plan"):
                prepared.steps = plan(root, python, prepared)
            for step in prepared.steps:
                if step.status == "PLANNED":
                    step.status, step.detail = "NOT_RUN", "static audit: nothing is prepared (audit --execute --provision would)"
        adapters = runner_adapters(root, python)
        if changed_since:
            selection = select_changes(root, changed_since)
        if not adapters:
            findings.append(
                Finding(
                    "NO_EXECUTABLE_TEST_ADAPTER_RECOGNIZED",
                    "No executable test adapter recognized this project. Assertiva does not infer that it has zero tests.",
                )
            )
            limitations.append("test evidence is UNKNOWN for this toolchain until an adapter or portable report is available")
        static_total = 0
        for adapter in static_providers(adapters):
            static_audit = getattr(adapter, "static_audit", None)
            if static_audit is None:
                continue
            static = static_audit(root, coverage_json or next(iter(coverage_reports), None))
            findings.extend(static.findings)
            static_total += len(static.tests) + len(static.materializations)
            limitations.append(f"{adapter.adapter_id}: static inventory is bounded source analysis, not native collection")
        if execute and adapters:
            subset = sorted(selection.selected) if selection is not None and not selection.full else None
            current = measure(root, "current", "isolated-project-copy", python,
                              reason="requested: audit --execute" + (" (selected set)" if subset else ""), selected=subset)
        else:
            current = StateEvidence("current", "static-analysis")
            not_requested = ("not executed by this call: test outcomes, coverage and artifact behavior stay UNKNOWN; "
                             "audit --execute measures them in a disposable copy")
            current.budget += [BudgetDecision("tests", "NOT_RUN", not_requested), BudgetDecision("artifact", "NOT_RUN", not_requested)]
            for adapter in static_providers(adapters):
                current.static.update(adapter.static_signals(root))
            if adapters:
                limitations.append("tests were not executed; --execute collects native evidence by running project code in an isolated copy")
        reproduced, declared_findings, reproduced_runs, runs_reported = [], [], [], []
        if run_checks:
            revision = {"digest": baseline.digest, "vcs_revision": baseline.revision, "dirty": baseline.dirty}
            reproduced, declared_findings, reproduced_runs, runs_reported = _declared_checks(
                root, surface, list(run_checks), adapters, python, current.budget, revision, config, list(current.runs))
        findings.extend(declared_findings)
        if not current.runs:
            current.runs.extend(reproduced_runs)
        current.runs.extend(load_junit(report) for report in junit_reports)
        if current.runs:
            findings.extend(_native_findings(current, static_total, tuple(runs_reported)))
            if any(run.invocations for run in current.runs):  # native collection found tests: the static "none" is contradicted
                findings = [f for f in findings if f.code != "NO_TESTS_DISCOVERED"]
        for report in [*coverage_reports, *([coverage_json] if coverage_json else [])]:
            summary = load_coverage_report(report)
            current.coverage.append(summary)
            if summary.error:
                findings.append(Finding("COVERAGE_REPORT_UNREADABLE", "A coverage report could not be read; it provides no evidence.",
                                        {"source": summary.source, "error": summary.error}))
        for report in mutation_reports:
            attach_mutation(current, load_mutation_report(report), root)
        findings.extend(_mutation_findings(current))
        effectiveness = _effectiveness(root, current)
        findings.extend(_effectiveness_findings(effectiveness))
        findings.extend(_artifact_findings(current))
        findings.extend(surface_findings(surface))
        declared: dict[str, dict] = {}
        for adapter in adapters:
            if hasattr(adapter, "declared_matrix"):
                declared.update(adapter.declared_matrix(root))
        covered = delivery_matrix(surface, adapters)
        findings.extend(matrix_findings(surface, declared, covered))
        delivered = {}
        for adapter in artifact_adapters(root, python):
            for evidence in current.artifacts:
                if hasattr(adapter, "delivered_candidates") and evidence.adapter_id == adapter.adapter_id:
                    delivered.setdefault(evidence.artifact or "", []).extend(adapter.delivered_candidates(root, evidence))
        lineage, lineage_findings = artifact_lineage(surface, current.artifacts, delivered, baseline.revision)
        findings.extend(lineage_findings)
        review = [c for adapter in static_providers(adapters) if hasattr(adapter, "review_candidates") for c in adapter.review_candidates(root)]
        findings.extend(_boundary_findings(boundary_report(root)))
    withheld = withheld_variables()
    if withheld:
        limitations.append("credential-like environment variables were withheld from executed project code: " + ", ".join(withheld))
    unprepared = [s for s in prepared.steps if s.status in ("BLOCKED", "FAILED")]
    if unprepared:
        findings.append(Finding("ENVIRONMENT_NOT_PREPARED",
                                "Part of the environment the tests need could not be prepared; what depends on it was not executed.",
                                {"steps": [{"step": s.step_id, "status": s.status, "why": s.detail} for s in unprepared]}, severity="info"))
    observed_ci, ci_findings = _observed_ci(ci_runs, baseline)
    findings.extend(ci_findings)
    status = "UNKNOWN" if not adapters and not current.runs else ("FINDINGS" if findings else "NO_FINDINGS_IN_SCOPE")
    for run in current.runs:
        limitations.extend(f"{run.adapter_id}: {item}" for item in run.limitations)
        if run.deselected:
            limitations.append(f"{run.adapter_id}: {len(run.deselected)} tests were deselected by the run's own filters; they are not evidenced")
    report = audit_model(root, baseline, findings, current, surface, limitations, [a.adapter_id for a in adapters], status)
    report["execution_budget"] = execution_budget("execute" if execute and adapters else "static", current.budget)
    report["test_selection"] = selection_summary(selection)
    report["delivery"] = {"matrix": {"declared": declared, "ci": covered}, "artifact_lineage": lineage}
    report["review_candidates"] = review
    report["declared_checks"] = reproduced
    report["ci_runs"] = observed_ci
    for run in report["ci_runs"]:
        if not run.get("error"):
            report["claim_boundary"]["observed"].append(
                f"CI run reported by {run['provider']} for {run['head_sha'][:12]}: {run['conclusion']} ({run['identity']})")
    report["environment"] = environment_summary(prepared, execute)
    report["test_effectiveness"] = effectiveness
    report["execution_manifest"] = execution_manifest(root, baseline, current, started, junit_reports, coverage_reports,
                                                      mutation_reports, ci_runs, withheld)
    boundary = report["claim_boundary"]
    for check in reproduced:
        if check["status"] != StageStatus.NOT_RUN.value:
            boundary["observed"].append(f"declared check {check['check_id']} reproduced in an isolated copy: {check['status']} ({check['detail']})")
    if any(c["kind"] == VerificationKind.TEST.value and c["status"] != StageStatus.NOT_RUN.value for c in reproduced) and not current.runs:
        swap = "no tests were executed; test outcomes are UNKNOWN"
        boundary["not_evidenced"] = ["per-test outcomes are UNKNOWN: declared test checks ran as whole commands" if x == swap else x
                                     for x in boundary["not_evidenced"]]
        report["remaining_unknowns"] = list(boundary["not_evidenced"])
    report["history"] = None
    if execute and current.runs:
        reasons = {test: why[0].reason for test, why in (selection.selected.items() if selection else ())}
        selection_brief = {"confidence": selection.confidence.value, "full": selection.full} if selection else None
        coverage = next((c for c in [*current.coverage, *(r.coverage for r in current.runs)] if c and c.error is None), None)
        report["history"] = record_state(
            root, "audit", "current", baseline.digest, baseline.revision, current.runs, selection=selection_brief,
            selection_reasons=reasons, coverage={"tool": coverage.tool, "counts": coverage.counts} if coverage else None,
            artifacts=[{"kind": a.kind, "artifact": a.artifact, "sha256": a.sha256, "status": a.status.value} for a in current.artifacts],
        )
    if selection is not None:
        boundary = report["claim_boundary"]
        counts = report["test_selection"]["counts"]
        if execute and not selection.full:
            boundary["observed"].append(f"selected-set run: {counts['selected']} of {counts['mapped']} mapped test files ({selection.confidence.value})")
            boundary["not_evidenced"].append(f"full-suite outcome: {counts['not_selected']} mapped test files were not run")
        boundary["limitations"] += [lim for lim in selection.limitations if lim not in boundary["limitations"]]
    return report
