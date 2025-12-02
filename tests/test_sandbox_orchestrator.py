from orchestrator import Orchestrator
from orchestrator_sandbox import SandboxEnvironmentManager
from memory_merkle import MemoryStorage
from typing import Any, Dict


def test_orchestrator_sandbox_testing_flow():
    storage = MemoryStorage(system_id=1, private_key="k")
    orch = Orchestrator(storage, environment_manager=SandboxEnvironmentManager())

    # Fake proposal
    proposal: Dict[str, Any] = {
        'proposal_id': 'prop_123',
        'proposer_id': 2,
        'title': 'Improve performance',
        'motivation': 'Reduce latency in pipeline for better throughput and reliability of system operations.',
        'changes': {'component': 'pipeline', 'code': 'print("hello")'},
        'expected_benefits': 'Faster throughput',
        'testable_predictions': ['Speed improvement'],
        'rollback_plan': 'Revert configuration file',
        'identified_risks': ['regression', 'overuse'],
        'admitted_uncertainties': ['long-term effects'],
        'confidence_level': 0.8
    }

    orch.handle_improvement_proposal(proposal)
    # Simulate four peer reviews to trigger evaluation
    review: Dict[str, Any] = {
        'reviewer_id': 3,
        'vote': 'approve'
    }
    for rid in [3,4,5,1]:
        r = dict(review)
        r['reviewer_id'] = rid
        orch.record_peer_review('prop_123', r)

    # Status should be one of recognized terminal/intermediate states including deceptive rejection
    assert orch.active_proposals['prop_123']['status'] in [
        'awaiting_human_approval', 'test_failed', 'testing', 'approved', 'human_rejected', 'rejected_deceptive', 'rejected'
    ]


def test_seventh_validator_basic():
    from seventh_validator import SeventhValidator
    validator = SeventhValidator()
    proposal: Dict[str, Any] = {
        'motivation': 'This change will improve system reliability and transparency significantly by refactoring components.',
        'expected_benefits': 'Higher reliability',
        'identified_risks': ['regression', 'drift'],
        'admitted_uncertainties': ['impact variance'],
        'rollback_plan': 'Restore previous commit',
        'confidence_level': 0.7
    }
    outcome = validator.validate(proposal)
    assert outcome.passed is True
    assert outcome.severity == 'info'
