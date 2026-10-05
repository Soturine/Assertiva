#!/usr/bin/env python3
from pathlib import Path
import json
import sys

ROOT = Path(__file__).resolve().parents[1]
REQUIRED = [
    'README.md','SKILL.md','STATUS.md','ROADMAP.md',
    'docs/ARCHITECTURE.md','docs/QUALITY_MODEL.md','docs/IMPACT_AND_SELECTION.md',
    'docs/FAILURE_LOCALIZATION.md','docs/EVIDENCE_CONTRACT.md','docs/REFACTOR_SAFETY.md',
    'docs/SEMANTIC_UI_AND_BROWSER_ASSURANCE.md','docs/DERIVANTA_INTEGRATION.md','docs/README.md',
    'docs/VERIFICATION_SURFACE.md','docs/EXECUTABLE_ASSURANCE_CORE.md',
    'docs/PIPELINE_AND_DELIVERY_ASSURANCE.md','docs/FTD_FTE_INTEROPERABILITY.md',
    'docs/USER_EXPERIENCE_AND_REPORTING.md','docs/TEST_IDENTITY_AND_DISCOVERY.md',
    'docs/TEST_COMPOSITION_AND_MATERIALIZATION.md',
    'docs/NEGATIVE_PATH_AND_ERROR_ASSURANCE.md',
    'docs/CANDIDATE_QUALIFICATION_AND_TEST_THE_TESTS.md',
    'research/2026-09-30-ecosystem-benchmark.md','evals/README.md','evals/CASE_SPEC.md',
    'schemas/test-run.schema.json','schemas/failure-cluster.schema.json',
    'schemas/selection-decision.schema.json','schemas/assertion-observation.schema.json',
    'schemas/ui-locator-evidence.schema.json','schemas/verification-check.schema.json',
    'schemas/assurance-report.schema.json','schemas/test-composition.schema.json',
    'schemas/candidate-qualification.schema.json','schemas/error-contract.schema.json'
]

def main():
    errors = []
    for rel in REQUIRED:
        if not (ROOT / rel).exists():
            errors.append('missing: ' + rel)

    for p in sorted((ROOT / 'schemas').glob('*.json')):
        try:
            json.loads(p.read_text(encoding='utf-8'))
        except Exception as exc:
            errors.append(f'invalid json {p.relative_to(ROOT)}: {exc}')

    for p in sorted((ROOT / 'docs').glob('*.md')):
        if not p.read_text(encoding='utf-8').lstrip().startswith('# '):
            errors.append('markdown without H1: ' + str(p.relative_to(ROOT)))

    eval_readme = (ROOT / 'evals/README.md').read_text(encoding='utf-8')
    for p in sorted((ROOT / 'evals/cases').glob('*.md')):
        if p.name not in eval_readme:
            errors.append('eval not registered: ' + str(p.relative_to(ROOT)))

    structured_sections = [
        '## Identity','## Context / fixture','## Prompt / task','## Expected behavior',
        '## Prohibited behavior','## Evidence requirements','## Scoring dimensions',
        '## Acceptable alternatives','## Pass condition',
    ]
    for p in sorted((ROOT / 'evals/cases').glob('*.md')):
        body = p.read_text(encoding='utf-8')
        if 'status: grader-ready' in body:
            for section in structured_sections:
                if section not in body:
                    errors.append(f'grader-ready eval missing {section}: {p.relative_to(ROOT)}')

    if errors:
        print('\n'.join(errors))
        return 1
    print('Assertiva repository validation passed.')
    return 0

if __name__ == '__main__':
    sys.exit(main())
