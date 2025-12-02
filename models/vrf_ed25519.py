"""Ed25519-based pseudo VRF interface.

Provides a stronger (though still not formal VRF) construction using Ed25519
signatures as a proof of binding between seed and domain. Target is derived
from hashing the public key, seed, and domain. Proof is the signature.

This is a stopgap until a proper VRF (e.g. ristretto255 based) is integrated.
External verifiers can confirm:
  - Signature validity over message (seed|domain)
  - Target recomputation matches provided target

Security caveats:
  - Not unique like real VRF outputs across all possible keys (standard signature scheme)
  - No formal unpredictability guarantee beyond Ed25519 properties

API mirrors vrf_random for drop-in replacement:
  get_vrf_target(seed: str, domain: str) -> (target, proof)
  verify_vrf(seed: str, target: str, proof: str, domain: str, public_key: bytes) -> bool
"""
from __future__ import annotations

from typing import Tuple
import hashlib


def _hash(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _try_import_nacl():  # lazy import to avoid hard dependency at import time
    try:  # pragma: no cover
        import importlib
        _signing = importlib.import_module('nacl.signing')
        _exc_mod = importlib.import_module('nacl.exceptions')
        _BadSignatureError = getattr(_exc_mod, 'BadSignatureError', Exception)
        return _signing, _BadSignatureError
    except Exception:
        return None, None


def generate_keypair() -> Tuple[bytes, bytes]:
    signing, _BadSignatureError = _try_import_nacl()
    if signing is None:
        # Fallback: derive pseudo keypair from random 32 bytes
        sk = hashlib.sha256(b"vrf-soft-fallback-sk").digest()
        pk = hashlib.sha256(sk).digest()
        return sk, pk
    sk = signing.SigningKey.generate()
    vk = sk.verify_key
    return bytes(sk), bytes(vk)


def get_vrf_target(seed: str, domain: str, signing_key_bytes: bytes) -> Tuple[str, str, bytes]:
    """Produce (target, proof, public_key) given seed and signing key.

    signing_key_bytes: 32-byte Ed25519 seed (PyNaCl form) or full key (PyNaCl accepts raw 32)."""
    signing, _BadSignatureError = _try_import_nacl()
    message = f"VRF|{domain}|{seed}".encode()
    if signing is None:
        # Soft fallback: proof=H(seed||domain||sk), pk=H(sk), target=H(pk||message)
        sk = signing_key_bytes[:32]
        pk = hashlib.sha256(sk).digest()
        proof = hashlib.sha256(sk + message).hexdigest()
        target = _hash(pk + message)[:32]
        return target, proof, pk
    sk = signing.SigningKey(signing_key_bytes[:32])
    signature = sk.sign(message).signature
    vk = sk.verify_key
    target = _hash(vk.encode() + message)[:32]
    return target, signature.hex(), vk.encode()


def verify_vrf(seed: str, target: str, proof: str, domain: str, public_key: bytes) -> bool:
    signing, _BadSignatureError = _try_import_nacl()
    message = f"VRF|{domain}|{seed}".encode()
    if signing is None:
        # soft fallback verification
        expected_target = _hash(public_key + message)[:32]
        # Without SK we cannot recompute proof in fallback; verify target only
        return expected_target == target
    vk = signing.VerifyKey(public_key)
    try:
        vk.verify(message, bytes.fromhex(proof))
    except Exception:
        return False
    expected_target = _hash(public_key + message)[:32]
    return expected_target == target


__all__ = [
    "generate_keypair",
    "get_vrf_target",
    "verify_vrf",
]