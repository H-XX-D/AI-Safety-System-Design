import json


def test_admin_requires_ajax_header(tmp_path, monkeypatch):
    import pytest
    pytest.importorskip('flask')
    # Use inspect endpoint (doesn't need orchestrator)
    monkeypatch.setenv('ADMIN_TOKEN', 't0k')
    from ui.app import app
    client = app.test_client()
    # Missing X-Requested-With
    headers = {
        'Authorization': 'Bearer t0k',
        'X-Admin-Role': 'safety_officer',
        'Content-Type': 'application/json',
    }
    resp = client.post('/api/admin/val/inspect', data=json.dumps({'path': str(tmp_path / 'none.json')}), headers=headers)
    assert resp.status_code == 400
    # With X-Requested-With
    headers['X-Requested-With'] = 'XMLHttpRequest'
    resp2 = client.post('/api/admin/val/inspect', data=json.dumps({'path': str(tmp_path / 'none.json')}), headers=headers)
    # Now auth passes and we get path required or not found error (400 or 404)
    assert resp2.status_code in (400, 404)


def test_admin_validation_proposal_id(monkeypatch):
    import pytest
    pytest.importorskip('flask')
    monkeypatch.setenv('ADMIN_TOKEN', 't0k')
    from ui.app import app
    client = app.test_client()
    headers = {
        'Authorization': 'Bearer t0k',
        'X-Admin-Role': 'safety_officer',
        'X-Requested-With': 'XMLHttpRequest',
        'Content-Type': 'application/json',
    }
    # Invalid proposal_id with spaces
    bad = client.post('/api/admin/val/export', data=json.dumps({'proposal_id': 'bad id'}), headers=headers)
    assert bad.status_code == 400
    # Valid proposal_id
    ok = client.post('/api/admin/val/export', data=json.dumps({'proposal_id': 'p123_ok'}), headers=headers)
    # Orchestrator may not be enabled; expect 501 or 200 depending on env
    assert ok.status_code in (200, 501)
