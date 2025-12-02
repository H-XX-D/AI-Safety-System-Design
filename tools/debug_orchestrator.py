from datetime import datetime
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from utilities.core_values import CoreValues
from infrastructure.memory_merkle import MemoryStorage
from core.orchestrator import Orchestrator
import security.worm_manifest


def run_debug() -> None:
    os.environ['CORE_VALUES_KNOWN_HASH'] = CoreValues.compute_hash()
    if hasattr(worm_manifest, '_manifest_cache'):
        worm_manifest._manifest_cache = None

    storage = MemoryStorage(system_id=0, private_key='test-key', include_entry_hash_in_metadata=True)
    orchestrator = Orchestrator(storage)
    orchestrator.environment_manager.max_memory_kb = 256 * 1024
    orchestrator.environment_manager.cpu_time_sec = 5

    proposal = {
        'proposal_id': 'debug-001',
        'proposer_id': 1,
        'title': 'Optimize processing pipeline',
        'motivation': 'Improve throughput with smarter caching and batching.',
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

    orchestrator.handle_improvement_proposal(proposal)
    for reviewer_id in range(2, 6):
        orchestrator.record_peer_review(proposal['proposal_id'], {
            'reviewer_id': reviewer_id,
            'vote': 'approve',
            'confidence': 'high',
            'risk': 'low',
            'timestamp': datetime.now().isoformat(),
            'justification': 'Looks good',
        })

    results = orchestrator.active_proposals[proposal['proposal_id']]['test_results']
    from pprint import pprint
    pprint(results)


if __name__ == '__main__':
    run_debug()
