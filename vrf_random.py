"""
vrf_random.py
--------------

Stable interface for verifiable audit randomness. This module ships a deterministic
placeholder so callers can integrate immediately. Swap the implementation later
for a real VRF or public randomness beacon without changing call sites.

Contract
- get_audit_target(seed: str, domain: str = "audit") -> tuple[target: str, proof: str]
- verify_proof(seed: str, target: str, proof: str, domain: str = "audit") -> bool

Properties (placeholder)
- Deterministic: target,proof repeat for same inputs
- Binding: change in seed or domain alters both values
- Verifiable: verify_proof returns True only for values produced by get_audit_target

Security note: This is NOT a cryptographic VRF. It uses SHA-256 over a salted
format to provide a stable interface only.
"""

from __future__ import annotations

import hashlib
from typing import Tuple

_PLACEHOLDER_SECRET = "vrf-placeholder-secret-v1"  # replace with HSM/VRF later


def _h(data: str) -> str:
    return hashlib.sha256(data.encode()).hexdigest()


def get_audit_target(seed: str, domain: str = "audit") -> Tuple[str, str]:
    """
    Produce a deterministic target and proof for a given seed.

    Args:
        seed: stringable entropy (e.g., block hash, timestamp bucket, etc.)
        domain: optional domain separation label (default: "audit")

    Returns:
        (target, proof) strings suitable for logging and external verification.
    """
    base = f"VRF|{domain}|{seed}|{_PLACEHOLDER_SECRET}"
    proof = _h(base)
    target = _h(f"{base}|target")[:16]  # short id for routing/selection
    return target, proof


def verify_proof(seed: str, target: str, proof: str, domain: str = "audit") -> bool:
    """
    Verify a (seed, target, proof) triple under this placeholder scheme.
    """
    expected_target, expected_proof = get_audit_target(seed, domain)
    return expected_target == target and expected_proof == proof
