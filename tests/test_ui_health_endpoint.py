def test_ui_health_endpoint(monkeypatch):
    import pytest
    pytest.importorskip('flask')
    from ui.app import app
    client = app.test_client()
    resp = client.get('/api/health')
    assert resp.status_code == 200
    data = resp.get_json()
    assert 'ok' in data and 'halted' in data and 'worm' in data
