import importlib
import pytest
from _pytest.monkeypatch import MonkeyPatch


def test_alignment_filter_code_hash_verification_success(monkeypatch: MonkeyPatch):
    mod = importlib.import_module('bulletproof_alignment_filter')
    expected = mod.BulletproofAlignmentFilter.get_own_code_hash()
    import security.worm_manifest
    worm_manifest.enable_software_equivalence_mode(justification='test')
    monkeypatch.setenv('CORE_ALIGNMENT_FILTER_HASH', expected)
    reporter = mod.CentralReporter(enable_network=False)
    mod.BulletproofAlignmentFilter(reporter)  # Should not raise


def test_alignment_filter_code_hash_verification_mismatch(monkeypatch: MonkeyPatch):
    mod = importlib.import_module('bulletproof_alignment_filter')
    import security.worm_manifest
    worm_manifest.enable_software_equivalence_mode(justification='test')
    monkeypatch.setenv('CORE_ALIGNMENT_FILTER_HASH', 'deadbeef')
    reporter = mod.CentralReporter(enable_network=False)
    with pytest.raises(ValueError):
        mod.BulletproofAlignmentFilter(reporter)
