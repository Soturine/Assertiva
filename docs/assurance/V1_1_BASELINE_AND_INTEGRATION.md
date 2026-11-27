# v1.1 baseline, integration of #11/#12, and architecture decisions

Recorded 2026-11-27 on branch `integration/v1.1-foundation`. Machine: Windows 11, CPython 3.12.10, Docker 29.8.2 (Linux engine). No paths or private projects are named.

## Starting state (verified, not assumed)

| Item | Observed |
| --- | --- |
| Latest release | `v1.0.1` (2026-11-16) |
| `main` | `b615b13d637d57b50d9acf14433ac4cd2ad6e66e` (merge of #10) |
| PR #11 | OPEN, head `4325936560bdf5254a95bbb1b5f88628ef41e415`, base `b615b13` |
| PR #12 | OPEN, head `8a0a7e1fb07abebb92a2e21a5c6ea50faff2003e`, base `b615b13` |
| Branches / tags | 30 refs listed; none deleted or moved |

## Baseline suite

| Revision | Command | Result |
| --- | --- | --- |
| `b615b13` (main) | `pytest -q -n auto -m "not browser and not jvm"` | **1349 passed, 19 skipped, 0 failed** (625 s) |

PR #11 reported 1341 passed / 34 skipped / 5 failed on its author's machine, with the same five failing on main there. They do not reproduce here; they were environment-dependent on that machine, not product failures of `main`. The numbers are not comparable across machines without the same selection and environment. The browser and JVM suites are not part of this local selection (they run in their own CI jobs).

## Integration matrix

| Origin | Decision | Commit on the branch | Verification | Status |
| --- | --- | --- | --- | --- |
| #11 `7ad77e3`, `5f18982`, `4325936` — missing build backend attributed to the environment | merged as is (merge commit keeps the SHAs) | `cc7d3e4` | its tests fail on main (collection error: `environment_build_cause` missing) and pass after: 10 passed; reproduced on `b615b13` in a separate worktree | IMPLEMENTED_AND_VERIFIED |
| #11 follow-up — `PIP_NO_BUILD_ISOLATION` semantics | refined: pip turns the value into `build_isolation` itself (`0`/`false` disable it, `1`/`true` keep it), checked with pip 25.0.1 by parsing the variable through pip's own option parser; the override and its limitation now fire only for a value pip reads as disabling | `a0036b0` | new test; 11 passed | IMPLEMENTED_AND_VERIFIED |
| #12 `8a0a7e1` — oracle and evidence review from QE lessons (`SKILL.md`, `docs/EVIDENCE_CONTRACT.md`) | merged as is; its qualification candidates (stale source, inaccessible diagram, fabricated PASS, partial reading, legitimate characterization) are implemented as engine checks and tests in 1.1 (`tests/test_context_traceability.py`), not by documentation alone | `56d24ca` | engine tests for those cases pass; agent evaluations of the guidance: NOT_RUN (needs an eval budget) | IMPLEMENTED_NOT_FULLY_QUALIFIED |
| Branches DrawLab/TCC and historical branches | not touched; nothing reintroduced | — | — | preserved |

Both PRs are ancestors of the integration branch: merging it marks them merged on GitHub. They were not closed or merged separately.

## Architecture map: who does what

| Responsibility | Owner | Why |
| --- | --- | --- |
| Choosing, reading and interpreting sources; visual reading | AGENT_PRIMARY | hosts read PDFs, images and tables natively; an extractor loses figures |
| Source path containment, digest, PDF page count, citation inside reviewed range | DETERMINISTIC_REQUIRED | mechanical, cheap, independent of the agent |
| Behavior slices, oracle judgement, relation of a test to a behavior | AGENT_PRIMARY | semantic; no keyword classifier |
| Status strength vs evidence (executed, outcome, protection) | DETERMINISTIC_REQUIRED | prevents "mapped = proven" |
| Running a stack without an adapter | AGENT_PRIMARY with OPTIONAL_EXTERNAL_TOOL | the agent runs it under consent and confinement |
| Receipt ingestion: digests, counts, revision link | DETERMINISTIC_REQUIRED | the engine never runs the receipt's command |
| Second opinions from another model | OPTIONAL_PROVIDER (recorded only) | no SDK in the engine; host-only is the supported path |
| Dogfood mechanical observations | DETERMINISTIC_REQUIRED | from the run itself |
| Dogfood semantic review | AGENT_PRIMARY | the agent's closing review |
| Portfolio import, dedup, lifecycle | DETERMINISTIC_REQUIRED | idempotent, append-only |

No engine module was replaced by an LLM call. `test_facts.py`, `effectiveness.py`, `impact.py` and `selection.py` are unchanged in 1.1: the agent's semantic work enters through the assessment, never through narrowing a proven selection.

## Decisions

| Item | Decision | Basis |
| --- | --- | --- |
| Source inventory and review, behavior traceability, status strength | ADOPT (engine contract `assertiva-context/1`, attached through the existing assessment) | reuses the run/attach validation; no new command |
| External execution receipts | ADOPT (record only) | gives non-native stacks provenance without an executor |
| Independent reviews | ADOPT (record only) | provider-neutral; no calls |
| Portable dogfood beside every report | ADOPT | works without Portfolio, network or account |
| Portfolio `import-feedback`, version-aware regressions, resolved commits | ADOPT | fixes "SHA-like text = verified" and old reports reopening fixes |
| PDF/OCR/layout libraries (pypdf, PyMuPDF, Docling, Tesseract) as dependencies | REJECT for the core; tools stay optional on the host | host-native visual reading answered the demo; PyMuPDF is AGPL; the engine counts pages without a library |
| Direct provider SDK integration (Claude, OpenAI, Gemini, local models) | DEFER | no case in this round where a second model changed an outcome; contract and consent rules exist for when one does |
| Native .NET / Go / Ruby adapters | DEFER | the external path worked for .NET and Ruby; frequency across audits (Portfolio overview) should decide |
| MCP server, RAG, vector index, graph database | REJECT for 1.1 | not needed for the vertical slice |
| Blind multimodal agent evaluation | RESEARCH, NOT_RUN | needs an approved eval budget |
