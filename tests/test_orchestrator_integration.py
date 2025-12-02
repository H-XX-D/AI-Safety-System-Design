from datetime import datetime
from typing import Dict

import pytest

import worm_manifest
from core_values import CoreValues
from debate_engine import Argument, Claim, DebateResult, DebateTurn
from memory_merkle import MemoryStorage
from orchestrator import Orchestrator
from orchestrator_sandbox import SandboxEnvironmentManager


@pytest.fixture(autouse=True)
def configure_core_values(monkeypatch: pytest.MonkeyPatch):
    import worm_manifest
    worm_manifest.enable_software_equivalence_mode(justification='test')
    monkeypatch.setenv('CORE_VALUES_KNOWN_HASH', CoreValues.compute_hash())
    # Set alignment filter hash to the actual locally computed hash so integrity checks pass
    import bulletproof_alignment_filter
    monkeypatch.setenv('CORE_ALIGNMENT_FILTER_HASH', bulletproof_alignment_filter.BulletproofAlignmentFilter.get_own_code_hash())
    monkeypatch.delenv('WORM_MOCK_MANIFEST', raising=False)
    if hasattr(worm_manifest, '_manifest_cache'):
        monkeypatch.setattr(worm_manifest, '_manifest_cache', None)
    yield
    # Ensure tests don't leave the software-equivalence enabled between tests
    worm_manifest.disable_software_equivalence_mode()


def _make_proposal(proposal_id: str = 'demo-001') -> Dict[str, object]:
    return {
        'proposal_id': proposal_id,
        'proposer_id': 1,
        'title': 'Optimize processing pipeline',
        'motivation': 'Improve overall throughput with smarter caching and batching.',
        'expected_benefits': 'Lower latency and reduced compute cost.',
        'identified_risks': ['Regression in cache consistency'],
        'admitted_uncertainties': ['Scaling behavior under burst load'],
        'rollback_plan': 'Revert deployment to last known good build.',
        'confidence_level': 0.7,
        'changes': {
            'code': 'def optimized_function():\n    return sum(range(1000))',
            'description': 'Optimize sum calculation by avoiding repeated allocations.'
        },
        'timestamp': datetime.now().isoformat(),
    }


def test_orchestrator_flow() -> None:
    memory_storage = MemoryStorage(system_id=0, private_key='test-key', include_entry_hash_in_metadata=True)
    orchestrator = Orchestrator(memory_storage)

    # Ensure sandbox security checks consider limits enforced.
    orchestrator.environment_manager.max_memory_kb = 256 * 1024
    orchestrator.environment_manager.cpu_time_sec = 5

    proposal = _make_proposal()
    orchestrator.handle_improvement_proposal(proposal)

    # Submit four peer reviews to trigger supermajority path.
    for reviewer_id in range(2, 6):
        review = {
            'reviewer_id': reviewer_id,
            'vote': 'approve',
            'confidence': 'high',
            'risk': 'low',
            'timestamp': datetime.now().isoformat(),
            'justification': 'Thorough tests attached; rollback plan is sufficient.',
        }
        orchestrator.record_peer_review(proposal['proposal_id'], review)

    record = orchestrator.active_proposals[proposal['proposal_id']]
    results = record['test_results']

    assert isinstance(results, dict)
    assert results['overall_pass'], results

    alignment = results['alignment']
    security = results['security']
    execution = results['execution']

    assert alignment['approved'] is True
    assert alignment['score'] >= 90.0
    assert security['score'] >= 80.0
    assert security['vulnerabilities_found'] == 0
    assert execution['executed'] is True
    assert execution['exit_code'] == 0

    summary = record.get('debate_summary')
    assert summary is not None
    participants = {turn['participant_id'] for turn in summary['turns']}
    expected_turns = len(participants) * getattr(orchestrator, '_debate_rounds', 1)
    assert len(summary['turns']) == expected_turns

    verifications = record.get('claim_verifications')
    assert isinstance(verifications, dict) and verifications
    debate_result = record.get('debate_result')
    assert isinstance(debate_result, DebateResult)
    assert debate_result.consensus
    assert debate_result.sandbox_feedback == verifications

    card = orchestrator.generate_impact_card(proposal['proposal_id'])
    assert 'sandbox_advisories' in record
    assert 'edge_case_advisories' in card
    assert isinstance(card['edge_case_advisories'], list)
    assert card['edge_case_advisories'] == record['sandbox_advisories']
    assert card['debate_rounds'] == getattr(orchestrator, '_debate_rounds', 1)
    assert card['debate_consensus'] == debate_result.consensus
    assert isinstance(card['debate_participants'], list) and card['debate_participants']
    assert isinstance(card['verified_claims'], list)
    assert isinstance(card['disputed_claims'], list)


def test_debate_feedback_adjusts_scores() -> None:
    storage = MemoryStorage(system_id=0, private_key='test-key', include_entry_hash_in_metadata=True)
    orchestrator = Orchestrator(storage, environment_manager=SandboxEnvironmentManager())

    positive_claim = Claim(text='Improves latency significantly', category='performance', claim_id='c-1')
    negative_claim = Claim(text='No safety risk detected', category='risk', claim_id='c-2')

    positive_argument = Argument(
        stance='support',
        reasoning='We tackle risk and uncertainty directly with evidence.',
        claims=[positive_claim],
        confidence=0.8,
    )
    negative_argument = Argument(
        stance='oppose',
        reasoning='General critique without risk focus.',
        claims=[negative_claim],
        confidence=0.4,
    )

    turn_support = DebateTurn(round_index=1, participant_id=2, argument=positive_argument)
    turn_oppose = DebateTurn(round_index=1, participant_id=3, argument=negative_argument)

    result = DebateResult(
        topic='Demo topic',
        turns=[turn_support, turn_oppose],
        scores={2: 0.0, 3: 0.0},
        consensus='',
        claims_for_verification=[positive_claim, negative_claim],
        sandbox_feedback={},
    )

    feedback = {'c-1': True, 'c-2': False}
    orchestrator._apply_claim_feedback(result, feedback)

    assert result.scores[2] > result.scores[3]
    assert result.scores[2] > 0.0
    assert result.scores[3] < 0.0
    assert result.consensus == positive_argument.reasoning
    assert result.sandbox_feedback['c-1'] is True
    assert result.sandbox_feedback['c-2'] is False

    previous_scores = dict(result.scores)
    orchestrator._apply_claim_feedback(result, feedback)
    assert result.scores == previous_scores
