from pathlib import Path
import dataclasses
import pytest
import time
from security.audit_seed_chain import (
    compute_hour_epoch,
    derive_seed,
    random_nonce,
    initial_seed_root,
    choose_targets,
    build_record,
    verify_record,
)


def test_compute_hour_epoch_monotonic():
    # Two timestamps constructed explicitly inside the same UTC hour.
    now = time.time()
    hour_epoch = compute_hour_epoch(now)
    hour_start = hour_epoch * 3600
    t1 = hour_start + 123  # 2m3s into the hour
    t2 = hour_start + 3500  # 58m20s into the same hour (<3600 boundary)
    assert compute_hour_epoch(t1) == compute_hour_epoch(t2)


def test_derive_seed_deterministic():
    prev_seed = '00' * 32
    hour = compute_hour_epoch(1730956800.0)
    nonce = bytes.fromhex('11' * 32)
    s1 = derive_seed(prev_seed, hour, nonce)
    s2 = derive_seed(prev_seed, hour, nonce)
    assert s1 == s2


def test_choose_targets_deterministic():
    seed_hex = 'aa' * 32
    universe = [f"file_{i}" for i in range(10)]
    picked1 = choose_targets(seed_hex, universe, count=3)
    picked2 = choose_targets(seed_hex, universe, count=3)
    assert picked1 == picked2
    assert len(picked1) == 3


def test_build_and_verify_record_roundtrip(tmp_path: Path):
    prev_seed = 'ab' * 32
    hour = compute_hour_epoch(1730956800.0)
    nonce = random_nonce()
    universe = ["a.txt", "b.txt", "c.txt"]
    rec = build_record(prev_seed, index=5, hour_epoch=hour, nonce_bytes=nonce, universe=universe, target_count=2)
    assert verify_record(rec) is True

    # Corrupting any field should fail
    bad = dataclasses.replace(rec, targets=["z.txt"] + rec.targets[1:])
    assert verify_record(bad) is False


def test_initial_seed_root_env(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setenv('AUDIT_SEED_ROOT', '00' * 32)
    assert initial_seed_root() == '00' * 32

    monkeypatch.setenv('AUDIT_SEED_ROOT', 'deadbeef')
    assert initial_seed_root() is None
