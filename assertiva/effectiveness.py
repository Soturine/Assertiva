"""Test effectiveness: what each test proves, judged the same way in every language.

Adapters translate a language's tests into ``TestFacts`` (what is asserted and how strongly, what is replaced by
doubles, which boundaries are crossed or simulated, what is observed, which smells appear, the declared level).
The rules below read only facts, so `status == 400` in one framework and in another, or a broad expected error
in any language, are judged alike. Results are candidates with their basis, never verdicts and never a score:
INFERRED (a static pattern), CONFIRMED (an execution or mutation showed it, or the fact is structural in the source:
identical literal parameter rows are a repetition, while what that repetition costs stays inferred), UNKNOWN
(cannot be decided here).
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
    "NO_OP_ASSERTION": "a mock check is referenced but never called, or misspelled so that the mock answers it with a new "
                       "attribute: it checks nothing",
    "SELF_REFERENTIAL_ORACLE": "the expected value is computed by the same call as the actual one: the test passes whatever "
                               "the code returns",
}
SMELL_NOTES = {
    "SLEEP": "a fixed sleep stands in for synchronization (slow, and flaky when the wait is too short)",
    "FIXED_WAIT": "a fixed wait stands in for waiting on a condition",
    "RETRY": "retries are configured: a pass may hide intermittent failures",
    "EXCESSIVE_MOCKING": "many collaborators are replaced: the test may verify the doubles more than the code",
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
    parameters: tuple[str, ...] = ()  # parameter rows as written, when visible
    parameter_expressions: tuple[str, ...] = ()  # the rows among them whose values are computed when the test runs
    component: str = ""  # the nearest directory with its own manifest: tests of different components test different subjects
    # where the expected values visibly come from: PROPERTY, SCHEMA (a contract the test states) or SNAPSHOT,
    # GOLDEN_FILE, APPROVAL (recorded output: characterization). A literal expected value shows neither.
    basis_signals: tuple[str, ...] = ()
    # how close to the real thing each boundary is exercised, "BOUNDARY:RUNG" (see LADDER)
    rungs: tuple[str, ...] = ()


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
            # different setup test different inputs and are never nominated, and parameter rows are setup too
            if f.body_signature and f.oracles:
                signatures[(f.component, f.body_signature, tuple(sorted(f.boundaries)), tuple(sorted(f.simulated)), f.declared_level,
                            tuple(sorted(f.parameters)))].append(f)
        for (_, _, boundaries, simulated, level, _), same in signatures.items():
            if len(same) > 1:
                out.append(Candidate("REDUNDANCY", _ids(same),
                                     f"{len(same)} test(s) have the same body (setup, call and checks) with the same boundaries and fidelity",
                                     "identical tests at the same level add no distinct evidence (other platforms, configurations or "
                                     "matrices can still make them distinct: check how they run)",
                                     "per-test mutation kills (killedBy) or a negative control: does each one detect something the others miss?",
                                     "review together; consolidate only after the candidate shows equal regression, coverage and mutation results",
                                     language=language, detail={"boundaries": list(boundaries), "simulated": list(simulated), "level": level,
                                                                "repetition": "IDENTICAL_BODY", "redundancy": "INFERRED"}))
        for f in group:
            rows = Counter(f.parameters)
            computed = set(f.parameter_expressions)
            literal = [row for row, n in rows.items() if n > 1 and row not in computed]
            expressions = [row for row, n in rows.items() if n > 1 and row in computed]
            if literal:
                # the repetition is a fact of the source; that it adds nothing is the inference (state, order or time
                # can make a second run of the same input meaningful)
                out.append(Candidate("DUPLICATE_CASES", [f.test_id], f"the literal parameter rows {literal[:5]} appear more than once in the table",
                                     "the same fixed input runs again; unless the test depends on shared state, order or time, "
                                     "the repeated row adds no evidence",
                                     "the parameter table", "remove the repeated rows or replace them with a partition not yet covered",
                                     basis="CONFIRMED", language=language,
                                     detail={"repetition": "IDENTICAL_LITERAL_ROWS", "rows": literal[:MAX_LISTED],
                                             "redundancy": "INFERRED", "computed_rows": expressions[:MAX_LISTED]}))
            elif expressions:
                out.append(Candidate("DUPLICATE_CASES", [f.test_id], f"the parameter rows {expressions[:5]} are written the same way more than once",
                                     "rows written alike but computed when the test runs may still produce different values "
                                     "(factories, counters, random or time-dependent data)",
                                     "the values each row produces (the runner's parameter ids) and the code that builds them",
                                     "if the rows produce the same values, remove the repeats or replace them with a partition not yet covered",
                                     language=language,
                                     detail={"repetition": "IDENTICAL_ROW_EXPRESSIONS", "rows": expressions[:MAX_LISTED], "redundancy": "INFERRED"}))
        smells = Counter(s for f in group for s in f.smells if s in SMELL_NOTES)
        for smell, count in sorted(smells.items()):
            hit = [f for f in group if smell in f.smells]
            out.append(Candidate("SMELL", _ids(hit), f"{count} test(s) show {smell}", SMELL_NOTES[smell],
                                 "the test's history (flaky reruns) or a review of the setup", "replace with condition-based synchronization, "
                                 "fewer doubles or named assertions where it helps diagnosis; a smell is a lead, not a verdict",
                                 language=language, detail={"smell": smell}))
    return out


def _test_label(run, test_id: str) -> str:
    """A detecting test as people know it: its name and file when the report gives them, otherwise the tool's id
    prefixed by the tool (numeric ids such as "2" are only unique within one report)."""
    name, where = run.test_names.get(test_id), run.test_locations.get(test_id)
    if name:
        return f"{name} ({where})" if where else name
    return test_id if where or not test_id.isdigit() else f"{run.tool or 'mutation'}#{test_id}"


def mutation_contribution(runs) -> dict:
    """Which tests detect which mutants, from reports that name the killing tests; exclusive vs shared detection.
    Not proof of equivalence: a test that killed no known mutant may still guard behavior no mutant touched.

    With complete killer matrices from runs tied to this state, also which tests detect only mutants another test
    detects too (``subsumed``) and which detect exactly the same ones (``same_detection``): evidence on the known
    mutants for the agent to weigh, never a reason to remove a test on its own."""
    kills: dict[str, set[str]] = defaultdict(set)
    survivors = 0
    with_killers = 0
    for index, run in enumerate(runs):
        for mutant in getattr(run, "mutants", []):
            if mutant.status.value == "SURVIVED":
                survivors += 1
            if mutant.killed_by:
                with_killers += 1
                identity = f"{index}:{mutant.stable_id or mutant.mutant_id}"
                for test in mutant.killed_by:
                    kills[_test_label(run, test)].add(identity)
    if not kills:
        return {"available": False, "reason": "no mutation report names the tests that killed each mutant"}
    owners: dict[str, list[str]] = defaultdict(list)
    for test, mutants in kills.items():
        for mutant in mutants:
            owners[mutant].append(test)
    exclusive = {test: sorted(m for m in mutants if owners[m] == [test]) for test, mutants in kills.items()}
    with_matrix = [run for run in runs if any(m.killed_by for m in getattr(run, "mutants", []))]
    complete = all(getattr(run, "killers_complete", None) is True for run in with_matrix)
    tied = all(getattr(run, "matches_state", None) is True for run in with_matrix)
    subsumed: dict[str, list[str]] = {}
    same: list[list[str]] = []
    if complete and tied:
        groups: dict[frozenset, list[str]] = defaultdict(list)
        for test, mutants in kills.items():
            groups[frozenset(mutants)].append(test)
        same = sorted(sorted(g) for g in groups.values() if len(g) > 1)
        for test, mutants in sorted(kills.items()):
            wider = sorted(other for other, theirs in kills.items() if mutants < theirs)
            if wider:
                subsumed[test] = wider[:5]
    return {
        "available": True, "mutants_with_killers": with_killers, "survivors": survivors,
        "tests": {test: {"kills": len(mutants), "exclusive": len(exclusive[test])} for test, mutants in sorted(kills.items())},
        "exclusive_protection": {t: [m.split(":", 1)[1] for m in ms[:10]] for t, ms in exclusive.items() if ms},
        "tied": tied,
        "subsumed": subsumed,
        "same_detection": same[:MAX_LISTED],
        "subsumption_note": ("on the known mutants only: a subsumed test may still check behavior no mutant changed, a "
                             "contract, or a level the wider test does not reach; weigh it with the tests' intent, never "
                             "remove on this alone" if complete and tied else
                             "not computed: needs complete killer matrices from runs tied to this state"),
        # kills are a lower bound and "exclusive" means "the only named detector" unless every report records all
        # detecting tests (tools stop at the first failing test by default)
        "killers_complete": complete,
        "note": "per-test detection of known mutants: a test that killed none may still protect behavior no mutant changed"
                + ("" if complete else "; the reports name only the first detecting test of each mutant, so kills are a lower "
                                       "bound and an exclusive detector may have unrecorded peers"),
    }


# from furthest to closest to production: a replaced collaborator, requests caught at the boundary, a fake
# implementation of it, the real code in the same process, a real service made for the test, the real thing
LADDER = ("DOUBLE", "INTERCEPTED", "SIMULATOR", "IN_PROCESS", "DISPOSABLE_REAL", "REAL")


def fidelity_ladder(facts: list[TestFacts]) -> dict:
    """Per boundary, how many tests reach each rung (a test counts once per boundary, at the rung its code shows)."""
    ladder: dict[str, Counter] = defaultdict(Counter)
    for f in facts:
        for item in f.rungs:
            boundary, rung = item.split(":", 1)
            ladder[boundary][rung] += 1
    return {"rungs": list(LADDER), "boundaries": {b: {r: c[r] for r in LADDER if c[r]} for b, c in sorted(ladder.items())},
            "note": "read from test code: a rung says how the boundary is exercised, not that the run reached it (a browser "
                    "test that was not executed proves nothing); REAL for a device means an emulator or a device"}


CONTRACT_SIGNALS = frozenset({"PROPERTY", "SCHEMA"})
CHARACTERIZATION_SIGNALS = frozenset({"SNAPSHOT", "GOLDEN_FILE", "APPROVAL"})


def oracle_basis(facts: list[TestFacts]) -> dict:
    """Which tests state a contract and which pin recorded output, as far as the code shows it. A literal expected value
    (``assert total == 1500``) may come from a specification or from what the code returned when the test was written:
    only its origin settles that, so such tests are UNDETERMINED, never counted as contracts."""
    contract = [f.test_id for f in facts if CONTRACT_SIGNALS & set(f.basis_signals)]
    pinned = [f.test_id for f in facts if CHARACTERIZATION_SIGNALS & set(f.basis_signals)]
    both = set(contract) & set(pinned)
    undetermined = [f.test_id for f in facts if f.oracles and not set(f.basis_signals) & (CONTRACT_SIGNALS | CHARACTERIZATION_SIGNALS)]
    return {
        "contract": len(contract), "characterization": len(pinned), "both": len(both), "undetermined": len(undetermined),
        "signals": dict(Counter(s for f in facts for s in f.basis_signals)),
        "characterization_tests": [t for t in pinned if t not in both][:MAX_LISTED],
        "note": "characterization pins today's behavior, bugs included, and fails on any change; a contract states what must "
                "hold. Literal expected values are undetermined: read where the value comes from (a requirement, a "
                "calculation, or the code's own output)",
    }


def summarize(facts: list[TestFacts], limitations: dict[str, list[str]], mutation_runs=()) -> dict:
    """The effectiveness view of a project: per dimension, per language, the candidates; never a single score."""
    found = candidates(facts)
    languages = Counter(f.language for f in facts)
    oracles = Counter(o for f in facts for o in f.oracles)
    no_oracle = [f.test_id for f in facts if not f.oracles]
    dimensions = {
        "oracle_strength": {"oracles": dict(oracles), "without_explicit_oracle": len(no_oracle),
                            "note": "no explicit oracle can still be a valid contract (must not raise, a guard double): read the test",
                            "oracle_basis": oracle_basis(facts)},
        "behavioral_surfaces": dict(Counter(s for f in facts for s in f.surfaces)),
        "negative_and_boundary_paths": {"error_expectations": sum(bool({"SPECIFIC_ERROR", "BROAD_ERROR"} & set(f.oracles)) for f in facts),
                                        "broad": sum("BROAD_ERROR" in f.oracles for f in facts)},
        "fidelity": {"ladder": fidelity_ladder(facts),
                     "declared_levels": dict(Counter(f.declared_level or "UNDECLARED" for f in facts)),
                     "boundaries_crossed": dict(Counter(b for f in facts for b in set(f.boundaries) - set(f.simulated))),
                     "boundaries_simulated": dict(Counter(b for f in facts for b in f.simulated))},
        "double_fidelity": {"tests_with_doubles": sum(bool(f.doubles) for f in facts),
                            "most_replaced": Counter(d for f in facts for d in f.doubles).most_common(5)},
        "distinct_contribution": {"redundancy_candidates": sum(c.kind == "REDUNDANCY" for c in found),
                                  "tests_in_redundancy_candidates": len({t for c in found if c.kind == "REDUNDANCY" for t in c.tests}),
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
        # a test can carry several patterns and appear in several candidates: signals count (test, pattern) pairs,
        # affected tests count each test once per kind (computed before the lists are shortened)
        "affected_tests": {kind: len({t for c in found if c.kind == kind for t in c.tests}) for kind in sorted({c.kind for c in found})},
        "note": "candidates are leads with their basis; none is a verdict, and no score combines them",
    }


def metrics(summary: dict) -> dict[str, int]:
    """Counts that can be compared between states (baseline vs candidate); fewer candidates is better only when
    the same tests were analyzed, which the comparison states. ``false_green_candidates`` counts signals (a test
    with two patterns counts twice, as in 0.7.2); ``false_green_tests`` counts the distinct tests behind them."""
    kinds = Counter(c["kind"] for c in summary.get("candidates", []))
    affected = summary.get("affected_tests", {})
    return {
        "false_green_candidates": sum(c.get("count", len(c["tests"])) for c in summary.get("candidates", []) if c["kind"] == "FALSE_GREEN"),
        "false_green_tests": affected.get("FALSE_GREEN", 0),
        "fidelity_mismatches": sum(c.get("count", len(c["tests"])) for c in summary.get("candidates", []) if c["kind"] == "FIDELITY_MISMATCH"),
        "redundancy_candidates": kinds.get("REDUNDANCY", 0),
        "redundancy_tests": affected.get("REDUNDANCY", 0),
        "distinct_oracle_signatures": summary.get("dimensions", {}).get("distinct_contribution", {}).get("distinct_oracle_signatures", 0),
    }
