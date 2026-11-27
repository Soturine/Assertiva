# FTD v2.6.0 → Assertiva 1.1.0 dogfood intake

Intake-only record (2026-11-27). Nothing in Assertiva's code is changed and no fix or version is claimed.
Machine-readable form: [FEEDBACK.json](FEEDBACK.json). Sanitized original feedback file: [evidence/audit.dogfood.json](evidence/audit.dogfood.json).
Synthetic reproducers: [reproducers/](reproducers/). Proposal for routing future feedback: [FEEDBACK_ROUTING_PROPOSAL.md](../FEEDBACK_ROUTING_PROPOSAL.md).

## Instrument and scope

- **Assertiva 1.1.0**, installed from tag `v1.1.0` (`8ff4048`) into its own virtual environment (import origin: that environment's site-packages, not an editable checkout); Windows 11, CPython 3.12.10. Cosmic Ray 8.9.0 in a separate project environment.
- **Audited project:** Functional Test Designer, release qualification of v2.6.0 (public repository `Soturine/functional-test-designer`, candidate `c8dfb7f`, baseline `v2.5.0`). Runs: `audit --execute` on baseline and candidate (both ENGINE_EXECUTED, unittest, PASS: 824 and 891 invocations), two `--mutate` attempts, one assessment with five external receipts.
- **Authority:** the same agent built the FTD release, ran Assertiva, wrote the assessment and this intake. Self-review plus tool evidence, not an independent qualification. Every engine behaviour below was re-run on a synthetic project with the published 1.1.0; nothing here needs the FTD source.

## The eight feedback entries, consolidated

The run's `audit.dogfood.json` (AGENT_LED) holds eight entries: three written by the agent (1–3), one added later by the agent (4) and four derived by the engine from the assessment (5–8).

| # | Entry (as written) | Consolidated | Classification |
| --- | --- | --- | --- |
| 1 | TEST_CLASS_COLLECTION_UNKNOWN on a transport fake with a `test_*` method | AXF-FTD-03 | precision gap (false positive at info level), REPRODUCED |
| 2 | Mutation budget blocks medium targets; no per-function filter | AXF-FTD-02 | capability gap; recurrence of DG-0101-12 / IDEA-02, REPRODUCED |
| 3 | Local Skill copy differs from the installed engine | AXF-FTD-06 | **withdrawn**: agent observation error (line endings); residual improvement opportunity |
| 4 | Mutation pre-run imports a module the project only runs through discovery | AXF-FTD-01 | **defect**, REPRODUCED; residual of AXF-VN-01 |
| 5 | TEST_CLASS_COLLECTION_UNKNOWN disposed as a false positive | duplicate of 1 → AXF-FTD-03; dedup gap AXF-FTD-04 | duplicate |
| 6 | Agent used pytest 9.2.0 for python tests outside the engine | AXF-FTD-05; dedup gap AXF-FTD-04 | misattribution |
| 7 | (same as 6, same signature) | duplicate of 6 → AXF-FTD-04 | duplicate |
| 8 | Agent used Cosmic Ray for python mutation outside the engine | AXF-FTD-05 (consequence of AXF-FTD-01/02) | misattribution |

Plus AXF-FTD-07, an evidence-import lesson from the same run (agent error on the evidence side, with a small improvement opportunity), not one of the eight entries.

## Findings

### AXF-FTD-01 (P1, defect, REPRODUCED) — unittest file selection for mutation loses the discovery path

- **Expected:** `--mutate-tests tests/test_x.py` runs that file the way the audit's own execution ran it (`unittest discover -s tests`), so the baseline passes when the suite passes.
- **Observed:** `test_command_for` turns the file into `python -m unittest --failfast tests.test_x`. Discovery puts the start directory `tests/` on `sys.path`; the dotted invocation does not, so a test module that imports a sibling helper (`from helper import …`) fails to import. The pre-run reports `the selected tests do not pass on this state before mutation (… FAILED (errors=1)); no mutant was run`, finding `MUTATION_RUN_NOT_COMPLETED`, stage `selection`/`baseline`.
- **Reproducer:** [reproducers/sibling-helper](reproducers/sibling-helper/). `python -m unittest discover -s tests` passes; `python -m unittest tests.test_calc` fails. `assertiva audit . --execute --mutate calc.py --mutate-tests tests/test_calc.py` → 0 mutants (run `f5865120f1e5447b`). **Control:** `--mutate-tests tests` → `discover --failfast -s tests`, 42 mutants, 36 killed, 6 survived (run `fe4e2f4ca27948da`).
- **History:** AXF-VN-01 (`discover -s FILE`) was fixed in 1.0 by dotted module names (`485df1d`); its tests cover package layouts. This is the remaining case: a plain (non-package) test directory whose modules rely on discovery's `sys.path` entry. FTD's suite has this layout; the agent fell back to running Cosmic Ray itself.
- **Suggested fix:** when the selected files sit in a non-package directory that the execution run used as discovery start, keep discovery semantics: `python -m unittest discover -s DIR -p FILENAME` per selected file (refusing a pattern that matches more than the named file, as today's ambiguity rules do), or run the dotted names with `DIR` prepended to the subprocess `PYTHONPATH`. Package layouts keep today's command.
- **Acceptance:** the reproducer's file selection runs exactly its 2 tests in the baseline and evaluates mutants; the AXF-VN-01 layouts in `tests/test_cosmic_ray.py` keep their commands; an ambiguous file name is still refused; a regression test fails on 1.1.0.

### AXF-FTD-02 (P2, capability gap, REPRODUCED; recurrence of DG-0101-12 / IDEA-02) — no way to narrow a target under the mutation budget

- **Observed:** `MAX_MUTANTS = 300` applies to the whole planned population of each `--mutate FILE`. FTD's `scripts/reading.py` (880 lines, the module changed most by the release) planned 2058 mutants and was refused (`stage: budget`); there is no flag to restrict mutation to the changed functions, lines or a risk-ranked subset. Synthetic: `reproducers/helper-fakes/make_big.py` writes a 120-line function; 7082 planned, refused (run `acb8e7a2f3de41e9`).
- **Prior art:** DG-0101-12 (self-mutation of `ci.py` refused, 371 > 300) and IDEA-02 (shards that keep the full denominator; RESEARCH). Derivanta M2 hit it with 594.
- **Different from IDEA-02:** sharding still measures the whole module. A *scoped* run measures a declared region and says so, like `--mutate-tests` already limits the tests.
- **Proof of concept (no Assertiva change):** Cosmic Ray ships `cr-filter-lines`. Between `init` and the budget check, `[cosmic-ray.filters.line-filter] lines = {"big.py" = ["3-6"]}` left **236 of 7082** mutants to run. `cr-filter-git` (changed lines against a branch) exists in the same distribution.
- **Suggested design:** `--mutate FILE::QUALNAME` (function or method, resolved with `ast` to its line span), `--mutate FILE:A-B`, and `--mutate-changed-since REV` (git hunks of FILE). The engine writes the line-filter section, counts only the mutants left to run against the budget, and reports `planned_total`, `selected`, `evaluated` and the scope (`function`, `lines`, `changed_since`) beside the counts; the score is labelled targeted and never presented as the module's. Ordering by risk (recently changed, low coverage, safety-critical names given by the auditor) only chooses what to select; it never drops mutants from a declared scope.
- **Acceptance:** a region selection on the synthetic module runs under the budget and reports both populations; survivors carry their line; whole-module behaviour is unchanged; IDEA-02's "full denominator" rule still holds for any whole-module claim.

### AXF-FTD-03 (P3, precision gap at info level, REPRODUCED) — a helper double reported as a possibly uncollected test class

- **Observed:** `TEST_CLASS_COLLECTION_UNKNOWN` lists `tests/test_history.py::HistoryTransport`, a transport double with an API method named `test_case_history`, whose base `FakeTransport` is a plain class imported from another test module of the same project. The same audit's native unittest run collected 2 tests and not that class (run `acb8e7a2f3de41e9`). In FTD the same shape (`HistoryAzure(TaggedAzure(FakeAzure))`) produced the same finding; the agent disposed it FALSE_POSITIVE.
- **By design:** CHANGELOG (1.0) introduced the finding for bases the static inventory cannot resolve, including bases imported from another module. The gap is precision, not a broken rule: the import resolves to a project file whose chain contains no `TestCase`, and the executed collection already answers the question the finding says is UNKNOWN.
- **Suggested fix:** follow imports that resolve to project files when reading bases (bounded depth), and, when a native run of the same audit exists, reconcile: a class absent from the executed test ids is reported as `NOT_COLLECTED` (fact) instead of UNKNOWN, kept only when it has a `TestCase` ancestor.
- **Acceptance:** the reproducer yields no UNKNOWN entry for `HistoryTransport` after `--execute`; a class whose imported base *is* a `TestCase` subclass and is skipped by the runner is still reported.

### AXF-FTD-04 (P2, feedback pipeline) — duplicates written, linked and planned inconsistently

- **Observed:** in one AGENT_LED file, entries 6 and 7 carry the **same signature** and are both written; entry 5 (derived from a FALSE_POSITIVE disposition) and entry 1 (the agent's own entry for the same finding code) have different signatures and no link. `portfolio import-feedback --dry-run` plans `CREATE AFB-6499b06a8b` **twice**; the real import creates once and reports `SKIP_ALREADY_IMPORTED` for the second (correct), and a re-import skips all eight (correct). Reproduced in a disposable `ASSERTIVA_HOME`.
- **Suggested fix:** dedup derived entries by signature when the file is written; give a derived entry a `relates_to` (finding code or agent signature) so an agent entry and the derived one about the same finding are one issue with two sources; make the dry run apply the same idempotence as the import.
- **Acceptance:** the run's file has seven entries or fewer with explicit links; the dry run and the import print the same plan; Portfolio sightings unchanged for a true second report.

### AXF-FTD-05 (P3, derivation misattribution) — external runs recorded as "unsupported stack"

- **Observed:** entries 6–8 are `UNSUPPORTED / tooling_discovery / capability_gap` "Agent used pytest … outside the engine". The engine supports and ran this stack in the same audit; the agent's external runs covered other profiles (an optional dependency absent, Linux in a container) and a mutation the engine could not complete (AXF-FTD-01/02). The receipts' `notes` said so.
- **Suggested fix:** derive "unsupported" only when the audit recognized no adapter for that purpose; otherwise record an external *complement* (profile, platform, or a link to the engine failure that caused it), not a capability gap.
- **Acceptance:** the same assessment produces no UNSUPPORTED entry for a stack the engine executed; an external mutation run after `MUTATION_RUN_NOT_COMPLETED` links to that finding.

### AXF-FTD-06 (withdrawn; residual P3 opportunity) — Skill/runtime version check

- **What happened:** the agent compared the loaded Skill files with `git show v1.1.0:<file>` byte for byte, saw differences and reported a version drift. The Skill was a link to a checkout at `v1.1.0` with `core.autocrlf=true`; ignoring CR, every compared file is identical. **The entry is an agent error and is withdrawn.**
- **Residual opportunity:** neither `SKILL.md` frontmatter nor the CLI states which Skill version is loaded, so a check has to diff bytes and can fail exactly this way. A `version` field in the frontmatter (or `metadata.version`), and an offline `assertiva --version` line that also reports the version of the Skill directory it was given, would make the check exact.
- **Portfolio gap exposed:** there is no state to withdraw an entry the reporter later disproves (only `NOT_SUPPORTED`, `BLOCKED`); see the routing proposal (`WITHDRAWN`, `DUPLICATE_OF`).
- **Acceptance:** a Skill/engine mismatch is reported from declared versions; line endings cannot produce one; an imported entry can be withdrawn with evidence and stops counting as open.

### AXF-FTD-07 (P3, evidence import) — what made external receipts UNVERIFIED

- **Observed:** four of five receipts are `link: UNVERIFIED`. Correct per contract: two test receipts cited plain text logs (no JUnit/CTRF/Allure, so `results_consistency: NO_STRUCTURED_RESULTS`), two fault-injection receipts were run on another revision. The mutation receipt (same revision, verified artifact) is `VERIFIED`. The agent learned this only by reading `audit.json`: the attach command printed counts, not each receipt's link and the reason.
- **Suggested fix:** the attach summary lists each receipt with `link` and its blocking reason ("no structured results", "different revision"); `references/ADAPTIVE_TOOLS.md` tells the agent to write `--junitxml`/CTRF when it runs tests outside the engine and to import Cosmic Ray results with `--mutation-report` when the engine could not run them.
- **Acceptance:** attaching the same assessment shows the four reasons without opening the JSON.

## Incidental observation (not analyzed)

The synthetic stdlib-unittest reproducers without CI also got `CI_PYTEST_NOT_OBSERVED`. It may relate to AXF-VN-05; not investigated in this intake.

## What the instrument did well (observed)

Engine-executed full runs on a read-only verified copy with revision identity; branch coverage split between product and tests; credential-like environment variables withheld; the assessment validator refused three malformed submissions with exact reasons (`cause_proven` without `cause_hypothesis`, an empty `rule`) instead of accepting them; Portfolio import was idempotent.

## Privacy review

The included `evidence/audit.dogfood.json` is the engine's sanitized file, reviewed by the agent before inclusion: no absolute paths, user names, e-mail addresses, hosts or credentials; the only project reference is the public FTD repository. Receipt artifact paths, interpreter paths and local run directories are summarized in [evidence/runs.json](evidence/runs.json) without paths.
