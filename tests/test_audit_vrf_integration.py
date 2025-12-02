import dataclasses
import os
from security.audit_seed_chain import build_record, verify_record, compute_hour_epoch, random_nonce


def test_audit_seed_record_with_ed25519_vrf(monkeypatch):
    # Provide a deterministic private key for test
    sk_hex = '11'*32
    monkeypatch.setenv('AUDIT_VRF_PRIV', sk_hex)
    prev_seed = 'aa'*32
    hour = compute_hour_epoch(1730956800.0)
    nonce = random_nonce()
    universe = ['x','y','z']
    rec = build_record(prev_seed, index=1, hour_epoch=hour, nonce_bytes=nonce, universe=universe, target_count=1)
    assert rec.vrf_public_key_hex is not None
    assert verify_record(rec) is True

    # Tamper target: should fail (checked in both fallback and ed25519 modes)
    vrf_len = len(rec.vrf_target) if rec.vrf_target is not None else 32
    bad = dataclasses.replace(rec, vrf_target='0' * vrf_len)
    assert verify_record(bad) is False


def test_audit_seed_record_without_env(monkeypatch):
    # Ensure fallback still works without env var
    monkeypatch.delenv('AUDIT_VRF_PRIV', raising=False)
    prev_seed = 'bb'*32
    hour = compute_hour_epoch(1730956800.0)
    nonce = random_nonce()
    universe = ['m','n','o']
    rec = build_record(prev_seed, index=2, hour_epoch=hour, nonce_bytes=nonce, universe=universe, target_count=1)
    assert rec.vrf_public_key_hex is None
    assert verify_record(rec) is True
