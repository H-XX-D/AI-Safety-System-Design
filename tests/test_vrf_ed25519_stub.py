import pytest
from vrf_ed25519 import generate_keypair, get_vrf_target, verify_vrf


def test_vrf_target_and_verify_roundtrip():
    sk, pk = generate_keypair()
    seed = 'ab'*32
    domain = 'audit'
    target, proof, public_key = get_vrf_target(seed, domain, sk)
    assert len(target) == 32
    assert isinstance(proof, str) and len(proof) > 10
    assert verify_vrf(seed, target, proof, domain, public_key) is True


def test_vrf_verify_failure_on_modified_target():
    sk, pk = generate_keypair()
    seed = 'cd'*32
    domain = 'audit'
    target, proof, public_key = get_vrf_target(seed, domain, sk)
    bad_target = '0'*32
    assert (bad_target != target) or target == '0'*32
    assert verify_vrf(seed, bad_target, proof, domain, public_key) is False
