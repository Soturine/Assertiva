"""Consumer-driven contracts (Pact): contract files and provider verification results.

A verification run says "passed" in cases that verified nothing, and the evidence keeps them apart:

- EMPTY: the run checked no interaction (a contract without interactions verifies "successfully");
- PENDING_FAILURES: interactions marked pending failed without failing the run, so they are not verified;
- FAILED: a non-pending interaction did not match what the consumer expects;
- VERIFIED: every interaction the run checked matched, none pending.

A contract file read without verification results is NOT_VERIFIED: it states what a consumer expects, not that the
provider does it. Results are verification JSON as the Pact Rust core writes it (``pact_verifier_cli --json``,
pact-python's ``Verifier.results``); contract files are Pact JSON (V2 to V4).
"""

from __future__ import annotations

import json
from pathlib import Path

VERIFIED, FAILED, PENDING_FAILURES, EMPTY, NOT_VERIFIED = "VERIFIED", "FAILED", "PENDING_FAILURES", "EMPTY", "NOT_VERIFIED"


def _contract(data: dict, source: str) -> dict:
    interactions = data.get("interactions") or data.get("messages") or []
    states = sorted({(s.get("name") if isinstance(s, dict) else str(s)) for i in interactions
                     for s in (i.get("providerStates") or ([{"name": i["providerState"]}] if i.get("providerState") else []))})
    spec = ((data.get("metadata") or {}).get("pactSpecification") or (data.get("metadata") or {}).get("pact-specification") or {}).get("version")
    return {"source": source, "kind": "contract", "consumer": (data.get("consumer") or {}).get("name"),
            "provider": (data.get("provider") or {}).get("name"), "specification": spec,
            "interactions": len(interactions), "pending": sum(bool(i.get("pending")) for i in interactions),
            "provider_states": states, "status": EMPTY if not interactions else NOT_VERIFIED}


def _verification(data: dict, source: str) -> dict:
    results = data.get("interactionResults") or []
    rows = []
    for item in results:
        ok = str(item.get("result")).upper() == "OK"
        mismatches = [m.get("mismatch") for m in ((item.get("mismatch") or {}).get("mismatches") or [])]
        rows.append({"description": item.get("description"), "consumer": item.get("consumer"), "pending": bool(item.get("pending")),
                     "provider_states": item.get("providerStates") or [], "matched": ok, "mismatches": mismatches[:5]})
    failed = [r for r in rows if not r["matched"] and not r["pending"]]
    pending_failed = [r for r in rows if not r["matched"] and r["pending"]]
    status = EMPTY if not rows else FAILED if failed or data.get("errors") else PENDING_FAILURES if pending_failed else VERIFIED
    return {"source": source, "kind": "verification", "provider": next((i.get("provider") for i in results if i.get("provider")), None),
            "consumers": sorted({r["consumer"] for r in rows if r["consumer"]}), "interactions": len(rows),
            "verified": sum(r["matched"] and not r["pending"] for r in rows), "failed": len(failed), "pending_failed": len(pending_failed),
            "tool_result": data.get("result"), "status": status, "results": rows}


def load_contract_evidence(path: str | Path) -> dict:
    """A Pact contract file or a verification result, recognized by shape; ``error`` when neither."""
    path = Path(path)
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        if isinstance(data, dict) and "interactionResults" in data and "result" in data:
            return _verification(data, path.name)
        if isinstance(data, dict) and "consumer" in data and "provider" in data and ("interactions" in data or "messages" in data):
            return _contract(data, path.name)
        raise ValueError("neither a Pact contract nor a verification result")
    except (OSError, ValueError, TypeError, AttributeError) as exc:
        return {"source": path.name, "kind": None, "status": None, "error": f"{type(exc).__name__}: {exc}"[:300]}


_ADVICE = {
    FAILED: ("high", "fix the provider or agree a new contract with the consumer; the mismatches name what differs"),
    EMPTY: ("medium", "a verification that checks no interaction passes without proving anything; make sure the consumer's "
                      "tests record interactions"),
    PENDING_FAILURES: ("medium", "pending interactions failed without failing the run: they are not verified until the "
                                 "provider satisfies them"),
    NOT_VERIFIED: ("low", "verify the provider against this contract and import the verification result"),
}


def findings(evidence: dict) -> list:
    """One finding for a contract or verification that is not VERIFIED (nothing for an unreadable file: it has an error)."""
    from assertiva.models import Finding

    status = evidence.get("status")
    if status not in _ADVICE:
        return []
    severity, recommendation = _ADVICE[status]
    who = evidence.get("consumer") or ", ".join(evidence.get("consumers") or []) or "a consumer"
    summary = f"{evidence['source']}: contract between {who} and {evidence.get('provider') or 'a provider'} is {status}"
    detail = {k: evidence.get(k) for k in ("source", "kind", "provider", "interactions", "failed", "pending_failed") if k in evidence}
    if evidence.get("results"):
        detail["mismatches"] = [f"{r['description']}: {m}" for r in evidence["results"] if not r["matched"] for m in r["mismatches"]][:5]
    if status == FAILED:
        return [Finding("CONTRACT_VERIFICATION_FAILED", summary, detail, severity=severity, recommendation=recommendation)]
    if status == EMPTY:
        return [Finding("CONTRACT_EMPTY", summary, detail, severity=severity, recommendation=recommendation)]
    if status == PENDING_FAILURES:
        return [Finding("CONTRACT_PENDING_FAILURES", summary, detail, severity=severity, recommendation=recommendation)]
    return [Finding("CONTRACT_NOT_VERIFIED", summary, detail, severity=severity, recommendation=recommendation)]
