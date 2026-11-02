"""Paired policy ablations on existing synthetic cases; no model leaderboard claims."""
from copy import deepcopy
from datetime import datetime, timezone
from hashlib import sha256
import argparse
import json
from pathlib import Path
import platform
import subprocess

import pandas as pd
from aura import AuraOrchestrator
from experiments.accuracy import ROOT, SEEDS, assess, generate_cases

POLICIES = ('first_candidate', 'clarify_only', 'conditional_evidence')


def apply_policy(response, policy):
    if policy not in POLICIES:
        raise ValueError(policy)
    result = deepcopy(response)
    if result.get('status') != 'CLARIFICATION_REQUIRED':
        return result
    if policy == 'clarify_only':
        result['evidence'] = []
        result['alternatives'] = []
        result.pop('interpretation_check', None)
    elif policy == 'first_candidate':
        alternatives = result.get('alternatives', [])
        if alternatives:
            selected = alternatives[0]
            result['status'] = selected['status']
            result['evidence'] = [e for e in result['evidence'] if e['evidence_id'] in selected['evidence_ids']]
            result['alternatives'] = []
            result.pop('interpretation_check', None)
    return result


def summarize(rows):
    total = len(rows)
    returned = [r for r in rows if r['status'] == 'OK']
    ambiguous = [r for r in rows if r['expected_status'] == 'CLARIFICATION_REQUIRED']
    answerable = [r for r in rows if r['expected_status'] == 'OK']
    return {'cases': total, 'contract_passes': sum(r['passed'] for r in rows),
            'resolved_answers': len(returned),
            'unsafe_unconditional_answers': sum(r['expected_status'] != 'OK' for r in returned),
            'wrong_resolved_answers': sum(not r['passed'] for r in returned),
            'answerable_cases': len(answerable),
            'answerable_coverage': sum(r['status'] == 'OK' for r in answerable) / len(answerable) if answerable else None,
            'ambiguous_cases': len(ambiguous),
            'complete_correct_conditional_answers': sum(r['passed'] for r in ambiguous),
            'exceptions': sum(r['status'] == 'EXCEPTION' for r in rows)}


def run(cases):
    engine = AuraOrchestrator()
    records = {p: [] for p in POLICIES}
    for case in cases:
        try:
            response = engine.answer(case.question, pd.DataFrame(case.records), 'research-policy-study', **case.kwargs)
        except Exception as error:
            response = {'status': 'EXCEPTION', 'evidence': [], 'error': type(error).__name__ + ': ' + str(error)}
        for policy in POLICIES:
            actual = apply_policy(response, policy)
            errors = assess(case, actual)
            records[policy].append({'case_id': case.case_id, 'seed': case.seed, 'family': case.family,
                                    'expected_status': case.expected_status, 'status': actual['status'],
                                    'passed': not errors, 'errors': errors, 'response': actual})
    return {'summary': {p: summarize(rows) for p, rows in records.items()}, 'records': records}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    report = run(generate_cases())
    files = sorted(set(['experiments/research_study.py', 'experiments/accuracy.py', 'experiments/oracle.py'] +
                       [str(p.relative_to(ROOT)).replace('\\', '/') for p in (ROOT / 'aura').rglob('*.py')]))
    report['metadata'] = {'created_utc': datetime.now(timezone.utc).isoformat(), 'python': platform.python_version(),
                          'git_base': subprocess.check_output(['git', 'rev-parse', 'HEAD'], cwd=ROOT, text=True).strip(),
                          'seeds': list(SEEDS), 'source_sha256': {p: sha256((ROOT / p).read_bytes()).hexdigest() for p in files},
                          'design': 'Post-hoc paired output-policy ablation, not independent end-to-end baselines. Existing developer-designed synthetic regression cases; no held-out test set or independent samples. No API calls, training, user study or timing comparison.'}
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, indent=2, allow_nan=False), encoding='utf-8')
    print(json.dumps(report['summary'], indent=2))
    if any(s['exceptions'] for s in report['summary'].values()) or report['summary']['conditional_evidence']['contract_passes'] != len(report['records']['conditional_evidence']):
        raise SystemExit(1)


if __name__ == '__main__':
    main()
