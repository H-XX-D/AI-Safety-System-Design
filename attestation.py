"""
attestation.py
---------------

Lightweight signature abstraction for manifests / critical events.
Currently uses HMAC-SHA256 with a shared secret; replace with Ed25519 + PQC hybrid later.

Contract:
    sign(data: bytes) -> str (hex signature)
    verify(data: bytes, signature: str) -> bool

Design goals:
    - Simple drop-in now
    - Clear TODO markers for future upgrade
    - Deterministic and side-effect free
"""

from __future__ import annotations

import hmac
import hashlib
from typing import Optional

_SECRET = b"attestation-shared-secret-v1"  # TODO: replace with key management


def sign(data: bytes, secret: Optional[bytes] = None) -> str:
    key = secret if secret is not None else _SECRET
    return hmac.new(key, data, hashlib.sha256).hexdigest()


def verify(data: bytes, signature: str, secret: Optional[bytes] = None) -> bool:
    key = secret if secret is not None else _SECRET
    expected = hmac.new(key, data, hashlib.sha256).hexdigest()
    # constant-time compare
    return hmac.compare_digest(expected, signature)


__all__ = ["sign", "verify"]
