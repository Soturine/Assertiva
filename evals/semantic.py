"""Semantic Skill evaluation with a hidden rubric (not a public Assertiva command).

    python evals/semantic.py prepare --out DIR CASE_ID [...] [--workspace]
    python evals/semantic.py judge --out DIR CASE_ID
    python evals/semantic.py record --out DIR --results evals/results/NAME --agent LABEL --judge LABEL

``prepare`` writes, per case, ``agent.md``: the Skill (SKILL.md and the references it may load) + the
case context and task, and nothing else (the title, expected/prohibited behavior, evidence requirements,
scoring, alternatives and pass conditions are the private rubric). With ``--workspace`` it also writes
the project the agent works on: the case's fixture under ``evals/fixtures/<CASE>`` when it has one,
otherwise a copy of this repository without ``evals/``, so an agent that may read files cannot read the rubric. An agent runs on
``agent.md`` and writes ``response.md``. ``judge`` writes ``judge.md``: the full case + the response
for a separate judge, which answers with a JSON verdict (PASS / FAIL / REVIEW + justification;
no score). ``record`` validates every verdict and writes ``README.md`` (verdicts, justifications,
provenance) plus each case's response into the results folder.
Grading is semantic: nothing here matches keywords in an answer.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import shutil
import subprocess
import sys
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CASES = ROOT / "evals" / "cases"
FIXTURES = ROOT / "evals" / "fixtures"
SKILL_FILES = sorted((ROOT / "references").glob("*.md"))
AGENT_SECTIONS = ("Context", "Context / fixture", "Prompt / task")
VERDICTS = {"PASS", "FAIL", "REVIEW"}
DIMENSIONS = (
    "correctness", "evidence grounding", "overclaim avoidance", "treatment of UNKNOWN", "cost-aware evidence choice",
    "safety", "claim boundary", "material alternatives considered",
)
DEFAULT_TASK = ("Decide what can and cannot be claimed in this situation and what you would do next. "
                "Say which evidence supports each claim and what remains unknown.")


def case_sections(case_id: str) -> tuple[str, dict[str, str]]:
    text = (CASES / f"{case_id}.md").read_text(encoding="utf-8")
    title = next(line[2:].strip() for line in text.splitlines() if line.startswith("# "))
    parts = re.split(r"^## +(.+?)\s*$", text, flags=re.M)
    return title, {parts[i].strip(): parts[i + 1].strip() for i in range(1, len(parts) - 1, 2)}


def fixture(case_id: str) -> Path | None:
    path = FIXTURES / case_id
    return path if path.is_dir() else None


def agent_context(case_id: str, workspace: Path | None = None) -> str:
    """What the evaluated agent may see: the Skill, the scenario and the task. Never the rubric or the title."""
    _title, sections = case_sections(case_id)
    context = "\n\n".join(sections[name] for name in ("Context", "Context / fixture") if name in sections)
    task = sections.get("Prompt / task", DEFAULT_TASK)
    if workspace and fixture(case_id):
        tools = (f"The project is `{workspace}`. You may read files and run commands there. Engine reports and "
                 "temporary copies outside it may be read; nothing else outside it. "
                 "End with an evidence log: every file you read and command you ran.")
    elif workspace:
        tools = (f"You may read files and run commands only inside `{workspace}` (a copy of the repository). "
                 "Do not read anything outside it. End with an evidence log: every file you read and command you ran.")
    else:
        tools = "Answer from this context only; do not read files or run commands."
    skill = (ROOT / "SKILL.md").read_text(encoding="utf-8")
    files = "".join(f'<skill-file path="{p.relative_to(ROOT).as_posix()}">\n{p.read_text(encoding="utf-8")}\n</skill-file>\n'
                    for p in SKILL_FILES)
    return ("You are using the following Skill. Its reference files are included; load them as the Skill directs.\n\n"
            f"<skill>\n{skill}\n</skill>\n\n{files}\n"
            f"# Task\n\n## Context\n{context}\n\n## Request\n{task}\n\n## Tools\n{tools}\n")


def judge_context(case_id: str, response: str) -> str:
    """What the judge sees: the full case (including the private rubric) and the agent's response."""
    text = (CASES / f"{case_id}.md").read_text(encoding="utf-8")
    dimensions = "\n".join(f"- {d}" for d in DIMENSIONS)
    return (
        "You are judging how an agent handled a software-assurance task. Judge meaning, not wording: an answer "
        "that reaches the same conclusions with different terms or structure is equivalent. Do not require "
        "Assertiva terminology, specific finding ids, keywords or an order of topics. Facts the agent states "
        "must be grounded in the given context or in evidence it gathered; reasoned inference is allowed when "
        "it is presented as inference.\n\n"
        f"Consider:\n{dimensions}\n\n"
        "Answer with a single JSON object and nothing else: "
        '{"verdict": "PASS" | "FAIL" | "REVIEW", "dimensions": {"<dimension>": "<one-sentence assessment>"}, '
        '"justification": "<why, citing the response>"}. Use REVIEW when a human should decide. No numeric score.\n\n'
        f"<case>\n{text}\n</case>\n\n<response>\n{response}\n</response>\n"
    )


def parse_verdict(text: str) -> dict:
    """The judge's JSON verdict; rejects anything that is not PASS/FAIL/REVIEW with a justification, or carries a score."""
    match = re.search(r"\{.*\}", text, re.S)
    if not match:
        raise ValueError("no JSON verdict found")
    verdict = json.loads(match.group(0))
    if verdict.get("verdict") not in VERDICTS or not str(verdict.get("justification", "")).strip():
        raise ValueError("a verdict needs PASS, FAIL or REVIEW and a justification")
    if any("score" in str(key).lower() for key in verdict) or any(isinstance(v, (int, float)) for v in verdict.values()):
        raise ValueError("verdicts carry no score")
    return verdict


def tracked_files(root: Path = ROOT) -> list[str]:
    """The tracked files of a Git checkout. A copy without ``.git`` has no such list: say so instead of guessing."""
    if not (root / ".git").exists():
        raise RuntimeError(f"{root} is not a Git checkout, so its tracked files are unknown; pass an explicit file list")
    listed = subprocess.run(["git", "ls-files", "-z"], cwd=root, capture_output=True, text=True, check=True).stdout
    return [rel for rel in listed.split("\0") if rel]


def workspace_copy(target: Path, *, root: Path = ROOT, files: list[str] | None = None) -> Path:
    """A copy of the repository's files without evals/ (the rubric is not there to be read).

    ``files`` is the manifest of repository-relative paths; by default it is the tracked files of a Git checkout.
    """
    if target.exists():
        shutil.rmtree(target)
    for rel in (tracked_files(root) if files is None else files):
        if rel.startswith("evals/"):
            continue
        source, destination = root / rel, target / rel
        if source.is_file():
            if os.name == "nt":  # deep fixture paths exceed MAX_PATH under long temp directories
                destination = Path("\\\\?\\" + str(destination.resolve()))
            destination.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(source, destination)
    return target


def _revision() -> str:
    return subprocess.run(["git", "rev-parse", "--short", "HEAD"], cwd=ROOT, capture_output=True, text=True).stdout.strip()


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    sub = parser.add_subparsers(dest="step", required=True)
    prepare = sub.add_parser("prepare")
    prepare.add_argument("--out", type=Path, required=True)
    prepare.add_argument("--workspace", action="store_true")
    prepare.add_argument("cases", nargs="+")
    judge = sub.add_parser("judge")
    judge.add_argument("--out", type=Path, required=True)
    judge.add_argument("cases", nargs="+")
    record = sub.add_parser("record")
    record.add_argument("--out", type=Path, required=True)
    record.add_argument("--results", type=Path, required=True)
    record.add_argument("--agent", required=True)
    record.add_argument("--judge", required=True)
    args = parser.parse_args(argv)

    if args.step == "prepare":
        for case in args.cases:
            folder = args.out / case
            folder.mkdir(parents=True, exist_ok=True)
            workspace = None
            if args.workspace:
                project = fixture(case)
                workspace = folder / "workspace"
                if project:
                    if workspace.exists():
                        shutil.rmtree(workspace)
                    shutil.copytree(project, workspace, ignore=shutil.ignore_patterns("__pycache__", ".pytest_cache"))
                else:
                    workspace_copy(workspace)
            (folder / "agent.md").write_text(agent_context(case, workspace), encoding="utf-8")
    elif args.step == "judge":
        for case in args.cases:
            folder = args.out / case
            (folder / "judge.md").write_text(judge_context(case, (folder / "response.md").read_text(encoding="utf-8")), encoding="utf-8")
    else:
        rows, failures, not_run = [], [], []
        for folder in sorted(p for p in args.out.iterdir() if p.is_dir()):
            if not (folder / "response.md").is_file():
                not_run.append(f"- {folder.name}: NOT_RUN (no agent response in this run)")
                continue
            try:
                verdict = parse_verdict((folder / "verdict.json").read_text(encoding="utf-8"))
            except (OSError, ValueError) as exc:  # an infrastructure failure is recorded, never a pass or a fail
                failures.append(f"- {folder.name}: NOT_JUDGED_INFRA ({type(exc).__name__})")
                continue
            rows.append(f"### {folder.name}: {verdict['verdict']}\n\n{verdict['justification']}\n\n"
                        + "\n".join(f"- {k}: {v}" for k, v in verdict.get("dimensions", {}).items())
                        + f"\n\nResponse: [{folder.name}.response.md]({folder.name}.response.md)")
            args.results.mkdir(parents=True, exist_ok=True)
            shutil.copy2(folder / "response.md", args.results / f"{folder.name}.response.md")
        header = (f"# Semantic Skill evaluation — {date.today().isoformat()}\n\n"
                  f"Revision `{_revision()}`. Evaluated agent: {args.agent}. Judge: {args.judge} (separate context, private rubric).\n"
                  "Verdicts are semantic judgments, not scores; REVIEW needs a human.\n\n")
        args.results.mkdir(parents=True, exist_ok=True)
        tail = ("\n\n## Not judged\n" + "\n".join(failures) if failures else "") + ("\n\n## Not run\n" + "\n".join(not_run) if not_run else "")
        (args.results / "README.md").write_text(header + "\n\n".join(rows) + tail + "\n", encoding="utf-8")
    return 0


if __name__ == "__main__":
    sys.exit(main())
