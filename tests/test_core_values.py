import os
import importlib
import pytest


def test_core_values_hash_verification_missing_env(monkeypatch):
    # Ensure env var not set
    monkeypatch.delenv('CORE_VALUES_KNOWN_HASH', raising=False)
    cv = importlib.import_module('core_values')
    cv.CoreValues.KNOWN_GOOD_HASH = None
    with pytest.raises(ValueError):
        cv.CoreValues.verify_immutability()


def test_core_values_hash_verification_success(monkeypatch):
    import worm_manifest
    worm_manifest.enable_software_equivalence_mode(justification='test')
    cv = importlib.import_module('core_values')
    expected = cv.CoreValues.compute_hash()
    monkeypatch.setenv('CORE_VALUES_KNOWN_HASH', expected)
    assert cv.CoreValues.verify_immutability() is True
    worm_manifest.disable_software_equivalence_mode()
