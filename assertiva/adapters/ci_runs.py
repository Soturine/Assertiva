"""Observed CI runs, as the provider reported them (JSON the user or the agent exported), read never fetched.

GitHub: ``gh run view <id> --json headSha,conclusion,status,jobs,url,workflowName,event,headBranch`` (or one
element of ``gh run list --json ...``). GitLab: a pipeline from the API (``/projects/:id/pipelines/:pipeline_id``)
with ``sha`` and ``status``, optionally ``jobs`` from ``/pipelines/:id/jobs``. A run proves a revision only when
its head SHA equals the audited one and the working tree has no local changes; anything else is reported as such.
"""

from __future__ import annotations

import json
from pathlib import Path

_GREEN = {"success", "passed"}


def _jobs(raw) -> list[dict]:
    out = []
    for job in raw or []:
        if isinstance(job, dict):
            out.append({"name": str(job.get("name") or job.get("workflowName") or ""),
                        "conclusion": str(job.get("conclusion") or job.get("status") or "").lower() or None})
    return out


def load_ci_run(path: str | Path) -> dict:
    """Normalized provider run: provider, id/url, head_sha, conclusion, jobs; ``error`` when unreadable."""
    path = Path(path)
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        if isinstance(data, list):
            if len(data) != 1:
                raise ValueError(f"expected one run, found {len(data)}; export a single run")
            data = data[0]
        if not isinstance(data, dict):
            raise ValueError("not a JSON object")
        if "headSha" in data:
            return {"provider": "github-actions", "source": str(path), "id": data.get("databaseId"), "url": data.get("url"),
                    "name": data.get("workflowName") or data.get("name"), "head_sha": data["headSha"], "branch": data.get("headBranch"),
                    "event": data.get("event"), "conclusion": (data.get("conclusion") or data.get("status") or "").lower() or None,
                    "jobs": _jobs(data.get("jobs"))}
        if "sha" in data and ("status" in data or "web_url" in data):
            return {"provider": "gitlab-ci", "source": str(path), "id": data.get("id"), "url": data.get("web_url"),
                    "name": data.get("name"), "head_sha": data["sha"], "branch": data.get("ref"), "event": data.get("source"),
                    "conclusion": str(data.get("status") or "").lower() or None, "jobs": _jobs(data.get("jobs"))}
        raise ValueError("not a recognized provider run (GitHub `gh run view --json headSha,...` or a GitLab pipeline)")
    except (OSError, ValueError, KeyError, TypeError) as exc:
        return {"source": str(path), "error": f"{type(exc).__name__}: {exc}"[:300]}


def identity(run: dict, revision: str | None, dirty: bool | None) -> str:
    """SAME_REVISION (proves this revision), LOCAL_CHANGES (same commit, tree differs), OTHER_REVISION, UNKNOWN."""
    if run.get("error") or not revision or not run.get("head_sha"):
        return "UNKNOWN"
    if run["head_sha"].lower() != revision.lower():
        return "OTHER_REVISION"
    return "LOCAL_CHANGES" if dirty else "SAME_REVISION"


def green(run: dict) -> bool:
    return (run.get("conclusion") or "") in _GREEN
