# Dogfood — DrawLab M10 (Assertiva 0.9.0)

Assertiva 0.9.0 (`cf5cb7d`) was used to audit a private Python + TypeScript research project (DrawLab, a lottery
research platform; about 1 300 Python tests, a one-hour suite on a Windows laptop) before and after a milestone. This
page is what can be published: no code, test, path, data or report of that project is reproduced. The audited
project's own reports stay in its private repository.

Three instruments were kept apart:

1. **the skill** — an agent followed `SKILL.md` and `references/` (read from the files; the slash skill was not
   installed in that session) and kept a decision log;
2. **the engine** — `assertiva audit` with `--execute`, `--ctrf`, `--mutate` and `--assessment`;
3. **an independent evaluation of the skill** — `evals/semantic.py` with evaluated agents and judges in separate
   contexts ([results](../../../evals/results/2026-10-30-drawlab-m10/README.md)).

## What happened

| Step | Engine outcome | What the agent concluded |
| --- | --- | --- |
| baseline, static | 12 findings, 22 declared checks | leads to read |
| baseline, `--execute` run 1 | 717 passed, 434 errors, 1 failed | the 434 are one environment fingerprint (pytest temp root ACL); engine labelled them PRODUCT → [AG-01/02](GAP_REGISTER.md) |
| baseline, run 2 | identical | the agent's redirect was ineffective (operator error, kept) |
| baseline, run 3 | BLOCKED: 900 s timeout | correct; cannot be raised without writing the project's file → [AG-10](GAP_REGISTER.md) |
| baseline, `--assessment` | attached, report re-rendered | dispositions for every finding; 20 of 45 effectiveness items read, 0 false greens among them |
| final, `--execute --mutate` | 1265 passed, 9 failed; mutation refused (suite not green) | 1 failure is the copy lacking `.git`; the others were investigated against the baseline in the same environment ([AGENT_VS_ENGINE](AGENT_VS_ENGINE.md)); mutation done by the agent in its own copies with targeted tests and labelled as such → [AG-11](GAP_REGISTER.md) |

## Meta-evaluation

* **Did the skill find what an independent auditor found?** The agent was also the independent auditor here, so recall
  cannot be measured; what can be said is that every engine finding was dispositioned with evidence, and the agent
  added four findings the engine could not raise (environment ACL, a failing test on the default branch, a fragile
  translation test, a biased null in the project's new code).
* **Hallucinated or misclassified conclusions?** Engine: the origin of the 434 errors (PRODUCT instead of
  infrastructure) and 11 heuristic candidates that the code disproved. Agent: two operator errors in its own
  environment handling (recorded), and a weak assertion it wrote in a new test and replaced.
* **Did `--execute` run what it claims?** Yes, with its own exit status and per-invocation outcomes; timeouts and
  refusals were reported as BLOCKED, never as passes.
* **Was `--mutate` completed?** No — refused both times (suite not green at the baseline of the mutation run). The
  agent's own Cosmic Ray runs on two files (191 and 794 mutants, targeted tests) were real but are agent evidence.
* **Cost:** see AGENT_VS_ENGINE; the expensive parts were the one-hour suite, run three times.
* **Semantic evaluation:** 15 cases (8 new, derived from this dogfood, synthetic), 14 PASS and 1 REVIEW; limits of
  independence are stated in the results page.

Opportunities, each with severity, reproducer, proposal and acceptance: [GAP_REGISTER.md](GAP_REGISTER.md).
