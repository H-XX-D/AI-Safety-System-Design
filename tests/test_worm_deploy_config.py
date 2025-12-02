import json
import os
import tempfile
from datetime import datetime
from typing import Dict

import pytest

from core_values import CoreValues
from memory_merkle import MemoryStorage
from orchestrator import Orchestrator


def _make_proposal(proposal_id: str = 'deploy-001') -> Dict[str, object]:
    return {
        'proposal_id': proposal_id,
        'proposer_id': 1,
        'title': 'Test deployment',
        'motivation': 'Test',
        'expected_benefits': 'Validate WORM enforcement',
        'identified_risks': [],
        'admitted_uncertainties': [],
        'rollback_plan': 'Revert',
        'confidence_level': 0.5,
        'changes': {'code': 'def noop(): return True', 'description': 'noop'},
        'timestamp': datetime.now().isoformat(),
    }


def test_deploy_blocked_in_strict_mode(monkeypatch, tmp_path):
    storage = MemoryStorage(system_id=0, private_key='test-key', include_entry_hash_in_metadata=True)
    orchestrator = Orchestrator(storage)
    # Strict mode means WORM verification is required
    orchestrator._config['worm']['guard_mode'] = 'strict'
    # Ensure no WORM manifest present and no software equivalence
    monkeypatch.delenv('WORM_MOCK_MANIFEST', raising=False)
    try:
        from worm_manifest import disable_software_equivalence_mode

        disable_software_equivalence_mode()
    except Exception:
        pass

    # Ensure the USB path used in the test is writable for this environment
    monkeypatch.setenv('WORM_USB_PATH', str(tmp_path))
    prop = _make_proposal()
    orchestrator.handle_improvement_proposal(prop)
    # Submit peer reviews to move the proposal forward
    for reviewer_id in range(2, 6):
        review = {
            'reviewer_id': reviewer_id,
            'vote': 'approve',
            'confidence': 'high',
            'risk': 'low',
            'timestamp': datetime.now().isoformat(),
            'justification': 'ok',
        }
        orchestrator.record_peer_review(prop['proposal_id'], review)

    # Reaffirm approval which triggers deploy attempt; should be blocked by worm guard
    assert orchestrator.reaffirm_approval(prop['proposal_id'])
    assert orchestrator.active_proposals[prop['proposal_id']]['status'] != 'deployed'


def test_deploy_allowed_with_signed_manifest(monkeypatch):
    storage = MemoryStorage(system_id=0, private_key='test-key', include_entry_hash_in_metadata=True)
    orchestrator = Orchestrator(storage)
    orchestrator._config['worm']['guard_mode'] = 'strict'
    orchestrator._config['worm']['require_manifest_signature'] = True
    # Build a temporary signed manifest with correct hashes
    import attestation
    import worm_manifest
    from bulletproof_alignment_filter import BulletproofAlignmentFilter

    cv_hash = CoreValues.compute_hash()
    align_hash = BulletproofAlignmentFilter.get_own_code_hash()
    data = {'core_values_hash': cv_hash, 'alignment_filter_hash': align_hash}
    canonical = json.dumps(data, sort_keys=True).encode()
    signature = attestation.sign(canonical)
    data['__signature__'] = signature
    fd, path = tempfile.mkstemp(prefix='worm_manifest_', suffix='.json')
    with os.fdopen(fd, 'w') as f:
        json.dump(data, f)
    monkeypatch.setenv('WORM_MOCK_MANIFEST', path)
    # Ensure software equivalence is disabled so we rely on manifest
    worm_manifest.disable_software_equivalence_mode()

    prop = _make_proposal('deploy-002')
    orchestrator.handle_improvement_proposal(prop)
    for reviewer_id in range(2, 6):
        review = {'reviewer_id': reviewer_id, 'vote': 'approve', 'confidence': 'high', 'risk': 'low', 'timestamp': datetime.now().isoformat(), 'justification': 'ok'}
        orchestrator.record_peer_review(prop['proposal_id'], review)

    # Now finalize and attempt deploy; should succeed with signed manifest
    assert orchestrator.reaffirm_approval(prop['proposal_id'])
    assert orchestrator.active_proposals[prop['proposal_id']]['status'] == 'deployed'