import json


def test_secure_transport_self_check(monkeypatch):
    import pytest
    pytest.importorskip('flask')
    monkeypatch.setenv('ADMIN_TOKEN', 't0k')
    # Ensure development config (secure transport enabled by default)
    monkeypatch.setenv('APP_ENV', 'development')
    from ui.app import app
    client = app.test_client()
    headers = {
        'Authorization': 'Bearer t0k',
        'X-Admin-Role': 'safety_officer',
        'X-Requested-With': 'XMLHttpRequest',
    }
    resp = client.post('/api/admin/secure-transport/self-check', headers=headers)
    assert resp.status_code == 200
    data = resp.get_json()
    assert data.get('ok') in (True, False)
    # When secure transport is enabled in development, expect ok True
    assert data.get('ok') is True

