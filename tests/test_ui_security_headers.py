import json


def test_ui_security_headers_present(monkeypatch):
    import pytest
    pytest.importorskip('flask')
    # Force production-like CSP settings (no CDNs) for the test
    monkeypatch.setenv('APP_ENV', 'production')
    from ui.app import app
    client = app.test_client()
    resp = client.get('/')
    # Basic headers should be present
    assert 'Content-Security-Policy' in resp.headers
    assert 'X-Content-Type-Options' in resp.headers
    assert resp.headers.get('X-Frame-Options') == 'DENY'
    assert resp.headers.get('Referrer-Policy') == 'no-referrer'

