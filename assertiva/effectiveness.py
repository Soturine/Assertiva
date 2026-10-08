"""Test effectiveness: what each test proves, judged the same way in every language.

Adapters translate a language's tests into ``TestFacts`` (what is asserted and how strongly, what is replaced by
doubles, which boundaries are crossed or simulated, what is observed, which smells appear, the declared level).
The rules below read only facts, so `status == 400` in one framework and in another, or a broad expected error
in any language, are judged alike. Results are candidates with their basis, never verdicts and never a score:
INFERRED (a static pattern), CONFIRMED (an execution or mutation showed it), UNKNOWN (cannot be decided here).
Similarity only nominates candidates for review; nothing is ever removed because of it.
"""

from __future__ import annotations

from collections import Counter, defaultdict
from dataclasses import dataclass, field

WEAK_ORACLES = frozenset({"EXISTENCE", "TRUTHY", "STATUS_ONLY", "BROAD_ERROR"})
STRONG_ORACLES = frozenset({"VALUE", "SPECIFIC_ERROR", "INTERACTION", "GUARD", "HELPER", "STATE"})
FALSE_GREEN_SMELLS = {
    "SWALLOWED_EXCEPTION": "an exception is caught and ignored, so the test passes whether or not the code fails",
    "CONDITIONAL_ASSERTION": "every assertion sits behind a condition, so a run where it is false asserts nothing",
    "TAUTOLOGY": "an assertion compares a value with itself or a constant with a constant: it cannot fail",
    "UNAWAITED_ASYNC": "asynchronous work is started but never awaited, so its failure cannot fail the test",
    "ACTION_WITHOUT_CHECK": "a user action is performed and nothing checks what it did",
    "SNAPSHOT_ONLY": "the only oracle is a snapshot, which an update accepts without review",
}
SMELL_NOTES = {
    "SLEEP": "a fixed sleep stands in for synchronization (slow, and flaky when the wait is too short)",
    "FIXED_WAIT": "a fixed wait stands in for waiting on a condition",
    "RETRY": "retries are configured: a pass may hide intermittent failures",
    "EXCESSIVE_MOCKING": "many collaborators are replaced: the test may verify the doubles more than the code",
    "ASSERTION_ROULETTE": "many unlabeled assertions: a failure is hard to diagnose",
    "MYSTERY_GUEST": "the test reads an external file or resource the reader cannot see",
}
DIMENSIONS = ("oracle_strength", "behavioral_surfaces", "negative_and_boundary_paths", "fidelity", "double_fidelity",
              "distinct_contribution", "mutation_sensitivity", "determinism", "maintainability")
MAX_LISTED = 20


@dataclass(frozen=True)
class TestFacts:
    """One test as evidence: normalized across languages, with the language and how the facts were obtained."""

    test_id: str
    path: str
    language: str
    oracles: tuple[str, ...] = ()  # VALUE, STATE, EXISTENCE, TRUTHY, STATUS_ONLY, BROAD_ERROR, SPECIFIC_ERROR, INTERACTION, GUARD, HELPER, SNAPSHOT
    assertions: int = 0
    doubles: tuple[str, ...] = ()  # what the test replaces, as written
    boundaries: tuple[str, ...] = ()  # boundaries the test exercises: HTTP, DATABASE, BROWSER, DEVICE, FILESYSTEM, NETWORK, PROCESS
    simulated: tuple[str, ...] = ()  # boundaries replaced by doubles, interception or simulators
    surfaces: tuple[str, ...] = ()  # RETURN, EXCEPTION, STATE, PERSISTENCE, RESPONSE_BODY, RESPONSE_STATUS, UI, INTERACTION
    smells: tuple[str, ...] = ()
    declared_level: str | None = None  # UNIT, INTEGRATION, FUNCTIONAL, CONTRACT, E2E (from paths, markers, annotations, tooling)
    oracle_signature: str = ""  # normalized asserted expressions (same text = same check)
    body_signature: str = ""  # normalized body (copies)
    parameters: tuple[str, ...] = ()  # literal parameter rows, when visible
    component: str = ""  # the nearest directory with its own manifest: tests of different components test different subjects


@dataclass
class Candidate:
    kind: str  # FALSE_GREEN, WEAK_ORACLE, FIDELITY_MISMATCH, REDUNDANCY, DUPLICATE_CASES, SMELL
    tests: list[str]
    shows: str  # what the evidence actually demonstrates
    why: str  # why the test may be weak, misleading or redundant
    resolve_with: str  # the evidence that would settle it
    recommendation: str
    basis: str = "INFERRED"
    contract: str | None = None
    language: str | None = None
    detail: dict = field(default_factory=dict)


def _ids(facts: list[TestFacts]) -> list[str]:
    return [f.test_id for f in facts]


def candidates(facts: list[TestFacts]) -> list[Candidate]:
    out: list[Candidate] = []
    by_language: dict[str, list[TestFacts]] = defaultdict(list)
    for f in facts:
        by_language[f.language].append(f)
    for language, group in sorted(by_language.items()):
        for smell, why in FALSE_GREEN_SMELLS.items():
            hit = [f for f in group if smell in f.smells]
            if hit:
                out.append(Candidate("FALSE_GREEN", _ids(hit), f"{len(hit)} test(s) show the pattern {smell} in their source",
                                     why, "a deliberate behavior break (negative control or mutant) in a disposable copy: does the test fail?",
                                     "make the check unconditional and specific to the behavior; await what the test starts",
                                     language=language, detail={"pattern": smell, "count": len(hit)}))
        weak = [f for f in group if f.oracles and set(f.oracles) <= WEAK_ORACLES]
        if weak:
            kinds = Counter(o for f in weak for o in f.oracles)
            out.append(Candidate("WEAK_ORACLE", _ids(weak), f"{len(weak)} test(s) assert only {', '.join(sorted(kinds))}",
                                 "existence, truthiness, a bare status or any error lets wrong values pass when the contract is more specific",
                                 "the contract each test claims (name, requirement) and the code under test; a mutant of the checked behavior",
                                 "assert the values, state and error details the contract specifies; keep the test when presence is the contract",
                                 language=language, detail={"oracles": dict(kinds)}))
        for level in ("INTEGRATION", "E2E"):
            claimed = [f for f in group if f.declared_level == level]
            fake = [f for f in claimed if f.simulated and not (set(f.boundaries) - set(f.simulated))]
            if fake:
                out.append(Candidate("FIDELITY_MISMATCH", _ids(fake),
                                     f"{len(fake)} test(s) declared {level.lower()} replace every boundary they cross ({', '.join(sorted({s for f in fake for s in f.simulated}))})",
                                     f"a {level.lower()} test whose dependencies are all simulated proves the code against the doubles, not the integration",
                                     "a run against a disposable real dependency (service, browser, backend) for the same behavior",
                                     "keep the fast simulated test as such, and add (or move) one check that crosses the real boundary",
                                     language=language, detail={"level": level}))
        signatures: dict[tuple, list[TestFacts]] = defaultdict(list)
        for f in group:
            # the same body (setup, call, checks) with the same boundaries and fidelity: same assertions after a
            # different setup test different inputs and are never nominated
            if f.body_signature and f.oracles:
                signatures[(f.component, f.body_signature, tuple(sorted(f.boundaries)), tuple(sorted(f.simulated)), f.declared_level)].append(f)
        for (_, _, boundaries, simulated, level), same in signatures.items():
            if len(same) > 1:
                out.append(Candidate("REDUNDANCY", _ids(same),
                                     f"{len(same)} test(s) have the same body (setup, call and checks) with the same boundaries and fidelity",
                                     "identical tests at the same level add no distinct evidence (other platforms, configurations or "
                                     "matrices can still make them distinct: check how they run)",
                                     "per-test mutation kills (killedBy) or a negative control: does each one detect something the others miss?",
                                     "review together; consolidate only after the candidate shows equal regression, coverage and mutation results",
                                     language=language, detail={"boundaries": list(boundaries), "simulated": list(simulated), "level": level}))
        for f in group:
            rows = Counter(f.parameters)
            duplicated = [row for row, n in rows.items() if n > 1]
            if duplicated:
                out.append(Candidate("DUPLICATE_CASES", [f.test_id], f"the parameter rows {duplicated[:5]} appear more than once",
                                     "a repeated row runs the same partition again and adds no evidence",
                                     "the parameter table", "remove the repeated rows or replace them with a partition not yet covered",
                                     basis="CONFIRMED", language=language))
        smells = Counter(s for f in group for s in f.smells if s in SMELL_NOTES)
        for smell, count in sorted(smells.items()):
            hit = [f for f in group if smell in f.smells]
            out.append(Candidate("SMELL", _ids(hit), f"{count} test(s) show {smell}", SMELL_NOTES[smell],
                                 "the test's history (flaky reruns) or a review of the setup", "replace with condition-based synchronization, "
                                 "fewer doubles or named assertions where it helps diagnosis; a smell is a lead, not a verdict",
                                 language=language, detail={"smell": smell}))
    return out


def mutation_contribution(runs) -> dict:
    """Which tests detect which mutants, from reports that name the killing tests; exclusive vs shared detection.
    Not proof of equivalence: a test that killed no known mutant may still guard behavior no mutant touched."""
    kills: dict[str, set[str]] = defaultdict(set)
    survivors = 0
    with_killers = 0
    for run in runs:
        for mutant in getattr(run, "mutants", []):
            if mutant.status.value == "SURVIVED":
                survivors += 1
            if mutant.killed_by:
                with_killers += 1
                for test in mutant.killed_by:
                    kills[test].add(mutant.mutant_id)
    if not kills:
        return {"available": False, "reason": "no mutation report names the tests that killed each mutant"}
    owners: dict[str, list[str]] = defaultdict(list)
    for test, mutants in kills.items():
        for mutant in mutants:
            owners[mutant].append(test)
    exclusive = {test: sorted(m for m in mutants if owners[m] == [test]) for test, mutants in kills.items()}
    return {
        "available": True, "mutants_with_killers": with_killers, "survivors": survivors,
        "tests": {test: {"kills": len(mutants), "exclusive": len(exclusive[test])} for test, mutants in sorted(kills.items())},
        "exclusive_protection": {t: m[:10] for t, m in exclusive.items() if m},
        "note": "per-test detection of known mutants: a test that killed none may still protect behavior no mutant changed",
    }


def summarize(facts: list[TestFacts], limitations: dict[str, list[str]], mutation_runs=()) -> dict:
    """The effectiveness view of a project: per dimension, per language, the candidates; never a single score."""
    found = candidates(facts)
    languages = Counter(f.language for f in facts)
    oracles = Counter(o for f in facts for o in f.oracles)
    no_oracle = [f.test_id for f in facts if not f.oracles]
    dimensions = {
        "oracle_strength": {"oracles": dict(oracles), "without_explicit_oracle": len(no_oracle),
                            "note": "no explicit oracle can still be a valid contract (must not raise, a guard double): read the test"},
        "behavioral_surfaces": dict(Counter(s for f in facts for s in f.surfaces)),
        "negative_and_boundary_paths": {"error_expectations": sum(bool({"SPECIFIC_ERROR", "BROAD_ERROR"} & set(f.oracles)) for f in facts),
                                        "broad": sum("BROAD_ERROR" in f.oracles for f in facts)},
        "fidelity": {"declared_levels": dict(Counter(f.declared_level or "UNDECLARED" for f in facts)),
                     "boundaries_crossed": dict(Counter(b for f in facts for b in set(f.boundaries) - set(f.simulated))),
                     "boundaries_simulated": dict(Counter(b for f in facts for b in f.simulated))},
        "double_fidelity": {"tests_with_doubles": sum(bool(f.doubles) for f in facts),
                            "most_replaced": Counter(d for f in facts for d in f.doubles).most_common(5)},
        "distinct_contribution": {"redundancy_candidates": sum(c.kind == "REDUNDANCY" for c in found),
                                  "distinct_oracle_signatures": len({f.oracle_signature for f in facts if f.oracle_signature})},
        "mutation_sensitivity": mutation_contribution(mutation_runs),
        "determinism": {s: sum(s in f.smells for f in facts) for s in ("SLEEP", "FIXED_WAIT", "RETRY", "UNAWAITED_ASYNC")},
        "maintainability": dict(Counter(s for f in facts for s in f.smells if s in SMELL_NOTES)),
    }
    return {
        "languages": {lang: {"tests": n, "limitations": limitations.get(lang, [])} for lang, n in sorted(languages.items())},
        "dimensions": dimensions,
        # each candidate lists up to MAX_LISTED tests and counts all of them, so a review can state its scope
        "candidates": [{**c.__dict__, "tests": c.tests[:MAX_LISTED], "count": len(c.tests)} for c in found],
        "note": "candidates are leads with their basis; none is a verdict, and no score combines them",
    }


def metrics(summary: dict) -> dict[str, int]:
    """Counts that can be compared between states (baseline vs candidate); fewer candidates is better only when
    the same tests were analyzed, which the comparison states."""
    kinds = Counter(c["kind"] for c in summary.get("candidates", []))
    return {
        "false_green_candidates": sum(c.get("count", len(c["tests"])) for c in summary.get("candidates", []) if c["kind"] == "FALSE_GREEN"),
        "fidelity_mismatches": sum(c.get("count", len(c["tests"])) for c in summary.get("candidates", []) if c["kind"] == "FIDELITY_MISMATCH"),
        "redundancy_candidates": kinds.get("REDUNDANCY", 0),
        "distinct_oracle_signatures": summary.get("dimensions", {}).get("distinct_contribution", {}).get("distinct_oracle_signatures", 0),
    }
