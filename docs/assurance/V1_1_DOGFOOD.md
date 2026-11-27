# v1.1 dogfood: real runs, results and feedback about Assertiva

Recorded 2026-11-27. Every project below is a synthetic fixture of this repository (`examples/`); runs used disposable copies outside the repository. Absolute paths are omitted. "Agent" is the coding agent that developed 1.1; its own reading and runs are labeled as such and are not independent evidence.

## 1. Document assurance: a rule only in a figure (`examples/document-assurance`)

| Step | Evidence |
| --- | --- |
| Text layer of `requirements.pdf` (pypdf 6.18.1) | page 1: RF-01 text; page 2: empty string. The approval threshold is not in any text layer or metadata |
| Host-native read (agent's PDF reader, text and page images) | page 2 read from the image: `qty > 100 ?` → `supervisor approval present ?` → `Reject 409 APPROVAL_REQUIRED, no stock moved, no event`; "a quantity of exactly 100 needs no approval". **Not blind**: the agent generated the fixture |
| Engine audit of the original (`--execute`) | 2 passed; findings `CI_PYTEST_NOT_OBSERVED`, `NO_DELIVERY_PIPELINE_OBSERVED`: no signal about the rule (by design: the engine does not read documents) |
| `improve` with a candidate test and two negative controls | `protection.gained`: `drop-approval`, `off-by-one-threshold` (baseline missed both, candidate detected both); `lost`: none; stability PASS (3 executions) |
| Audit of an "after" copy with the candidate test + attached assessment | source labels `READ_NATIVE`, `READ_VISUAL`, coverage 2/2 pages (`ENGINE_COUNTED`), digest MATCH; `BHV-approval` PROVEN_IN_SCOPE (two STRONG validating tests, both breaks detected), `BHV-transfer` PARTIAL (atomic rollback not exercised) |

The candidate was not approved by the agent: the "after" copy is a separate disposable copy with the candidate test added, so no `--approve` was ever passed.

**v1.0.1 versus 1.1 on the same copy and assessment** (v1.0.1 installed from the tag in its own virtual environment; import origin checked from outside the checkout): v1.0.1 accepts the assessment and drops `sources`, `behaviors` and `dogfood` without a word — including a PROVEN claim it never checks — and writes only `audit.html`/`audit.json`. 1.1 validates and renders them, refuses a citation outside what was read and a status stronger than its evidence, and writes the dogfood files.

## 2. Adaptive tool discovery on two stacks without an adapter (`examples/adaptive-tools`)

Both: download stage with network into an isolated volume; execution stage with `--network none`, project mounted read-only, non-root user, CPU/memory/pid limits; outputs to a directory outside the project; the project copy's `git status` stayed clean.

### Ruby (minitest)

| Item | Value |
| --- | --- |
| Image | `ruby@sha256:97fde153c07a5106a684cedebb49732fc14872c6b15c56d7c97752ee0a07e2b3` (ruby 3.3.14), user 1000, read-only root |
| Results tool | minitest-junit 2.1.0 (MIT). Its RubyGems page does not document the flags; `--junit` and `--junit-filename` were read from the installed gem's `junit_plugin.rb` |
| Setup friction | its dependency `ox` is a native extension: `gem install` failed in the slim image; built in a throwaway container with `build-essential`, then the run used the slim image |
| Run | `ruby -Ilib -Itest test/price_test.rb --junit --junit-filename=/out/minitest.xml` → exit 0, 3 runs, 3 passed; JUnit sha256 `eaa6f689…f7877` |
| Manual negative control (not a mutation tool) | `>=` → `>` on the bulk threshold, in the container's copy only → exit 0, 3 passed: the boundary break is **not detected** |
| Engine | `NO_EXECUTABLE_TEST_ADAPTER_RECOGNIZED`; JUnit imported (`EXTERNAL_UNVERIFIED`); both runs recorded as receipts with link VERIFIED (same revision, digests and counts agree) |

### .NET 10 (xUnit 2.9.3, Stryker.NET 5.1.0)

| Item | Value |
| --- | --- |
| Research | Stryker.NET docs (read 2026-11-27): requires the .NET 10 runtime — the SDK 8 image planned from memory would not run it; `--reporter json`, `--output`, `--skip-version-check`. Package versions from `dotnet package search` (exact match): xunit 2.9.3, xunit.runner.visualstudio 3.1.5, Microsoft.NET.Test.Sdk 18.12.0, JunitXml.TestLogger 8.1.0, dotnet-stryker 5.1.0 |
| Image | `mcr.microsoft.com/dotnet/sdk@sha256:8c6edfb26c85153f236d26efebd9ad349aec403583f343f201ee67838b23658d` (SDK 10.0.404), user 1654 |
| Fixture fixes found by running | an XML comment containing `--` broke the csproj; the library missed `using System;` — both fixture errors, fixed before the runs below |
| Tests | `dotnet test --logger "junit;LogFilePath=/out/xunit.xml"` → exit 0, 3 passed; JUnit sha256 `48344607…b33ba`. NuGet's vulnerability lookup failed offline (NU1900): confirms the run had no network |
| Mutation | `dotnet tool run dotnet-stryker --skip-version-check --reporter json --reporter cleartext` → exit 0, 36 s; JSON: 8 Killed, 3 Survived, 1 Ignored (score 72.73 % = 8/11). The console table says 4 survived (it counts the ignored mutant); the JSON was used. Survivors: `quantity > BulkThreshold` (the boundary), `gross / 0.05m`, an empty exception message (equivalent for behavior) |
| Engine | `--mutation-report` read the counts correctly; tied to the state after the 1.1 fix (see feedback 1); `MUTATION_SURVIVORS` raised; receipts VERIFIED |

## 3. Colleague test: two installations, no registration

- Wheel `assertiva-1.1.0rc1-py3-none-any.whl` (sha256 `60f6a98b…64e3b`), sdist (`ec3f48d1…0c`), built from `git -c core.autocrlf=false archive` of the candidate.
- "Colleague": a new virtual environment with only the wheel, run with `python -I -m assertiva.cli` from outside the checkout (imports resolved to the installed package), its own `ASSERTIVA_HOME`, no Portfolio, no provider credentials; audited its own copy of the Ruby fixture → `audit.dogfood.json` (`ENGINE_ONLY`, `semantic_review: NOT_RUN`, one entry "No executable test adapter for Ruby"); the project name and folder appear 0 times in the file.
- "Maintainer": another `ASSERTIVA_HOME`. `import-feedback --dry-run` wrote nothing (the home did not exist afterwards); the import created one entry; a second import was `SKIP_ALREADY_IMPORTED`. Importing the three agent-led files of sections 1–2 as well: 10 entries, 11 sightings, 4 imports, 0 projects registered; the Ruby gap is one entry seen from 2 origins.
- Both installations ran on the same machine and were operated by the same agent: this demonstrates portability, not independent adoption. No external developer evaluated 1.1.

## 4. Self-audit

Static audit of the candidate tree (`git archive` copy) with the candidate engine: 3 findings (`STATE_AFTER_REJECTION_NOT_EVIDENCED`, `TEST_SMELL_SIGNALS`, `UNCLASSIFIED_VERIFICATION`), dogfood `ENGINE_ONLY` with no entries. Runtime self-qualification is the full suite (V1_1_RELEASE_READINESS.md).

## Feedback about Assertiva from this round

| # | Kind / component | Observation | Status | Decision |
| --- | --- | --- | --- | --- |
| 1 | FALSE_POSITIVE / engine | A mutation report written in a container root (`/tmp/work/...`) was called `MUTATION_REPORT_SOURCE_MISMATCH` for the very revision audited | REPRODUCED; fixed (`8bb6338`): re-rooted by trailing path, identical content still decides; `tests/test_mutation_report_reroot.py` fails on `b615b13`, passes after; control (other content) stays a mismatch | fixed in 1.1 |
| 2 | FALSE_NEGATIVE / engine | `improve` said the candidate adds no negative-path test while it asserts a 409 rejection with unchanged state and no event | OBSERVED | backlog: negative-path detection keys on raised errors, not rejection responses |
| 3 | MISSING_ANALYSIS / document_assurance | The engine cannot know a rule that exists only in a document | OBSERVED, by design | agent-primary; the engine verifies the citation |
| 4 | UNSUPPORTED / adapter | No adapter for Ruby; no adapter for C# | OBSERVED (Ruby from 2 origins) | DEFER native adapters; count across audits |
| 5 | UNSUPPORTED / tooling_discovery | Current Stryker.NET needs the .NET 10 runtime; the plan from memory was wrong | OBSERVED | the protocol's research step caught it; no code change |
| 6 | COST / tooling_discovery | minitest-junit needs a native build | OBSERVED | documented; log-only receipt is the fallback |
| 7 | EVIDENCE_INCONSISTENCY / traceability (found in the agent's own 1.1 code) | A behavior linked to a misnamed external test was accepted as UNKNOWN | fixed (`8bb6338`): refused with the closest names | fixed in 1.1 |
| 8 | external tool | Stryker.NET's console table and its JSON disagree on survivors | OBSERVED | not Assertiva's; the JSON is used |

## Not run

- Blind reading of the PDF by an independent agent, and the agent evaluation cases of PR #12: need an approved eval budget (NOT_RUN).
- C++ (no compiler or CMake on this machine; a container image would work the same way as above): NOT_RUN.
- Office formats (DOCX/PPTX/XLSX), scans with OCR, spreadsheets with formulas: no fixture in this round (NOT_RUN).
- Any provider other than the host: no call was made.
