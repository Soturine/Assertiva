# v1.0 branch disposition (report only)

**Inventory date:** 2026-11-13, before PR #9 was merged. This page was written before the merge so that the release
needs no commit after its tag, and the comparison is against `integration/v1.0-foundation` at `ecb1b23`, the content
`main` receives with PR #9. Ancestry was checked with `git merge-base --is-ancestor <branch> <integration>`, and
behind/ahead with `git rev-list --left-right --count`. The divergent branches were compared file by file by blob hash
(`git rev-parse <ref>:<path>`).

**No branch or tag was deleted.** The deletion commands at the end are options for the owner.

| Branch | Tip | Behind / ahead of integration | Ancestor | Category | Note |
|---|---|---|---|---|---|
| `docs/derivanta-m1-dogfood-intake-20261031` | `411606d58fd1` | 53 / 0 | yes | ALREADY_IN_MAIN_SAFE_TO_DELETE | PR #3, merged |
| `docs/derivanta-m3-dogfood-intake-20261101` | `a6a68b68bb57` | 56 / 0 | yes | ALREADY_IN_MAIN_SAFE_TO_DELETE | PR #4, merged |
| `docs/dogfood-beamng-randomizer-0712` | `a2e2953a5eec` | 40 / 0 | yes | OPEN_PR_OR_OTHER_BLOCKER until PR #6 is settled | integrated by PR #9 |
| `docs/voznativa-v05-dogfood-intake-20261105` | `3415828b4dda` | 39 / 0 | yes | OPEN_PR_OR_OTHER_BLOCKER until PR #8 is settled | integrated by PR #9 |
| `evals/fiscal-soc-agent-oracle-wave-20261102` | `4eedfee71660` | 31 / 0 | yes | OPEN_PR_OR_OTHER_BLOCKER until PR #7 is settled | integrated by PR #9 |
| `fix/artifact-cleanup-keeps-report` | `3d24a9047675` | 40 / 0 | yes | ALREADY_IN_MAIN_SAFE_TO_DELETE | integrated by PR #9 |
| `fix/dogfood-prescripta-collect-cause` | `9885ddec05a1` | 39 / 0 | yes | ALREADY_IN_MAIN_SAFE_TO_DELETE | integrated by PR #9 |
| `feature/assertiva-0.10.0-hardening` | `2e34542b4d04` | 57 / 0 | yes | ALREADY_IN_MAIN_SAFE_TO_DELETE | PR #2, merged |
| `fix/assertiva-0.10.1-dogfood` | `819207848b6f` | 42 / 0 | yes | ALREADY_IN_MAIN_SAFE_TO_DELETE | PR #5, merged |
| `release/0.7.2` | `8de5a248c5b9` | 153 / 0 | yes | ALREADY_IN_MAIN_SAFE_TO_DELETE | tag `v0.7.2` stays |
| `release/0.7.3` | `6d49565e09db` | 142 / 0 | yes | ALREADY_IN_MAIN_SAFE_TO_DELETE | never released on its own |
| `release/0.8.0` | `49c6377b80e0` | 129 / 0 | yes | ALREADY_IN_MAIN_SAFE_TO_DELETE | never released on its own |
| `release/0.9.0` | `cf5cb7d0c089` | 87 / 0 | yes | ALREADY_IN_MAIN_SAFE_TO_DELETE | tag `v0.9.0` stays |
| `docs/dogfood-drawlab-m10` | `56855232ff0a` | 87 / 3 | **no** | DIVERGED_PRESERVE | 42 files: 41 identical by blob; `evals/README.md` differs only because `main`'s index is newer, and all 27 links the branch added are present in it |
| `docs/tcc-dogfood-evidence-20261025` | `6a375ec1b8eb` | 87 / 10 | **no** | DIVERGED_PRESERVE | 14 files: the 8 content files are identical by blob; the 6 indexes differ. 18 entries the branch added to the top-level indexes (README, ROADMAP, STATUS, docs/README) are not in them, but every target file exists and is linked from `research/README.md` or `evals/README.md`. PR #1 was closed unmerged; the old indexes are not imported |
| `integration/v1.0-foundation` | `ecb1b23129e2` (before the bump) | 0 / 0 | yes | keep until the release is verified | head of PR #9 |
| `main` | `2618d95caa66` (before the merge) | 41 / 0 | yes | default branch | receives PR #9 |

## Optional cleanup (not run)

After the release is verified, and only with the owner's confirmation:

```bash
# ALREADY_IN_MAIN_SAFE_TO_DELETE (no tag is affected)
git push origin --delete docs/derivanta-m1-dogfood-intake-20261031 docs/derivanta-m3-dogfood-intake-20261101 \
  fix/artifact-cleanup-keeps-report fix/dogfood-prescripta-collect-cause feature/assertiva-0.10.0-hardening \
  fix/assertiva-0.10.1-dogfood release/0.7.2 release/0.7.3 release/0.8.0 release/0.9.0
# after PRs #6, #7 and #8 are settled:
git push origin --delete docs/dogfood-beamng-randomizer-0712 docs/voznativa-v05-dogfood-intake-20261105 \
  evals/fiscal-soc-agent-oracle-wave-20261102
```

Never delete tags (`v0.7.1` … `v1.0.0`). DrawLab and TCC stay unless the owner decides otherwise after reading the
table above.
