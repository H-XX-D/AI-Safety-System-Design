import json


def test_proposal_detail_includes_deception_analysis(monkeypatch):
    import pytest
    pytest.importorskip('flask')
    from ui.app import app
    client = app.test_client()

    # Fetch proposals list; if empty, skip
    resp = client.get('/api/proposals/all')
    assert resp.status_code == 200
    proposals = resp.get_json()
    if not proposals:
        pytest.skip('no proposals available in test environment')

    pid = proposals[0].get('id') or proposals[0].get('proposal_id')
    assert pid, 'proposal lacks id'

    detail = client.get(f'/api/proposals/{pid}')
    assert detail.status_code == 200
    data = detail.get_json()
    # Surface deception_analysis block
    assert 'deception_analysis' in data
    assert isinstance(data.get('deception_analysis'), dict)


def test_collusion_attempt_detail_includes_similar_pairs():
    import pytest
    pytest.importorskip('flask')
    from ui.app import app
    client = app.test_client()

    # Ensure sample data present
    list_resp = client.get('/api/collusion/attempts')
    assert list_resp.status_code == 200
    # Try known sample ids first
    for attempt_id in (1, 3):
        resp = client.get(f'/api/collusion/attempts/{attempt_id}')
        if resp.status_code != 200:
            continue
        payload = resp.get_json()
        assert payload.get('success') is True
        attempt = payload.get('attempt') or {}
        # similar_pairs should be present for our seeded samples
        assert 'similar_pairs' in attempt
        assert isinstance(attempt['similar_pairs'], list)
        break
    else:
        pytest.skip('sample collusion data not available')

