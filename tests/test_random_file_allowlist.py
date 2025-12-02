def test_random_file_download_allowlist(monkeypatch):
    import pytest
    pytest.importorskip('flask')
    from ui.app import app
    client = app.test_client()
    # Attempt to fetch a disallowed path
    resp = client.get('/api/random-file/download?file_path=/etc/hosts')
    assert resp.status_code in (400, 403, 404)

