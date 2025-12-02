import logging
from datetime import datetime

from orchestrator import Orchestrator
from orchestrator_sandbox import SandboxEnvironmentManager
from memory_merkle import MemoryStorage


def _make_simple_proposal(proposer_id: int):
    return {
        'proposal_id': f"prop_flat_{datetime.now().timestamp()}",
        'proposer_id': proposer_id,
        'title': 'Minor refactor for clarity',
        'motivation': 'Improve readability without changing behavior.',
        'expected_benefits': 'Clearer code',
        'identified_risks': ['minimal regression risk'],
        'admitted_uncertainties': ['none'],
        'confidence_level': 0.6,
        'changes': {
            'component': 'dummy_component',
            'code': "print('hello world')"
        },
    }


def test_sandbox_flatten_structure(tmp_path, caplog):
    caplog.set_level(logging.INFO)
    storage = MemoryStorage(system_id=1, private_key='key1')
    env_mgr = SandboxEnvironmentManager()
    orch = Orchestrator(storage, environment_manager=env_mgr)

    proposal = _make_simple_proposal(1)
    orch.handle_improvement_proposal(proposal)
    pid = proposal['proposal_id']
    # Simulate enough peer approvals to trigger sandbox quickly
    for rid in [2,3,4,5]:
        orch.record_peer_review(pid, {
            'reviewer_id': rid,
            'vote': 'approve',
            'comments': 'ok'
        })

    rec = orch.active_proposals[pid]
    assert 'test_results' in rec
    assert 'sandbox_flat' in rec, 'Flattened sandbox results missing'
    flat = rec['sandbox_flat']
    # Required keys subset
    required = {
        'alignment_tests_passed',
        'alignment_test_count',
        'performance_change',
        'performance_metrics',
        'regression_tests_passed',
        'error_count',
        'red_team_attacks_blocked',
        'test_cases_run',
        'timestamp'
    }
    missing = required - set(flat.keys())
    assert not missing, f"Missing flattened keys: {missing}"
    assert isinstance(flat['performance_metrics'], dict)
    assert isinstance(flat['alignment_tests_passed'], bool)
    # performance_change should be a normalized fraction (-1..1 typically)
    assert -1.0 <= flat['performance_change'] <= 1.0
