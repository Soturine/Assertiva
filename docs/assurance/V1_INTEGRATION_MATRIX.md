# v1.0 integration matrix

**Branch:** `integration/v1.0-foundation`, created from `origin/main` at `2618d95` (v0.10.1) on 2026-11-13.
**Method:** each contribution was merged with `--no-ff`, so its commits keep their original SHAs and authors and a
GitHub PR closes as merged when the integration reaches `main`. Nothing was squashed or rewritten. Before anything was
merged, the remote state (PRs, heads, checks, rulesets, releases, tags) was checked against the 2026-11-13 snapshot.
It matched.

## Contributions

| ID | Source | Head SHA | Type | Decision | Integrated as | Evidence and status after integration |
|---|---|---|---|---|---|---|
| PR #8 | `docs/voznativa-v05-dogfood-intake-20261105` | `3415828` | INTAKE + CODE + TEST | merged, then qualified | `d17828f` | AXF-VN-01 code kept and hardened (`485df1d`); its last remote CI run was **cancelled** on every job, so it was never qualified remotely. AXF-VN-02..05 were open at intake and are fixed on this branch ([V1_REMEDIATION.md](V1_REMEDIATION.md)) |
| PR #7 | `evals/fiscal-soc-agent-oracle-wave-20261102` | `4eedfee` | EVAL + INTAKE | merged as registered evals | `bb36fe1` | 7 semantic cases, run for the first time in this round ([V1_AGENT_EVALS.md](V1_AGENT_EVALS.md)). No static detector was added for fiscal, RBAC, Grafana or agent-security shapes (no labeled cases) |
| PR #6 (draft) | `docs/dogfood-beamng-randomizer-0712` | `a2e2953` | INTAKE | merged as intake | `7b1a3a1` | AXR-02/03/04/05/06/08 addressed in code (`2e4b437`, `e0ae1c8`, `517ce4b`); AXR-01, 07, 09..14 not changed ([V1_REMEDIATION.md](V1_REMEDIATION.md)) |
| Prescripta-1 | `fix/dogfood-prescripta-collect-cause` | `9885dde` | CODE + TEST | merged, then corrected | `9fd45f9` | `removeprefix("E")` bug (turned `Exception:` into `xception:`), missing sanitization and missing classification fixed in `4bd6840` |
| Prescripta-2 | `fix/artifact-cleanup-keeps-report` | `3d24a90` | CODE + TEST | merged, then corrected | `4b4157d` | the hidden errors (`ignore_errors=True`), the assumed cause and the exported absolute temp path fixed in `163c67f` |
| DrawLab | `docs/dogfood-drawlab-m10` | `5685523` | INTAKE + EVAL | **not merged**: already in `main` | none | all 42 files compared by blob: 41 identical on `main`, `evals/README.md` differs only because `main` evolved |
| TCC (PR #1, closed) | `docs/tcc-dogfood-evidence-20261025` | `6a375ec` | INTAKE + EVAL | **not merged**: already in `main` | none | every case and research file identical on `main`; only the indexes (README, ROADMAP, STATUS, docs/README, evals/README, research/README) differ, and `main`'s versions are newer |
| PRs #2..#5 | merged | none | none | not reimplemented | none | base of v0.10.0 and v0.10.1 |

## Historical deduplication (DrawLab and TCC)

The DrawLab and TCC branches are older and diverge from `main` (46 commits behind). They were compared by **content**,
not by commit count: `git rev-parse origin/main:<path>` against `origin/<branch>:<path>` for every file the branch
changes. No file is missing from `main`. Merging them would only bring back older indexes, so they are recorded here
and left alone. Neither branch was deleted.

## Confidentiality check of what came in

All merged material was searched for secrets, e-mail addresses, absolute local paths and personal data. Nothing was
found. PR #7 links public third-party repositories as read-only comparison sources and paraphrases public comments
without naming anyone. It was already public in an open PR. The private Derivanta Engine repository was not used in any
dogfood run of this round.

## Remote state found (2026-11-13)

- `main` = `2618d95`. `v0.10.1` is the latest GitHub Release, and its wheel matches `SHA256SUMS.txt`.
- Branch protection is off, and the repository has **no rulesets** (checked with `rulesets` and `rules/branches/main`,
  not only `protected`). A proposal is in [V1_RELEASE_READINESS.md](V1_RELEASE_READINESS.md). Nothing was changed.
- The CI ran on both `push` and `pull_request`, so each PR commit was qualified twice. This is fixed in `90905cd`.
