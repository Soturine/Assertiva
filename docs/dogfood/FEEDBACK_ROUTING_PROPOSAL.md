# Proposal: routing dogfood feedback to Assertiva as reviewed pull requests

Status: **proposal, not implemented.** Written from the FTD v2.6.0 intake ([ftd-v2.6.0/](ftd-v2.6.0/README.md)), where turning one run's `audit.dogfood.json` into this repository's intake took manual work that every project repeats: reading eight entries, finding duplicates, checking which issues were already fixed, writing reproducers, sanitizing, and opening a docs-only pull request without touching code.

## Goals and non-goals

- Make that path reusable for any project that runs Assertiva, from the files Assertiva already writes.
- Keep it **local-first and agent-first**: the engine never contacts a network service, never holds a token and never decides what an issue means. The host agent (or a person) does the semantic work; the engine validates, deduplicates, sanitizes and produces a deterministic plan.
- A pull request is created or updated **only under a prior, scoped authorization**, never merged, never touches code, never publishes a release.
- No new runtime dependency; no integration the user did not ask for.

## What already exists and is reused

| Existing contract | Role in the flow |
| --- | --- |
| `audit.dogfood.json` (`assertiva-dogfood/1`), one per run, sanitized, `LOCAL_ONLY`, `reviewed_for_export: false` | capture |
| `portfolio import-feedback` with signatures, `AFB-…` ids, sightings, `reported_status`, idempotent re-import | consolidation and deduplication across runs and machines |
| `portfolio move` states with proof (`CLAIMED`, `COMMIT_IDENTITY_ONLY`, `RETEST_RESULTS_RECORDED`, `VERIFIED_AT_SHA`) | lifecycle after a fix |
| `<ASSERTIVA_HOME>/consent.toml` (user's, never the project's) | authorization |
| `--ci-run FILE` pattern: the engine reads a provider export the agent fetched, it never calls the provider | knowing which intake PRs and branches already exist |
| intake convention: `docs/dogfood/<project>/` or `docs/assurance/*_INTAKE.md` + `*_FEEDBACK.json`, ROADMAP line "documented, not implemented" | target layout |

## Proposed flow

```text
audit/improve ──> audit.dogfood.json (per run)            [exists]
        │
        ▼
portfolio import-feedback ──> AFB-… entries + sightings     [exists; + DUPLICATE_OF / WITHDRAWN / relates_to]
        │
        ▼
portfolio intake build --ids … | --since …                  [new, offline]
        │   bundle: README.md, FEEDBACK.json (assertiva-intake/1), evidence/, reproducers/
        │   privacy scan + human review flag
        ▼
portfolio intake plan --target-index FILE                    [new, offline]
        │   FILE = the agent's export of the target repo's open PRs, branches and existing intake ids
        │   plan: CREATE | UPDATE <branch> | SKIP (already reported / fixed) per AFB id
        ▼
host agent executes the plan with its own tools (git, gh)    [agent; only with consent]
```

### 1. Consolidation (Portfolio additions)

- `DUPLICATE_OF <AFB>` and `WITHDRAWN` states, each with evidence, so a reporter can withdraw an entry it later disproves (AXF-FTD-06) and two entries about one issue become one (AXF-FTD-04) without deleting history.
- Derived entries carry `relates_to` (finding code or agent signature); import links them to the agent's entry instead of creating a second issue.
- `--dry-run` uses the same idempotence as the import (one plan line per id).

### 2. Intake bundle (`portfolio intake build`, offline)

- Input: selected `AFB-…` entries (open, not `WITHDRAWN`, not `DUPLICATE_OF`). Output: a directory under `ASSERTIVA_HOME/intakes/<digest>/` with the target layout, a `FEEDBACK.json` (`assertiva-intake/1`: id, priority, kind, status, related ids, reproducer reference, suggested fix, acceptance, sightings, versions), and the original dogfood files.
- **Privacy:** the existing sanitizer plus a stricter export check (absolute paths, home and user names, hosts, e-mail, token shapes, project-name list from the Portfolio registry). Any hit blocks the bundle. Reproducers are never copied from the project: the bundle references an agent-written synthetic reproducer directory, and refuses one that contains files whose digest matches a file of a registered project.
- `reviewed_for_export` stays false until `portfolio intake review <digest> --reviewed` records who reviewed and when; an unreviewed bundle cannot be planned.

### 3. Plan (`portfolio intake plan`, offline, deterministic)

- Input: the reviewed bundle and a target index the agent exported (`gh pr list --json …`, `gh api …/branches`, and the ids already present in `docs/**/FEEDBACK.json` of the target's default branch). The engine reads files; it never calls GitHub.
- For each entry: `SKIP_ALREADY_REPORTED` (id or signature present in an existing intake), `SKIP_FIXED` (Portfolio state FIXED_* with proof, or the target's remediation records it), `UPDATE` (an open intake PR for the same source project exists), else `CREATE`.
- Branch name derived from the bundle digest (`docs/<project>-dogfood-intake-<date>-<short digest>`), so re-running the plan never opens a second PR for the same content.
- The plan lists the exact files and the path allowlist (`docs/dogfood/**`, `docs/assurance/**`, one `ROADMAP.md` line), the PR title and body, and the statement "no code, no merge, no release".

### 4. Execution (host agent, authorized)

- `consent.toml` gains a section such as:

  ```toml
  [feedback_routing]
  repositories = ["Soturine/Assertiva"]
  allowed_paths = ["docs/dogfood/**", "docs/assurance/**", "ROADMAP.md"]
  actions = ["create_branch", "push_branch", "open_pr", "update_pr"]   # never merge, release or delete
  require_reviewed_bundle = true
  ```

- The Skill tells the agent to execute a plan only when the consent covers the repository, every path and every action, to stop and ask otherwise, and to verify after pushing that the PR diff touches only planned files. The engine can check that last step from an exported `gh pr view --json files` (`portfolio intake verify`).
- After merge by a maintainer, `portfolio move` records the intake reference; fixes later move entries to FIXED_* with proof as today.

## Safety properties

| Risk | Control |
| --- | --- |
| duplicate PRs or entries | signature + `AFB` dedup, `relates_to`, digest-named branches, target index check |
| private data leaving the machine | sanitizer + export scan blocking on hit, no project files in bundles, explicit human review flag |
| unauthorized changes | consent scoped to repository, paths and actions; path allowlist in the plan; post-push verification of the PR diff |
| code changes or releases | not in the action vocabulary; plans never contain code paths |
| hidden network access | engine reads exports only; every network action is the agent's, visible to the user |
| a wrong report travelling far | `WITHDRAWN` with evidence; intake status "documented, not implemented" until a maintainer acts |

## Incremental delivery

1. Portfolio states `DUPLICATE_OF` / `WITHDRAWN`, derived-entry `relates_to`, dry-run idempotence (fixes AXF-FTD-04/06 on the way).
2. `intake build` + export privacy scan + review flag (useful alone: produces the directory a person commits by hand).
3. `intake plan` from a target index file.
4. Consent section and Skill instructions for authorized execution; `intake verify`.

Each step is testable offline with fixtures (a fake target index, synthetic dogfood files), in the same style as `portfolio import-feedback`'s tests.
