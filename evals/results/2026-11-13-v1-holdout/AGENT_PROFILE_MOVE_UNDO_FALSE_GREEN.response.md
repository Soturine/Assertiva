# Assurance assessment: file-moving CLI test (move, fault, new turn, undo)

## Answer

The green test proves very little about the move. As described, it shows that the destination git folder exists and that one Claude CLI session resumes. It does not show that the agent state is intact: the two Codex SQLite state stores, the rollout byte offsets, the Antigravity URIs, the trusted folders and the git worktree are not part of the claim. Nothing in the description shows that recovery from the mid-move fault is checked, or that the new chat turn created after the move survives undo. The suite therefore has a high risk of false green for the outcome that matters: no agent state or new work is lost.

This rests only on the scenario text. I did not read the test code, did not run the engine and did not run any command, so every statement about the suite is a description, not an observation.

## What green proves and does not

| Claim | How you know | Status |
| --- | --- | --- |
| Destination git folder exists after the move | DECLARED (scenario) | Protected, but weakly: an existence check is also true after a partial move |
| One Claude CLI session resumes at the destination | DECLARED (scenario) | Protected for one agent and one session only |
| Two Codex SQLite state stores are moved and readable | not described | UNKNOWN |
| Rollout byte offsets still resume at the same position | not described | UNKNOWN |
| Antigravity URIs resolve to the moved paths | not described | UNKNOWN |
| Trusted folders are carried over | not described | UNKNOWN |
| Git worktree is still linked and usable | not described | UNKNOWN |
| Mid-move fault leaves no mixed state | not described | UNKNOWN |
| Undo restores the pre-move state without dropping the post-move turn | not described | UNKNOWN; this is the highest-risk gap |

Count unit: one test, one synthetic profile, one injected fault, one new turn, one undo. The scenario describes no repeated invocations.

## Findings, ranked by consequence

1. **Undo can silently erase new work (highest risk, INFERRED).** The new turn is created after the move and before the undo. If undo restores a snapshot taken before the turn, the turn is lost in the Codex stores, the rollout files and the Claude session, and the test stays green as long as the folder exists and one session resumes. The scenario's own ordering makes this the case the suite most needs to check, and nothing described checks it.

2. **The existence oracle is a false green (INFERRED).** A folder that exists after a partial move, or after a half-undone move, passes the same check. The assertion is true for a wrong state, so it cannot detect the fault the scenario injects.

3. **One resumed session does not cover the agent state (INFERRED).** The profile holds two separate Codex SQLite stores, rollout offsets, URIs, trusted folders and a worktree. A resume that succeeds for the Claude session says nothing about any of them. A single-store check would also miss a loss in the second store.

4. **Fault injection without a stated recovery contract (INFERRED).** The scenario injects a fault mid-move but describes no assertion on what happens after it. The suite may pass because the fault was absorbed, or because the test never checks the state after recovery. Either way the result is unknown from the description.

5. **Byte offsets are a silent failure mode (INFERRED).** A rollout file that is copied with different line endings, or re-encoded, keeps its content but moves its offsets. Resume would then start in the wrong place without an error. A test that only reads the session name would not see it.

## Minimal high-signal evidence

Use one synthetic profile, generic names only, and capture a digest of each state category before the move. After move, injected fault, recovery, one new turn and undo, assert each of these. Each line is a separate check, so a failure names the lost piece.

1. **Codex stores, both of them:** each store's row keys and content digest equal the pre-move values, `PRAGMA integrity_check` returns `ok`, and the row written by the new turn is present after undo.
2. **Rollout files:** each file's size and content digest match the pre-move values, the byte offset recorded before the move resumes at the same position, and the bytes appended by the new turn are still present after undo.
3. **Antigravity URIs:** every URI in the profile resolves to an existing path after undo, and none points at the pre-move location.
4. **Trusted folders:** the set of trusted entries after undo equals the set before the move.
5. **Git worktree:** `git worktree list` before and after names the same worktree, its `.git` link resolves, and the uncommitted or new change made by the new turn is still present.
6. **Claude CLI session:** the session resumes after undo, and the transcript contains the new turn.
7. **Fault recovery:** after the injected fault and recovery, the state is either the pre-move state or the completed move, never a mix. Check it with the same digests as items 1 to 5, not with the folder check.

The first assertion to add is item 1's presence check for the new turn, because it is the one that catches the highest-risk loss.

## Negative controls

Settle the false-green question with deliberate breaks in a disposable copy, not in the project:

- Make undo restore a snapshot taken before the new turn. The new-turn checks in items 1, 2, 5 and 6 must fail. If they stay green, the suite cannot see lost work.
- Drop one row from the second Codex store during the move. Item 1 must fail for that store, which proves the check covers both stores.
- Shift one rollout file's bytes by a line ending. Item 2 must fail.
- Remove one trusted folder entry. Item 4 must fail.

These are hand-made breaks I would run myself. They are observed evidence, not engine-executed mutation results, and their commands and outputs must be kept so they can be rerun.

## What stays unknown and what would settle it

- Whether the existing test asserts any of items 1 to 7. Reading the test file and its fixtures would settle it. The engine's `assertiva audit --execute` on a disposable copy would show what runs and what passes, but the scenario does not give me access to either.
- Whether the new turn is actually written before undo in the real flow. Only a run of the flow with the new-turn check would show this.
- Whether recovery after the injected fault is part of the real move code. The description does not say.

## Recommendation

Do not treat the current green as evidence that agent state or new work survives the move. Add the seven checks above to a synthetic-profile test, keep the folder and session checks as a smoke layer only, and run the negative controls before trusting the result. Describe the claim as "the destination folder exists and one Claude CLI session resumes" until the other checks pass.
