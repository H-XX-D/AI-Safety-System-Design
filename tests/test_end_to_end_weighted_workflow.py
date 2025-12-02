import logging
from datetime import datetime

from core.orchestrator import Orchestrator
from infrastructure.memory_merkle import MemoryStorage
from infrastructure.reputation_system import ReputationRating
from types import SimpleNamespace


def _make_proposal(proposer_id: int, code: str):
    return {
        'proposal_id': f"prop_{datetime.now().timestamp()}",
        'proposer_id': proposer_id,
        'title': 'Speed up data pipeline',
        'motivation': 'Improve performance while respecting core values.',
        'expected_benefits': 'Faster processing',
        'identified_risks': ['possible resource overuse mitigated by limits'],
        'admitted_uncertainties': ['throughput variance'],
        'confidence_level': 0.7,
        'changes': {
            'code': code,
        },
    }


def test_end_to_end_weighted_voting_and_execution(tmp_path, caplog):
    caplog.set_level(logging.INFO)
    storage = MemoryStorage(system_id=1, private_key="key1")
    orch = Orchestrator(storage)

    # Enable weighted voting via internal flag if present
    # (Assumes config defaults to disabled; set in-memory flag for test)
    try:
        orch._rep_options['weighted_voting'] = True  # type: ignore[index]
    except Exception:
        pass

    # Seed advanced reputation so reviewers have non-neutral weights
    # We have 5 systems; proposer is 1, reviewers are others (2..5).
    # To increase reviewer composite scores, add ratings they RECEIVED from another rater (not self).
    rm = orch.reputation_advanced
    for ratee_id in [2, 3, 4, 5]:
        rm.add_rating(ReputationRating(
            rater_id=1,
            ratee_id=ratee_id,
            alignment_score=85,
            trust_score=80,
            knowledge_score=78,
            timestamp=datetime.now().isoformat(),
            justification="seed",
            context="peer_rating",
        ))
    # Additional cross rating
    rm.add_rating(ReputationRating(
        rater_id=2,
        ratee_id=3,
        alignment_score=90,
        trust_score=88,
        knowledge_score=82,
        timestamp=datetime.now().isoformat(),
        justification="cross",
        context="peer_rating"
    ))

    # Reduce chance of automated deception rejection by stubbing detector to always return benign
    orch.deception_detector = SimpleNamespace(
        detect_deception=lambda *args, **kwargs: SimpleNamespace(
            deception_detected=False,
            deception_type=None,
            severity=None,
            confidence=0.0,
            reasons=[],
            evidence={'memory': {}}
        )
    )

    # Build proposal with a tiny script that exits 0
    code = "print('hello'); import sys; sys.exit(0)"
    proposal = _make_proposal(1, code)
    orch.handle_improvement_proposal(proposal)

    # Create four reviews (approve) by reviewers 2..5
    pid = proposal['proposal_id']
    for reviewer_id in [2, 3, 4, 5]:
        orch.record_peer_review(pid, {
            'reviewer_id': reviewer_id,
            'vote': 'approve',
            'comments': 'Looks good'
        })

    # After 4 reviews, orchestrator should have run sandbox and set status accordingly
    record = orch.active_proposals[pid]
    assert record['status'] in ('testing', 'awaiting_human_approval', 'test_failed')

    # Ensure sandbox results exist and execution ran
    tr = record.get('test_results')
    assert isinstance(tr, dict)
    assert 'execution' in tr
    assert tr['execution'].get('executed') is True
    assert 'exit_code' in tr['execution']

    # Given the strict thresholds, overall_pass may be True or False depending on other synthetic scores
    # We only assert execution worked and status reached a post-testing state
    assert record['status'] in ('awaiting_human_approval', 'test_failed')
