import math
from typing import Dict, Any
from core.orchestrator import Orchestrator
from infrastructure.memory_merkle import MemoryStorage
from security.worm_manifest import worm_manifest


def make_dummy_proposal(system_id: int) -> Dict[str, Any]:
    proposal: Dict[str, Any] = {
        'proposal_id': 'test_prop_001',
        'proposer_id': system_id,
        'title': 'Test Improvement',
        'motivation': 'Improve performance of component X by refactoring loop',
        'changes': {'component': 'inference_optimization.py', 'refactor': True},
        'expected_benefits': '10% faster inference',
        'testable_predictions': ['Speed improvement >5%'],
        'rollback_plan': 'Restore previous version via git',
        'timestamp': '2025-11-07T00:00:00'
    }
    return proposal


def test_reward_multiplier_applied():
    # Setup orchestrator
    storage = MemoryStorage(system_id=6, private_key='key')
    orch = Orchestrator(memory_storage=storage)

    # Baseline: no permanent penalty
    proposal = make_dummy_proposal(system_id=3)
    # Ensure clean baseline for proposer system (reset any prior penalties from other tests)
    previous_penalty = worm_manifest.permanent_penalties.get(3, 0.0)
    worm_manifest.reset_system_penalties(3)
    orch.handle_improvement_proposal(proposal)
    base_reward = orch.compute_reward_for_proposal(
        proposal_id=proposal['proposal_id'],
        outcome='approved',
        human_understanding_score=0.9,
        debate_context=None
    )

    # Apply permanent penalty (simulate prior confirmed deception)
    worm_manifest.permanent_penalties[3] = 0.40  # 40% penalty -> multiplier 0.60

    penalized_reward = orch.compute_reward_for_proposal(
        proposal_id=proposal['proposal_id'],
        outcome='approved',
        human_understanding_score=0.9,
        debate_context=None
    )

    multiplier_recorded = orch.active_proposals[proposal['proposal_id']]['permanent_penalty_multiplier']

    assert math.isclose(multiplier_recorded, 0.60, rel_tol=1e-6), 'Recorded multiplier should reflect penalty'
    # Reward after penalty should equal base_reward * 0.60 (within tolerance)
    assert penalized_reward < base_reward, 'Penalized reward must be lower than baseline'
    # Expect direct scaling from base reward by new multiplier (0.60)
    assert math.isclose(penalized_reward, base_reward * 0.60, rel_tol=1e-6), 'Penalized reward should scale with multiplier'

    # Restore previous penalty to avoid cross-test interference
    worm_manifest.permanent_penalties[3] = previous_penalty


if __name__ == '__main__':
    test_reward_multiplier_applied()
    print('Test passed: reward multiplier propagation')
