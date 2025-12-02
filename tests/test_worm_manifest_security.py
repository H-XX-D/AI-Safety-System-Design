import json
from pathlib import Path

from security.attestation import sign


def _write_manifest(path: Path, payload: dict, *, signed: bool = True) -> None:
    data = dict(payload)
    if signed:
        data['__signature'] = sign(json.dumps(payload, sort_keys=True).encode())
    path.write_text(json.dumps(data))


def _reset_state(monkeypatch):
    import security.worm_manifest

    monkeypatch.setattr(worm_manifest, '_manifest_cache', None)
    monkeypatch.setattr(worm_manifest, '_last_error', None)
    monkeypatch.setattr(worm_manifest, '_manifest_signature_verified', False)
    worm_manifest.disable_software_equivalence_mode()


def test_signed_manifest_required(monkeypatch, tmp_path):
    import security.worm_manifest

    payload = {
        'core_values_hash': 'a' * 64,
        'alignment_filter_hash': 'b' * 64,
    }
    manifest_path = tmp_path / 'signed_manifest.json'
    _write_manifest(manifest_path, payload, signed=True)

    _reset_state(monkeypatch)
    monkeypatch.delenv('CORE_VALUES_KNOWN_HASH', raising=False)
    monkeypatch.delenv('CORE_ALIGNMENT_FILTER_HASH', raising=False)
    monkeypatch.setenv('WORM_MOCK_MANIFEST', str(manifest_path))

    assert worm_manifest.get_expected_core_values_hash() == payload['core_values_hash']
    assert worm_manifest.get_expected_alignment_filter_hash() == payload['alignment_filter_hash']
    state = worm_manifest.describe_dev_state()
    assert state['manifest_signature_verified'] is True
    assert state['manifest_loaded'] is True


def test_unsigned_manifest_rejected(monkeypatch, tmp_path):
    import security.worm_manifest

    payload = {
        'core_values_hash': 'c' * 64,
        'alignment_filter_hash': 'd' * 64,
    }
    manifest_path = tmp_path / 'unsigned_manifest.json'
    _write_manifest(manifest_path, payload, signed=False)

    _reset_state(monkeypatch)
    monkeypatch.setenv('WORM_MOCK_MANIFEST', str(manifest_path))
    monkeypatch.delenv('CORE_VALUES_KNOWN_HASH', raising=False)
    monkeypatch.delenv('CORE_ALIGNMENT_FILTER_HASH', raising=False)

    assert worm_manifest.get_expected_core_values_hash() is None
    state = worm_manifest.describe_dev_state()
    assert state['manifest_signature_verified'] is False
    assert state['manifest_loaded'] is False
    assert state['using_env_fallback'] is False
