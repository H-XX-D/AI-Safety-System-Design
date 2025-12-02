import os
import importlib


def test_worm_manifest_prefer_manifest_over_env(monkeypatch):
    # Ensure environment fallback is NOT trusted unless software equivalence mode is enabled
    monkeypatch.delenv('CORE_VALUES_KNOWN_HASH', raising=False)
    worm_manifest = importlib.import_module('worm_manifest')
    # Clear any cached manifest from other tests
    worm_manifest._manifest_cache = None
    worm_manifest._manifest_signature_verified = False
    worm_manifest.disable_software_equivalence_mode()
    assert not worm_manifest.is_worm_verified()

    # Even if env var is present, without software mode it should not verify
    monkeypatch.setenv('CORE_VALUES_KNOWN_HASH', 'a' * 64)
    assert not worm_manifest.is_worm_verified()

    # Enable software equivalence; now env fallback should be trusted for dev/test
    worm_manifest.enable_software_equivalence_mode(justification='test')
    assert worm_manifest.is_worm_verified()
    worm_manifest.disable_software_equivalence_mode()
