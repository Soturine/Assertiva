# External dogfood — AIGoat, agentroot, Tandrio and HackerTube (2026-11-03)

**State:** static source-and-publication review; semantic test-audit candidates **NOT_RUN**. Source owners: Framework [PR #11](https://github.com/Soturine/Derivanta/pull/11), Engine [PR #2](https://github.com/Soturine/Derivanta-Engine/pull/2). Baseline Assertiva v0.10.1. No new executable detector/adapter, attack execution, third-party security finding, vulnerability disclosure, or deployment.

## Verified code-level references and false-green patterns

| Source | Code reviewed / evidence | Test-oracle risk | Owner/overlap |
| --- | --- | --- | --- |
| [AIGoat](https://github.com/AISecurityConsortium/AIGoat) @ `bb3cd1b` | `app/agent/broker.py` IntentGate, `app/agent/memory.py`, `app/defense/profiles.py`, `app/labs/effects.py`, shell sandbox, Docker Compose, CI | “Attack blocked” based only on final model text or activated guardrail flag, while tool effect, permission and memory persistence are not checked; intentional L0 vulnerability falsely reported as a product defect | Reuse authorization and effect-oracle cases, add a distinct longitudinal memory/effect case |
| [agentroot](https://github.com/mvoloch/agentroot) @ `765abc8` | `src/agentroot/move.py` with plan/journal/undo, `snapshot.py`, adapters, `tests/test_safety.py`, Windows CI | “Migration pass” checks path exists but not every chat registry, SQLite/WAL consistent snapshot, offset indexes, git worktrees, post-move changes or rollback | Reuse platform matrix and transaction harness; new narrow agent profile test-strength case |
| Tandrio social post | Agent canvas, shared context and multi-provider claims; no source repo or runnable binary verified | UI screenshot is not evidence of concurrent edit safety, no lost changes or agent approval isolation | Defer new rule until a testable fixture exists |
| HackerTube | [author post](https://karpathy.bearblog.dev/hacker-tube/) and social screenshot; no public code artifact inspected | “Built in 2h” or successful site preview doesn't measure source reliability, curation precision, infra costs or security outcomes | Reuse evidence-provenance, final-output-only, and pipeline tests; no duplicate case |

## Calibration proposal

1. **Agent memory/indirect injection:** create synthetic user/ticket, read-only third-party text, note store, task-bound tool authorization, and independent database readback. Positive allowed workflow, negative poisoned memory, cleared memory, replay, unrelated principal, side-effect failure and source-to-memory trace. A safe final answer does not prove no unauthorized call; an intentionally vulnerable educational level is not a reportable product flaw.
2. **Agent profile move:** isolated fake user home with realistic, versioned but synthetic Claude/Codex/Gemini registries and git worktrees. Exercise read-only scan, dry run, partial move, concurrent SQLite changes, fail/undo, stale absolute paths and new post-move work. Assert content/index hashes and no unapproved change to trust or credential scope. A test of *only* folder renaming remains valid for its narrow contract.
3. **Agent collaboration:** use independently verified final repo diff and task result, matched baseline and recorded agent identities; avoid assuming Tandrio's claimed architecture or adopting UI patterns as proof of conflict resolution.
4. **Data-to-product pipeline:** count raw/selected/rejected items, citation lineage and false discovery; data collection, labeling, coding and deployment have separate budgets. No token/cost number from public posts is independently audited.

## Non-overlap and promotion
Existing cases `RBAC_DENIAL_WITHOUT_EFFECT_ORACLE`, `MOCKED_AWAY_INTEGRATION`, `TRANSACTION_HARNESS_MASKS_COMMIT_BEHAVIOR`, `PLATFORM_MATRIX_COLLAPSE`, `HIGH_COVERAGE_WEAK_ORACLE` and `E2E_BLIND_RERUN` remain canonical for general mistakes. Two new narrow cases below require longitudinal memory+effect or multi-registry rollback reasoning. Do not create heuristic detectors on keywords "injection", "agentroot", "migration" or "guardrails". Admit deterministic runtime checks only with a measured failure population, negative controls and platform/version reproductions. All source claims remain bounded; none of the new cases have agent/judge trial results.
