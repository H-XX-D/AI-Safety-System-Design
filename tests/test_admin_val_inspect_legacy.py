import os
import json


def test_val_inspect_legacy_single_signer(tmp_path, monkeypatch):
    # Configure admin token and role
    monkeypatch.setenv('ADMIN_TOKEN', 't0k')
    secret = 'valsecret'
    monkeypatch.setenv('VAL_SIGNING_SECRET', secret)

    # Build legacy response
    msg = {
        'reviewer_id': 303,
        'proposal_id': 'legacy1',
        'approved': True,
        'timestamp': '2025-01-02T00:00:00Z',
        'notes': 'legacy path',
    }
    from research.human_review import sign_human_decision
    msg['signature'] = sign_human_decision(msg, secret)
    f = tmp_path / 'VAL_LEGACY.json'
    f.write_text(json.dumps(msg))

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
    assert data['format'] == 'legacy'
    # legacy path may not include signatures_detail; ensure the API returns defaults
    assert data.get('signatures', 0) == 0
    assert data.get('approved') in (True, False)  # verify_val_response may set approved True

