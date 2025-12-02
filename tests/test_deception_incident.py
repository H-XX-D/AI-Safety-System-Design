from orchestrator import Orchestrator
from memory_merkle import MemoryStorage


def _build_orchestrator() -> Orchestrator:
    # Minimal memory storage (empty) for orchestrator initialization
    storage = MemoryStorage(system_id=99, private_key="key")
    return Orchestrator(storage)


from typing import Any


def test_deception_detection_triggers_incident(monkeypatch: Any):
    """Craft a proposal containing suspicious patterns and ensure orchestrator flags deception.

    We inject the proposal into orchestrator.active_proposals with approving reviews to
    exercise the _peer_deception_check path and confirm status becomes 'rejected_deceptive'.
    """
    orch = _build_orchestrator()
    proposal_id = "prop_deceptive_001"
    deceptive_code = """# minimal code\n# artificially complex pattern\n""" + "a" * 600
    deceptive_text = (
        "This proposal is completely safe and has zero risk. "
        "Implementation details omitted for proprietary method. Absolutely certain of success."
    )
    orch.active_proposals[proposal_id] = {
        'proposal': {
            'proposer_id': 3,
            'motivation': deceptive_text,
            'expected_benefits': 'faster and more accurate inference',
            'changes': {'code': deceptive_code},
            'identified_risks': [],  # triggers risk disclosure suspicion
            'admitted_uncertainties': [],
            'confidence_level': 0.99,
        },
        'reviews': [
            {'reviewer_id': 1, 'vote': 'approve'},
            {'reviewer_id': 2, 'vote': 'approve'},
            {'reviewer_id': 4, 'vote': 'approve'},
            {'reviewer_id': 5, 'vote': 'approve'},
        ],
        'status': 'peer_review'
    }

    # Run evaluation (will call deception check internally)
    # Use the public workflow by pushing reviews and letting orchestrator evaluate
    orch._evaluate_peer_reviews(proposal_id)  # type: ignore[attr-defined]

    assert orch.active_proposals[proposal_id]['status'] == 'rejected_deceptive'
    # Ensure incident rationale appears in console output path via recorded reasons.
