#!/usr/bin/env python3
from pathlib import Path
import json
import sys

ROOT = Path(__file__).resolve().parents[1]
REQUIRED = [
    'README.md','SKILL.md','STATUS.md','ROADMAP.md',
    'docs/ARCHITECTURE.md','docs/QUALITY_MODEL.md','docs/IMPACT_AND_SELECTION.md',
    'docs/FAILURE_LOCALIZATION.md','docs/EVIDENCE_CONTRACT.md','docs/REFACTOR_SAFETY.md',
    'research/2026-09-30-ecosystem-benchmark.md','evals/README.md',
    'schemas/test-run.schema.json','schemas/failure-cluster.schema.json','schemas/selection-decision.schema.json'
]

def main():
    errors = []
    for rel in REQUIRED:
        if not (ROOT / rel).exists():
            errors.append('missing: ' + rel)
    for p in (ROOT / 'schemas').glob('*.json'):
        try:
            json.loads(p.read_text(encoding='utf-8'))
        except Exception as exc:
            errors.append(f'invalid json {p.relative_to(ROOT)}: {exc}')
    eval_readme = (ROOT / 'evals/README.md').read_text(encoding='utf-8')
    for p in sorted((ROOT / 'evals/cases').glob('*.md')):
        if p.name not in eval_readme:
            errors.append('eval not registered: ' + str(p.relative_to(ROOT)))
    for rel in [x for x in REQUIRED if x.endswith('.md')]:
        p = ROOT / rel
        if p.exists() and not p.read_text(encoding='utf-8').lstrip().startswith('# '):
            errors.append('markdown without H1: ' + rel)
    if errors:
        print('\n'.join(errors))
        return 1
    print('Assertiva repository validation passed.')
    return 0

if __name__ == '__main__':
    sys.exit(main())
