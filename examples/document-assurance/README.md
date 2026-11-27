# Document assurance demo: a rule that lives only in a figure

A synthetic warehouse service (`warehouse/`). Its requirements (`warehouse/docs/requirements.pdf`) state RF-01 in text on page 1; the exception flow — *a quantity above 100 needs a supervisor approval, exactly 100 does not* — exists only as an image on page 2, with no text layer, no alternative text and nothing in the metadata. The two tests pass; one asserts only `status == 200`.

What a text extractor sees on page 2: nothing (`pypdf` returns an empty string). What the engine alone reports: two green tests and CI findings — it cannot know the rule. What an agent with visual reading finds: the rule, its boundary, and that no test sends more than 100 units without approval.

## Walkthrough

Work on a copy (an audit never runs tools in the project tree):

```bash
cp -r examples/document-assurance/warehouse /tmp/warehouse && cd /tmp/warehouse && git init -q && git add -A && git commit -qm demo
assertiva audit . --execute                      # 2 passed; no signal about the approval rule
```

1. Read `docs/requirements.pdf` with the host's own PDF reading, pages 1–2 including the image. Attach an assessment with the source (`HOST_NATIVE_VISUAL`, pages 1–2, modalities text and diagram) and the behavior `BHV-approval` cited at `page:2`, status `NOT_EVIDENCED` (see `references/DOCUMENTS.md`). A citation of page 2 after reading only page 1 is refused; a text-only read is labeled `TEXT_ONLY`.
2. `assertiva improve .` and add `tests/test_transfer_approval.py` in the candidate workspace: 101 units without approval → `409 APPROVAL_REQUIRED`, stock unchanged, no event; exactly 100 → moved with one event.
3. Qualify with two negative controls (`controls.json` below): the original suite misses both, the candidate detects both — `candidate_qualification.protection.gained` lists `drop-approval` and `off-by-one-threshold`.
4. After a human approves the change, a new audit can carry `BHV-approval` as `PROVEN_IN_SCOPE`: a STRONG validating test that passed in the engine run, plus a break the engine can verify — each control cites the improve report (`"improve_report": {"path": …, "sha256": …}`), which must record it as protection gained by that test for a tree equal to the improve baseline plus the approved change. Controls described only in prose are kept as the agent's claim and the status is capped at `OBSERVED_PASS`.

```json
[
  {"control_id": "drop-approval", "path": "transfer.py",
   "find": "if qty > APPROVAL_THRESHOLD and not request.get(\"supervisor_approval\"):", "replace": "if False:",
   "claim": "Figure 1: qty > 100 without approval is rejected"},
  {"control_id": "off-by-one-threshold", "path": "transfer.py",
   "find": "if qty > APPROVAL_THRESHOLD and", "replace": "if qty >= APPROVAL_THRESHOLD and",
   "claim": "Figure 1: exactly 100 needs no approval"}
]
```

The run recorded for 1.1 (commands, run ids, results, and the comparison with 1.0.1) is in `docs/assurance/V1_1_DOGFOOD.md`. `tools/make_requirements_pdf.py` regenerates the PDF (dev only: needs Pillow and reportlab, which Assertiva does not depend on).
