import os
import json


def test_val_inspect_manifest_signers(tmp_path, monkeypatch):
    # Configure admin token and role
    monkeypatch.setenv('ADMIN_TOKEN', 't0k')

    # Build a manifest-style VAL response with two signatures, one valid
    payload = {
        'proposal_id': 'px1',
        'created_at': '2025-01-01T00:00:00Z',
        'proposal': {'proposal_id': 'px1'},
        'test_results': {'ok': True},
        'schema': 'val_package_v1',
    }
    content_hash = __import__('hashlib').sha256(json.dumps(payload, sort_keys=True).encode('utf-8')).hexdigest()
    secret = 'valsecret'
    monkeypatch.setenv('VAL_SIGNING_SECRET', secret)
    from research.human_review import sign_human_decision

    sig1_msg = {
        'reviewer_id': 101,
        'proposal_id': payload['proposal_id'],
        'approved': True,
        'timestamp': '2025-01-01T01:00:00Z',
        'content_hash': content_hash,
    }
    sig2_msg = {
        'reviewer_id': 202,
        'proposal_id': payload['proposal_id'],
        'approved': True,
        'timestamp': '2025-01-01T02:00:00Z',
        'content_hash': content_hash,
    }
    good_sig = sign_human_decision(sig1_msg, secret)
    bad_sig = '00' * 32

    doc = {
        'manifest': {
            'proposal_id': payload['proposal_id'],
            'created_at': payload['created_at'],
            'content_hash': content_hash,
            'required_signers': 2,
            'signatures': [
                {**sig1_msg, 'signature': good_sig, 'notes': 'ok'},
                {**sig2_msg, 'signature': bad_sig, 'notes': 'bad'},
            ],
        },
        'payload': payload,
    }
    f = tmp_path / 'VAL_RESP.json'
    f.write_text(json.dumps(doc))

    # Import app and use test client
    import pytest
    pytest.importorskip('flask')
    from ui.app import app
    client = app.test_client()
    headers = {
        'Authorization': 'Bearer t0k',
        'X-Admin-Role': 'safety_officer',
        'Content-Type': 'application/json',
    }
    resp = client.post('/api/admin/val/inspect', data=json.dumps({'path': str(f)}), headers=headers)
    assert resp.status_code == 200
    data = resp.get_json()
    assert data['format'] == 'manifest'
    assert data['signatures'] == 2
    assert data['required_signers'] == 2
    # Only one of the signatures should validate
    valid_flags = [d.get('valid') for d in data.get('signatures_detail', [])]
    assert valid_flags.count(True) == 1
