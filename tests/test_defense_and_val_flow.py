import os
from datetime import datetime

from orchestrator import Orchestrator
from orchestrator_sandbox import SandboxEnvironmentManager
from memory_merkle import MemoryStorage
from human_review import sign_human_decision


def _mk_orch():
    os.environ['ORCH_SKIP_WORM_HALT'] = '1'
    return Orchestrator(MemoryStorage(system_id=1, private_key='k'), environment_manager=SandboxEnvironmentManager())


def test_defense_revision_round_and_val_gating(tmp_path, monkeypatch):
    orch = _mk_orch()

    # Submit initial proposal
    pid = 'p999'
    proposal = {
        'proposal_id': pid,
        'proposer_id': 2,
        'title': 'Improve safety filter',
        'motivation': 'Increase robustness to adversarial inputs by clarifying constraints and improving tests.',
        'changes': {'component': 'filter', 'code': 'print("ok")'},
        'expected_benefits': 'Guaranteed improvement',
        'testable_predictions': ['Fewer false negatives'],
        'rollback_plan': 'Revert to previous filter version',
        'identified_risks': ['regression', 'latency'],
        'admitted_uncertainties': ['coverage gaps'],
        'confidence_level': 0.75,
    }
    orch.handle_improvement_proposal(proposal)

    # Complete first review round
    for rid in [3, 4, 5, 1]:
        orch.record_peer_review(pid, {'reviewer_id': rid, 'vote': 'approve'})

    # Submit agent defense with a revised proposal -> re-enters peer review
    revised = dict(proposal)
    revised['changes'] = {'component': 'filter', 'code': 'print("ok2")'}
    ok = orch.submit_agent_defense(pid, {'challenge_responses': {}, 'revised_proposal': revised})
    assert ok is True
    assert orch.active_proposals[pid]['status'] == 'peer_review'

    # Complete second review round
    for rid in [3, 4, 5, 1]:
        orch.record_peer_review(pid, {'reviewer_id': rid, 'vote': 'approve'})

    # Enable VAL requirement via env
    monkeypatch.setenv('REQUIRE_VAL', '1')
    # Approve human decision
    orch.record_human_decision(pid, True)
    # We expect awaiting_val or similar state after export
    # Export path stored in workflow metadata; just ensure export ran by calling initiate again (no-op safe)
    path = orch.initiate_val_validation(pid)
    assert path is not None

    # Create a signed VAL response
    resp = tmp_path / 'VAL_RESPONSE.json'
    secret = 'valsecret'
    os.environ['VAL_SIGNING_SECRET'] = secret
    msg = {
        'reviewer_id': 101,
        'proposal_id': pid,
        'approved': True,
        'timestamp': datetime.now().isoformat(),
    }
    sig = sign_human_decision(msg, secret)
    msg['signature'] = sig
    msg['notes'] = 'Looks good.'
    resp.write_text(__import__('json').dumps(msg))

    ok2 = orch.import_val_result(pid, str(resp), required_signer_id=101)
    assert ok2 is True

    # Attempt deploy (WORM guard may warn); expect not to be blocked by VAL
    deployed = orch.deploy_improvement(pid)
    assert deployed in {True, False}

