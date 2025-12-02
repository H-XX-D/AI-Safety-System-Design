import hashlib
import json
from security.worm_guard import get_guard, WormGuard


def test_basic_verification_pass(monkeypatch):
    # Patch expected hash functions to simulate presence
    import security.worm_manifest
    worm_manifest.enable_software_equivalence_mode(justification='test')
    monkeypatch.setenv('CORE_VALUES_KNOWN_HASH', 'a'*64)
    monkeypatch.setenv('CORE_ALIGNMENT_FILTER_HASH', 'b'*64)
    g = get_guard()
    allowed, reason = g.decision_point()
    assert allowed, reason
    st = g.status()
    assert st['fail_count'] == 0
    assert not st['soft_tamper']


def test_fail_escalation(monkeypatch):
    # Remove hashes to force failure
    import security.worm_manifest
    # Ensure any previous manifest is cleared so tests remain isolated
    worm_manifest._manifest_cache = None
    worm_manifest._manifest_signature_verified = False
    worm_manifest.disable_software_equivalence_mode()
    monkeypatch.delenv('CORE_VALUES_KNOWN_HASH', raising=False)
    monkeypatch.delenv('CORE_ALIGNMENT_FILTER_HASH', raising=False)
    # Fresh guard (avoid shared state) by constructing directly
    g = WormGuard()
    for _ in range(g.max_failures_soft):
        allowed, reason = g.decision_point()
        assert not allowed
    assert g.status()['soft_tamper']
    # Further attempts remain blocked
    allowed, reason = g.decision_point()
    assert not allowed and reason in ('soft_tamper_lockout', 'worm_verification_failed')


def test_audit_chain_integrity(monkeypatch):
    import security.worm_manifest
    worm_manifest.enable_software_equivalence_mode(justification='test')
    monkeypatch.setenv('CORE_VALUES_KNOWN_HASH', 'c'*64)
    monkeypatch.setenv('CORE_ALIGNMENT_FILTER_HASH', 'd'*64)
    g = WormGuard()
    for i in range(3):
        ok = g.verify_worm()
        assert ok
    chain = g.export_audit_chain()
    for ev in chain:
        recomputed = hashlib.sha256((ev['hash_prev'] + json.dumps({'kind': ev['kind'], 'detail': ev['detail'], 'ts': ev['ts']}, sort_keys=True)).encode()).hexdigest()
        assert recomputed == ev['hash_event']
    assert chain[-1]['hash_event'] == g.status()['last_event_hash']


def test_version_advance_and_rollback(monkeypatch):
    import security.worm_manifest
    worm_manifest.enable_software_equivalence_mode(justification='test')
    monkeypatch.setenv('CORE_VALUES_KNOWN_HASH', 'e'*64)
    monkeypatch.setenv('CORE_ALIGNMENT_FILTER_HASH', 'f'*64)
    g = WormGuard()
    assert g.advance_version(1)
    assert g.advance_version(2)
    assert not g.advance_version(2)  # rollback attempt (not greater)
    assert g.status()['soft_tamper']
