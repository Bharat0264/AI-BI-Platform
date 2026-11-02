from experiments.accuracy import generate_cases
from experiments.research_study import apply_policy, run, summarize
import pytest


def test_policy_does_not_mutate_source_and_preserves_selected_evidence():
    response = {'status': 'CLARIFICATION_REQUIRED', 'alternatives': [
        {'status': 'OK', 'evidence_ids': ['a']}], 'evidence': [{'evidence_id': 'a'}, {'evidence_id': 'b'}]}
    first = apply_policy(response, 'first_candidate')
    assert first['status'] == 'OK'
    assert first['evidence'] == [{'evidence_id': 'a'}]
    assert len(response['evidence']) == 2
    assert apply_policy(response, 'clarify_only')['evidence'] == []
    with pytest.raises(ValueError):
        apply_policy(response, 'unknown')


def test_real_ambiguity_policies_separate_safety_from_conditional_completeness():
    case = next(c for c in generate_cases([42]) if c.family == 'ambiguity')
    report = run([case])
    first, clarify, full = (report['summary'][p] for p in ('first_candidate', 'clarify_only', 'conditional_evidence'))
    assert first['unsafe_unconditional_answers'] == 1
    assert clarify['unsafe_unconditional_answers'] == full['unsafe_unconditional_answers'] == 0
    assert clarify['complete_correct_conditional_answers'] == 0
    assert full['complete_correct_conditional_answers'] == 1
    assert summarize([])['answerable_coverage'] is None
