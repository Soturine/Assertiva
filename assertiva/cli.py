"""Two user-facing commands: `assertiva audit` and `assertiva improve`.

Isolation, qualification, application and post-apply verification are internal phases
of `improve`, not separate modes.
"""

from __future__ import annotations

import argparse
import getpass
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

from . import __version__, process
from .adapters import timeout_override
from .assessment import apply_assessment, load_assessment
from .audit import run_audit
from .config import load_config
from .evidence import NegativeControl
from .improve import (
    SessionExistsError,
    apply_approved,
    discard_session,
    load_qualified_changes,
    load_session,
    qualify_candidate,
    start_improve,
)
from .report import improve_report, write_report
from .workspace import (
    Approval, ApplyFailedError, ApprovalRequiredError, ProjectModifiedError, StaleBaselineError, capture_baseline, read_only_guard,
    state_dir,
)


class UsageError(Exception):
    pass


def _report_dir(root: Path, requested: str | None) -> Path:
    if not requested:
        return state_dir(root, "reports")
    directory = Path(requested).resolve()
    if directory == root.resolve() or directory.is_relative_to(root.resolve()):
        raise UsageError("the report directory must be outside the project so audit stays read-only")
    return directory


def _emit(payload: dict, output: str, lines: list[str]) -> None:
    if output == "json":
        print(json.dumps(payload, indent=2, sort_keys=True))
    else:
        print("\n".join(lines))


_MEASUREMENT = ("execute", "changed_since", "coverage_report", "mutation_report", "junit_xml", "run_check", "accessibility_report", "contract")


def _attach(root: Path, directory: Path, args: argparse.Namespace) -> int:
    """Join the agent's assessment to the latest audit of this project and re-render that run's page."""
    if any(getattr(args, name) for name in _MEASUREMENT):
        raise UsageError("--assessment attaches to the last audit run; it cannot be combined with options that measure")
    stored = directory / "audit.json"
    if not stored.is_file():
        raise UsageError(f"no audit report for this project in {directory}; run `assertiva audit` first")
    report = json.loads(stored.read_text(encoding="utf-8"))
    digest = (report.get("project") or {}).get("digest")
    if not digest:
        raise UsageError("the last audit report predates assessments (no project digest); run `assertiva audit` again")
    with read_only_guard(root):
        current = capture_baseline(root).digest
    if current != digest:
        raise UsageError("the project changed since the audited run; run `assertiva audit` again and assess that run")
    report = apply_assessment(report, load_assessment(args.assessment))
    report["report_path"] = str(write_report(report, directory, "audit"))
    a = report["assessment"]
    _emit(report, args.output, [
        f"Assessment attached to audit run {report['run_id']}: {a['dispositions']} dispositions, {a['findings']} agent findings",
        f"Report: {report['report_path']}",
    ])
    return 0


def _audit(args: argparse.Namespace) -> int:
    root = Path(args.root).resolve()
    if args.mutate_tests and not args.mutate:
        raise UsageError("--mutate-tests selects the tests for --mutate; name the files to mutate with --mutate")
    directory = _report_dir(root, args.report_dir)
    if args.assessment:
        return _attach(root, directory, args)
    report = run_audit(root, execute=args.execute, python=args.python, mutation_reports=args.mutation_report or [],
                       junit_reports=args.junit_xml or [], coverage_reports=args.coverage_report or [], changed_since=args.changed_since,
                       accessibility_reports=args.accessibility_report or [], contract_reports=args.contract or [],
                       export_ctrf=args.ctrf,
                       ci_runs=args.ci_run or [], provision=args.provision,
                       run_checks=args.run_check or [], mutation_targets=args.mutate or [],
                       mutation_tool=args.mutation_tool, mutation_tests=args.mutate_tests or [])
    report["provenance"]["trace"] = str(process.TRACE_PATH) if process.TRACE_PATH else None
    report["report_path"] = str(write_report(report, directory, "audit"))
    lines = [f"Assertiva audit: {report['status']} ({root})"]
    lines += [f"[{f['severity'].upper()}] {f['code']}: {f['summary']}" for f in report["findings"]]
    lines += ["Not evidenced:"] + [f"  - {item}" for item in report["claim_boundary"]["not_evidenced"]]
    lines.append(f"Report: {report['report_path']}")
    _emit(report, args.output, lines)
    return 0


def _controls(path: str | None) -> list[NegativeControl]:
    if not path:
        return []
    return [
        NegativeControl(**{**item, "tests": tuple(item.get("tests", ()))})
        for item in json.loads(Path(path).read_text(encoding="utf-8"))
    ]


def _state_reports(values: list[str] | None) -> dict[str, str]:
    reports = {}
    for value in values or []:
        state, sep, path = value.partition("=")
        if not sep or state not in {"baseline", "candidate"}:
            raise UsageError("improve reports expect baseline=PATH or candidate=PATH")
        reports[state] = path
    return reports


def _improve(args: argparse.Namespace) -> int:
    root = Path(args.root).resolve()
    with process.passthrough(load_config(root).env):
        return _improve_in(args, root)


def _improve_in(args: argparse.Namespace, root: Path) -> int:
    session = load_session(root)

    if args.discard:
        if session:
            discard_session(session)
        _emit({"status": "DISCARDED"}, args.output, ["Improve session discarded; the project was not changed."])
        return 0

    if session is None:
        if args.approve:
            raise UsageError("nothing to approve: no improve session has been qualified for this project")
        session = start_improve(root, python=args.python)
        payload = {
            "status": "CANDIDATE_WORKSPACE_READY",
            "candidate_workspace": str(session.workspace),
            "baseline": {"revision": session.baseline.revision, "dirty": session.baseline.dirty, "digest": session.baseline.digest},
        }
        _emit(payload, args.output, [
            "Baseline measured in isolation. The project was not changed.",
            f"Write candidate changes in: {session.workspace}",
            "Then run `assertiva improve` again to qualify them.",
        ])
        return 0

    directory = _report_dir(root, args.report_dir)
    if args.approve:
        changes = load_qualified_changes(session)
        if not changes:
            raise UsageError("approve after qualification: run `assertiva improve` to qualify the candidate first")
        approval = Approval(frozenset(args.approve), args.approved_by or getpass.getuser())
        qualified = json.loads((session.directory / "qualification.json").read_text(encoding="utf-8"))
        applied = apply_approved(session, changes, approval)
        result = _result_from(qualified)
        report = improve_report(session, result, applied)
        report["provenance"]["trace"] = str(process.TRACE_PATH) if process.TRACE_PATH else None
        report["report_path"] = str(write_report(report, directory, "improve"))
        discard_session(session)
        _emit(report, args.output, [
            f"Applied {len(applied.applied)} approved changes; post-apply files match candidate: {applied.files_match_candidate}",
            *[f"  {run.adapter_id}: {run.status.value}" for run in applied.evidence.runs],
            f"Report: {report['report_path']}",
        ])
        return 0

    result = qualify_candidate(
        session, _controls(args.negative_controls), _state_reports(args.mutation_report), set(args.run_check or ()),
        coverage_reports=_state_reports(args.coverage_report), mutation_targets=args.mutate or None,
        mutation_tool=args.mutation_tool,
    )
    report = improve_report(session, result)
    report["provenance"]["trace"] = str(process.TRACE_PATH) if process.TRACE_PATH else None
    report["report_path"] = str(write_report(report, directory, "improve"))
    q = result.qualification
    lines = [f"Candidate qualification: {report['status']} (not applied)"]
    for s in q.stages:
        lines.append(f"  {s.stage.value:<32} {s.status.value}")
        lines += [f"    {c.check.value:<30} {c.status.value:<8} {c.summary}" for c in s.checks]
    lines += [f"  change {c.kind.value:<17} {c.change_id}" for c in q.changes]
    lines += [f"Report: {report['report_path']}"]
    if q.changes:
        lines.append("Apply only with explicit approval: assertiva improve --approve <change_id> [...]")
    _emit(report, args.output, lines)
    return 0


def _result_from(data: dict):
    """Rebuild the qualification result persisted at qualification time."""
    from .candidate import (
        CandidateChangeKind, CandidateQualification, CandidateTestChange, DeltaState, MetricDelta,
        CheckResult, QualificationCheck, QualificationStage, QualificationStageResult, StageStatus,
    )
    from .evidence import ControlOutcome, NegativeControlResult, state_from_dict
    from .improve import QualificationResult
    from .models import BudgetDecision, Outcome, StabilityEvidence, StabilityRecord

    q = data["qualification"]
    return QualificationResult(
        qualification=CandidateQualification(
            changes=[CandidateTestChange(**{**c, "kind": CandidateChangeKind(c["kind"])}) for c in q["changes"]],
            metric_deltas=[MetricDelta(**{**d, "state": DeltaState(d["state"])}) for d in q["metric_deltas"]],
            stages=[
                QualificationStageResult(
                    QualificationStage(s["stage"]), StageStatus(s["status"]), s["summary"],
                    tuple(CheckResult(QualificationCheck(c["check"]), StageStatus(c["status"]), c["summary"],
                                      tuple(c["evidence_refs"]), tuple(c["limitations"]))
                          for c in s["checks"] if c["check"] in QualificationCheck.__members__),  # checks merged since older sessions
                )
                for s in q["stages"]
            ],
        ),
        baseline_evidence=state_from_dict(data["baseline_evidence"]),
        candidate_evidence=state_from_dict(data["candidate_evidence"]),
        baseline_controls=[NegativeControlResult(**{**r, "outcome": ControlOutcome(r["outcome"])}) for r in data["baseline_controls"]],
        stability=StabilityEvidence(**{
            **data["stability"],
            "records": [
                StabilityRecord(r["invocation_id"], tuple(Outcome(o) if o else None for o in r["outcomes"]), tuple(r["durations_s"]), r["verdict"])
                for r in data["stability"]["records"]
            ],
        }),
        timings=list(data["timings"]),
        budget=[BudgetDecision(**d) for d in data.get("budget", [])],
        history=data.get("history"),
    )


def _seconds(value: str) -> float:
    try:
        seconds = float(value)
    except ValueError:
        raise argparse.ArgumentTypeError(f"{value!r} is not a number of seconds") from None
    if not 0 < seconds <= 7 * 24 * 3600:
        raise argparse.ArgumentTypeError("the limit must be more than 0 and at most a week of seconds")
    return seconds


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="assertiva", description="Adaptive Test Intelligence & Assurance")
    parser.add_argument("--version", action="version", version=f"assertiva {__version__}")
    sub = parser.add_subparsers(dest="command", required=True)

    def common(p: argparse.ArgumentParser) -> None:
        p.add_argument("root", nargs="?", default=".")
        p.add_argument("--python", help="interpreter of the project environment (default: this interpreter)")
        p.add_argument("--report-dir", help="where to write the report (must be outside the project)")
        p.add_argument("--output", choices=("text", "json"), default="text")
        p.add_argument("--timeout-s", type=_seconds, metavar="SECONDS",
                       help="per-run limit for test runs and artifact qualification (wins over the project's [tests] "
                            "timeout_s and the adapter defaults; recorded in the run's manifest; never written to the project)")

    audit = sub.add_parser("audit", help="read-only assurance audit; never changes project files")
    common(audit)
    audit.add_argument("--coverage-report", "--coverage-json", dest="coverage_report", action="append",
                       help="existing coverage report to ingest: coverage.py JSON, istanbul summary, LCOV, Cobertura or JaCoCo XML")
    audit.add_argument("--execute", action="store_true", help="also run the tests natively, in an isolated copy")
    audit.add_argument("--changed-since", metavar="REV", help="select tests impacted by changes since REV (widened when impact is not proven); "
                                                              "with --execute, only the selected set runs")
    audit.add_argument("--mutation-report", action="append", help="existing mutation-tool report to ingest (repeatable)")
    audit.add_argument("--mutate", action="append", metavar="FILE",
                       help="with --execute: run the project's native mutation tool on FILE in a disposable copy (repeatable; "
                            "Cosmic Ray for Python tests under pytest, unittest or Django; StrykerJS for Jest or Vitest; "
                            "PIT for a Maven build that declares it; each installed in the project, never by Assertiva)")
    audit.add_argument("--mutate-tests", action="append", metavar="PATH",
                       help="with --mutate: run only these tests (files or folders) for the baseline and each mutant; the "
                            "run records the selection and never claims the whole suite (repeatable; Cosmic Ray)")
    audit.add_argument("--mutation-tool", choices=["cosmic-ray", "stryker", "pit"],
                       help="with --mutate: the mutation tool to use when several apply to the project")
    audit.add_argument("--ctrf", action="store_true",
                       help="also write the executed runs as CTRF JSON beside the report (audit.ctrf.json)")
    audit.add_argument("--contract", action="append", metavar="PATH",
                       help="a Pact contract file or a provider verification result (JSON) to ingest (repeatable); an empty "
                            "or pending-only verification is never counted as verified")
    audit.add_argument("--accessibility-report", action="append", metavar="PATH",
                       help="existing axe-core JSON results to ingest (repeatable); no violation is never proof of accessibility")
    audit.add_argument("--junit-xml", "--test-results", dest="junit_xml", action="append", metavar="PATH",
                       help="existing test results to ingest as portable evidence: JUnit XML, CTRF JSON or an Allure "
                            "results directory, recognized by shape (repeatable)")
    audit.add_argument("--provision", action="store_true",
                       help="with --execute: prepare what the tests need in isolation (interpreter environment, dependencies, JDK, "
                            "build tool, a disposable local database); downloads and runs installers outside the project")
    audit.add_argument("--ci-run", action="append", metavar="FILE",
                       help="a CI provider run exported as JSON (gh run view --json headSha,conclusion,jobs,url; a GitLab pipeline), compared with the audited revision")
    audit.add_argument("--run-check", action="append", metavar="CHECK_ID",
                       help="reproduce a discovered verification check (see verification_surface) in a disposable copy; "
                            "deploy/publish checks never run")
    audit.add_argument("--assessment", metavar="FILE", help="attach the auditing agent's assessment (JSON) to the last audit run "
                                                            "and re-render its report; executes nothing")
    audit.set_defaults(handler=_audit)

    improve = sub.add_parser("improve", help="build and qualify candidate test improvements; apply only with approval")
    common(improve)
    improve.add_argument("--approve", nargs="+", metavar="CHANGE_ID", help="explicitly approve qualified changes to apply")
    improve.add_argument("--approved-by", help="name recorded with the approval (default: current user)")
    improve.add_argument("--negative-controls", help="JSON list of deliberate behavior-breaking edits to challenge the tests")
    improve.add_argument("--mutation-report", action="append", metavar="STATE=PATH", help="mutation-tool report for baseline or candidate")
    improve.add_argument("--mutate", action="append", metavar="FILE",
                         help="run the project's native mutation tool on FILE for the baseline and the candidate, each in a "
                              "disposable copy, and report the protection the candidate gains or loses (repeatable)")
    improve.add_argument("--mutation-tool", choices=["cosmic-ray", "stryker", "pit"],
                         help="with --mutate: the mutation tool to use when several apply to the project")
    improve.add_argument("--coverage-report", action="append", metavar="STATE=PATH", help="coverage report for baseline or candidate")
    improve.add_argument("--run-check", action="append", metavar="CHECK_ID", help="authorize running a discovered delivery check in the candidate copy")
    improve.add_argument("--discard", action="store_true", help="drop the candidate session without touching the project")
    improve.set_defaults(handler=_improve)
    port = sub.add_parser("portfolio", help="registry of audited projects, their audits over time, and feedback about Assertiva")
    port.add_argument("--output", choices=("text", "json"), default="text")
    acts = port.add_subparsers(dest="action", required=True)
    p_add = acts.add_parser("add", help="register a local checkout (read-only; nothing is changed in it)")
    p_add.add_argument("path")
    p_add.add_argument("--name")
    p_add.add_argument("--phase", default="unknown", choices=("active", "maintenance", "archived", "legacy", "unknown"))
    p_add.add_argument("--criticality", default="unknown")
    p_add.add_argument("--need", action="append", metavar="TEXT", help="what the project needs to run (JDK 11, a device…)")
    p_list = acts.add_parser("list", help="each project's status: CURRENT, STALE, BLOCKED or UNKNOWN")
    p_list.add_argument("--paths", action="store_true", help="include local paths (left out by default)")
    p_audit = acts.add_parser("audit", help="run `assertiva audit` on a registered project and record its summary")
    p_audit.add_argument("project")
    p_audit.add_argument("--execute", action="store_true")
    p_audit.add_argument("--python")
    p_audit.add_argument("--timeout-s", type=_seconds, metavar="SECONDS")
    p_report = acts.add_parser("report", help="the portfolio view (JSON, and an offline HTML page with --html)")
    p_report.add_argument("--html", metavar="FILE", help="write a static page (no paths, no project code)")
    p_fb = acts.add_parser("feedback", help="record feedback about Assertiva itself (kept apart from project findings)")
    p_fb.add_argument("project")
    p_fb.add_argument("--kind", required=True, choices=("FALSE_POSITIVE", "FALSE_NEGATIVE", "MISSING_ANALYSIS", "ADAPTER_ERROR",
                                                        "SECURITY", "COST", "EVIDENCE_INCONSISTENCY", "UNSUPPORTED"))
    p_fb.add_argument("--rule", required=True, help="the finding code or engine rule concerned")
    p_fb.add_argument("--signature", required=True, help="sanitized signature of the issue (dedup key)")
    p_fb.add_argument("--reproducer", required=True, help="synthetic fixture path or description; never the project's code or data")
    p_fb.add_argument("--engine-version")
    p_fb.add_argument("--run-id")
    p_fb.add_argument("--note")
    p_mv = acts.add_parser("move", help="move feedback to a new state with its evidence")
    p_mv.add_argument("feedback_id")
    p_mv.add_argument("state", choices=("OBSERVED", "REPRODUCED", "FIXED_IN_ASSERTIVA_BRANCH", "RETESTED_WITH_ASSERTIVA",
                                        "VERIFIED_AT_SHA", "BLOCKED", "NOT_SUPPORTED", "REOPENED", "REGRESSION"))
    p_mv.add_argument("--evidence", required=True)
    p_disc = acts.add_parser("discover", help="list an owner's GitHub repositories (metadata only; clones and adds nothing)")
    p_disc.add_argument("--owner", required=True)
    port.set_defaults(handler=_portfolio, root=".")
    return parser


def _portfolio(args: argparse.Namespace) -> int:
    from . import portfolio

    action = args.action
    if action == "add":
        project = portfolio.add(args.path, name=args.name, phase=args.phase, criticality=args.criticality, needs=args.need or [])
        payload, lines = {"added": project.name, "stacks": project.stacks}, [f"added {project.name}: " + ", ".join(s["name"] for s in project.stacks)]
    elif action == "list":
        payload = portfolio.report(include_paths=args.paths)
        lines = [f"{p['name']}: {p['status']} ({p['why']})" for p in payload["projects"]] or ["the portfolio is empty"]
    elif action == "audit":
        payload = portfolio.audit(args.project, execute=args.execute, python=args.python, timeout_s=args.timeout_s)
        lines = [f"{args.project}: tests {payload['tests_status']} at {str(payload['revision'])[:12]}; report {payload['report']}"]
    elif action == "report":
        payload = portfolio.report(include_paths=False)
        out = Path(args.html) if args.html else None
        if out:
            from .portfolio_html import render

            out.write_text(render(payload), encoding="utf-8")
        lines = [f"{len(payload['projects'])} projects, {len(payload['assertiva_feedback'])} Assertiva feedback entries"
                 + (f"; page: {out}" if out else "")]
    elif action == "feedback":
        payload = portfolio.add_feedback(args.project, args.kind, args.rule, args.signature, args.reproducer,
                                         args.engine_version or __version__, run_id=args.run_id, note=args.note or "")
        lines = [f"{payload['feedback_id']}: {payload['state']} ({len(payload['sightings'])} sightings)"]
    elif action == "move":
        payload = portfolio.move_feedback(args.feedback_id, args.state, args.evidence)
        lines = [f"{payload['feedback_id']}: {payload['state']}"]
    else:  # discover
        payload = {"owner": args.owner, "repositories": portfolio.discover(args.owner),
                   "note": "listed only: nothing was cloned or added; add a local checkout with `assertiva portfolio add PATH`"}
        lines = [f"{r['name']} ({r['visibility']}{', archived' if r['archived'] else ''}): {r['language'] or '?'}" for r in payload["repositories"]]
    _emit(payload, args.output, lines)
    return 0


def main(argv: list[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    try:
        stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%fZ")
        process.TRACE_PATH = state_dir(Path(args.root), "traces") / f"{args.command}-{stamp}.jsonl"
        with process.run_scope(), timeout_override(getattr(args, "timeout_s", None)):
            return args.handler(args)
    except (UsageError, ValueError, ApprovalRequiredError, SessionExistsError) as exc:
        print(f"assertiva: {exc}", file=sys.stderr)
        return 2
    except StaleBaselineError as exc:
        print(f"assertiva: refused: {exc}", file=sys.stderr)
        return 2
    except ApplyFailedError as exc:
        print(f"assertiva: {exc}", file=sys.stderr)
        return 2
    except ProjectModifiedError as exc:
        print(f"assertiva: READ-ONLY VIOLATION: {exc}", file=sys.stderr)
        return 3
    finally:
        process.TRACE_PATH = None


if __name__ == "__main__":
    raise SystemExit(main())
