"""Tests for Human Trust Layer additions.

Verifies:
 - Impact card structure
 - Human decision signing & verification
 - Grace period scheduling basic behavior
"""
from datetime import datetime
from typing import Dict, Any

from orchestrator import Orchestrator
from orchestrator_sandbox import SandboxEnvironmentManager
from memory_merkle import MemoryStorage
from human_review import sign_human_decision, verify_human_signature


def _make_demo_proposal(pid: str) -> Dict[str, Any]:
    return {
        'proposal_id': pid,
        'proposer_id': 1,
        'title': 'Improve caching efficiency',
        'motivation': 'Reduce redundant recomputation in subsystem A to save latency.',
        'expected_benefits': 'Lower average response time, reduced CPU usage.',
        'identified_risks': ['Potential stale reads'],
        'admitted_uncertainties': ['Cache hit ratio under new workload'],
        'rollback_plan': 'Disable new cache layer and flush entries.',
        'changes': {'component': 'cache_layer', 'code': 'print("demo")'},
        'confidence_level': 0.7,
        'timestamp': datetime.now().isoformat()
    }


def test_impact_card_and_signature_roundtrip():
    storage = MemoryStorage(system_id=1, private_key="demo_key")
    orch = Orchestrator(storage, environment_manager=SandboxEnvironmentManager())
    pid = 'P001'
    proposal = _make_demo_proposal(pid)
    orch.handle_improvement_proposal(proposal)

    # Simulate 4 peer reviews to trigger sandbox testing
    for rid in [2, 3, 4, 5]:
        review = {
            'reviewer_id': rid,
            'vote': 'approve',
            'timestamp': datetime.now().isoformat(),
        }
        orch.record_peer_review(pid, review)

    # After sandbox testing, status should be awaiting human approval
    assert orch.active_proposals[pid]['status'] == 'awaiting_human_approval'

    card = orch.generate_impact_card(pid)
    # Basic structure assertions
    for key in ['proposal_id', 'reversibility', 'clarity_score', 'review_count', 'expected_reviews']:
        assert key in card
    assert card['proposal_id'] == pid
    assert card['reversibility'] == 'present'
    assert 0.0 <= card['clarity_score'] <= 1.0

    # Human decision signing
    secret = 'test_human_secret'
    decision_msg = {
        'reviewer_id': 99,
        'proposal_id': pid,
        'approved': True,
        'timestamp': datetime.now().isoformat()
    }
    sig = sign_human_decision(decision_msg, secret)
    assert verify_human_signature(decision_msg, secret, sig)

    orch.record_human_decision(pid, True, reviewer_id=99, signature=sig, secret=secret, signed_timestamp=decision_msg['timestamp'])
    assert orch.active_proposals[pid]['status'] in {'approved', 'finalized'}  # may be approved then finalized later
    assert 'human_signature' in orch.active_proposals[pid]


def test_reaffirmation_flow():
    storage = MemoryStorage(system_id=1, private_key="demo_key")
    orch = Orchestrator(storage, environment_manager=SandboxEnvironmentManager())
    pid = 'P002'
    orch.handle_improvement_proposal(_make_demo_proposal(pid))
    for rid in [2, 3, 4, 5]:
        orch.record_peer_review(pid, {
            'reviewer_id': rid,
            'vote': 'approve',
            'timestamp': datetime.now().isoformat(),
        })
    assert orch.active_proposals[pid]['status'] == 'awaiting_human_approval'
    # Approve without signature
    orch.record_human_decision(pid, True)
    assert orch.active_proposals[pid]['status'] == 'approved'
    # Reaffirm immediately
    assert orch.reaffirm_approval(pid) is True
    # Reaffirm now triggers an attempt to deploy; in the default mode this should set status to 'deployed'
    assert orch.active_proposals[pid]['status'] == 'deployed'
