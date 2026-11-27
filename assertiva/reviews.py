"""Independent reviews: a second opinion recorded with what makes it independent or not.

The host agent is the first choice; a review by another model, a local model or a human is optional and recorded only
when it happened. The engine does not call any provider. It validates the record: who reviewed (as far as it is
known), how that reviewer relates to the author, what was sent where and under which consent, what it cost when
measured, and the outcome. A review never changes an engine fact or a coverage status: agreement is not ground
truth, and a disagreement is settled by a source or an experiment, not by a vote.
"""

from __future__ import annotations

from typing import Any

from .sanitize import sanitize_message

RELATIONS = ("SAME_AGENT", "SAME_MODEL", "SAME_FAMILY", "DIFFERENT_FAMILY", "LOCAL_MODEL", "HUMAN", "TOOL", "UNKNOWN")
OUTCOMES = ("AGREES", "DISAGREES", "PARTIAL", "INCONCLUSIVE", "NOT_RUN", "BLOCKED", "INVALID_RESPONSE")
TRANSMISSION = ("NONE", "LOCAL_ONLY", "EXTERNAL")
CONSENT = ("USER_AUTHORIZED", "NOT_NEEDED", "NOT_GIVEN")
INDEPENDENCE = {"SAME_AGENT": "NONE", "SAME_MODEL": "LOW", "SAME_FAMILY": "LOW", "DIFFERENT_FAMILY": "PARTIAL",
                "LOCAL_MODEL": "PARTIAL", "HUMAN": "PARTIAL", "TOOL": "PARTIAL", "UNKNOWN": "UNKNOWN"}


class ReviewError(ValueError):
    pass


def _choice(value: Any, allowed: tuple, what: str) -> str:
    if value not in allowed:
        raise ReviewError(f"{what} must be one of {', '.join(allowed)}")
    return value


def review(entry: Any) -> dict:
    if not isinstance(entry, dict):
        raise ReviewError("each review is an object")
    scope = entry.get("scope")
    if not isinstance(scope, str) or not scope.strip():
        raise ReviewError("a review states its scope (which findings, behaviors or sources it covered)")
    what = f"review of {scope.strip()[:60]!r}"
    reviewer = entry.get("reviewer") or {}
    if not isinstance(reviewer, dict):
        raise ReviewError(f"{what}: reviewer is an object (kind, provider, model, as far as known)")
    relation = _choice(entry.get("relation_to_author"), RELATIONS, f"{what}: relation_to_author")
    transmission = entry.get("transmission") or {"mode": "NONE"}
    if not isinstance(transmission, dict):
        raise ReviewError(f"{what}: transmission is an object")
    mode = _choice(transmission.get("mode", "NONE"), TRANSMISSION, f"{what}: transmission.mode")
    consent = _choice(transmission.get("consent", "NOT_NEEDED" if mode != "EXTERNAL" else None), CONSENT, f"{what}: transmission.consent")
    if mode == "EXTERNAL" and consent != "USER_AUTHORIZED":
        raise ReviewError(f"{what}: sending material to an external reviewer needs the user's authorization; without it "
                          "the review did not happen (record NOT_RUN)")
    items = transmission.get("items") or []
    if mode == "EXTERNAL" and not items:
        raise ReviewError(f"{what}: an external transmission lists what was sent (files, excerpts), never 'everything'")
    outcome = _choice(entry.get("outcome"), OUTCOMES, f"{what}: outcome")
    evidence = entry.get("evidence") or []
    if outcome in ("AGREES", "DISAGREES", "PARTIAL") and not evidence:
        raise ReviewError(f"{what}: an outcome that says something cites what the reviewer pointed at")
    cost = entry.get("cost") or {}
    if not isinstance(cost, dict):
        raise ReviewError(f"{what}: cost is an object of measured values (tokens, seconds, currency) or empty when unknown")
    return {
        "scope": sanitize_message(scope.strip(), limit=300),
        "reviewer": {k: sanitize_message(str(reviewer.get(k) or "unknown"), limit=120) for k in ("kind", "host", "provider", "model")},
        "relation_to_author": relation, "independence": INDEPENDENCE[relation],
        "transmission": {"mode": mode, "consent": consent, "items": [sanitize_message(str(i), limit=200) for i in items][:50]},
        "outcome": outcome, "evidence": [sanitize_message(str(e), limit=300) for e in evidence][:50],
        "cost": {k: v for k, v in cost.items() if isinstance(k, str) and isinstance(v, (int, float))} or "UNKNOWN",
        "effect": "recorded beside the agent's conclusions; never changes an engine fact or a coverage status",
    }


def apply_reviews(data: dict) -> list[dict]:
    entries = data.get("reviews") or []
    if not isinstance(entries, list):
        raise ReviewError("reviews must be a list")
    return [review(e) for e in entries]
