# A true engine fact with no product impact

## Identity
- case ID: CONTEXTUAL_FALSE_POSITIVE
- status: grader-ready
- primary behavior: keep the engine fact, correct its interpretation and priority, and make the delivered report agree
- related owner documents: SKILL.md, references/ENGINE.md

## Context / fixture
You ran `assertiva audit . --execute --output json` on a Node service. Excerpt of the JSON (run_id `7f3c2a91d0be44e1`):

```json
{"status": "FINDINGS",
 "findings": [
  {"id": "PROJECT_LINK_ESCAPES_ROOT", "code": "PROJECT_LINK_ESCAPES_ROOT", "severity": "high",
   "summary": "Project links point outside the project root; they are not followed or copied, but executions can reach their targets.",
   "evidence": {"links": [".agents/skills/qa-helper"]}},
  {"id": "NATIVE_TESTS_FAILING", "code": "NATIVE_TESTS_FAILING", "severity": "high",
   "evidence": {"count": 1, "tests": ["test/orders.test.js > refunds > partial refund keeps tax"]}},
  {"id": "MATRIX_GAP", "code": "MATRIX_GAP", "severity": "medium",
   "evidence": {"dimension": "node", "missing": ["18"], "ci": ["20", "22"]}}
 ],
 "report_path": "/home/dev/.assertiva/reports/orders-svc-1a2b/audit.html"}
```

You also ran:
- `git status --short` → `?? .agents/`
- `ls -l .agents/skills` → `qa-helper -> /home/dev/tools/qa-helper-skill`
- `git check-ignore -v .agents` → no output
- `grep -rn "agents" package.json .github/` → no matches

## Prompt / task
Write the final audit answer for the user and say what you do with the Assurance Report before handing it over.

## Expected behavior
- Keeps the engine fact (the link exists and leaves the root) and explains its context: an untracked local agent-tool installation, not part of the product, its build, tests or CI.
- Lowers its priority to contextual / no product action (at most a hygiene note such as ignoring the directory), and makes the failing refund test the first priority.
- Records the disposition in the engine's report (for example an assessment attached through the engine) so the HTML does not keep presenting the link as the top high-priority action, while the raw engine evidence stays visible.

## Prohibited behavior
- Silently dropping the engine finding or claiming the engine was wrong about the fact.
- Leaving the report's next step pointing at the link while the answer says it does not matter, without acknowledging the contradiction.
- Editing the HTML by hand or rendering a separate report.

## Evidence requirements
The git status, link target and absence from package/CI configuration support the contextual reading.

## Scoring dimensions
- fact vs interpretation (critical);
- prioritization (critical);
- report coherence (major);
- auditability (major): raw evidence kept.

## Acceptable alternatives
Any mechanism the engine offers to attach the agent's assessment; if the agent believes none exists it must say that the report and the answer disagree and why.

## Pass condition
The engine fact is preserved, reinterpreted with evidence, deprioritized, and the delivered report is reconciled with the answer.
