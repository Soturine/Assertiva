#!/usr/bin/env python3
import argparse
import json
import xml.etree.ElementTree as ET
from pathlib import Path

def summarize(path: Path):
    root = ET.parse(path).getroot()
    cases = []
    for tc in root.findall('.//testcase') if root.tag != 'testcase' else [root]:
        status = 'passed'
        detail = None
        for tag, state in [('failure','failed'),('error','error'),('skipped','skipped')]:
            el = tc.find(tag)
            if el is not None:
                status = state
                detail = (el.get('message') or (el.text or '')).strip()[:1000]
                break
        ident = '::'.join([x for x in [tc.get('classname'), tc.get('name')] if x])
        cases.append({'id': ident, 'status': status, 'time': float(tc.get('time') or 0), 'detail': detail})
    return {
        'executed': len(cases),
        'passed': sum(c['status']=='passed' for c in cases),
        'failed': sum(c['status'] in ('failed','error') for c in cases),
        'skipped': sum(c['status']=='skipped' for c in cases),
        'duration_seconds': round(sum(c['time'] for c in cases), 6),
        'failures': [c for c in cases if c['status'] in ('failed','error')],
    }

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('junit_xml')
    ap.add_argument('--pretty', action='store_true')
    args = ap.parse_args()
    print(json.dumps(summarize(Path(args.junit_xml)), indent=2 if args.pretty else None, ensure_ascii=False))

if __name__ == '__main__':
    main()
