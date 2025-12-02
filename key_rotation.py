"""Key rotation utilities for config signing (Ed25519 / PyNaCl).

Provides simple file-based rotation: a directory with active key symlink
and versioned keypairs. Intended for demonstration / tests only.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Optional, Tuple
import os
import time
from binascii import hexlify

try:
    from nacl.signing import SigningKey
except Exception:  # pragma: no cover
    SigningKey = None  # type: ignore


@dataclass
class KeyVersion:
    version: str
    public_hex: str
    private_hex: str  # WARNING: for demo only; do not persist raw private key hex in production
    created_ts: float


def generate_keypair() -> Tuple[str, str]:
    if SigningKey is None:  # pragma: no cover
        raise RuntimeError("PyNaCl not available for key generation")
    sk = SigningKey.generate()
    pk = sk.verify_key
    return pk.encode().hex(), sk.encode().hex()


def rotate_key(storage_dir: str, *, label: Optional[str] = None) -> KeyVersion:
    """Generate a new keypair and record metadata.

    Creates files:
      storage_dir/keys/{version}.pub
      storage_dir/keys/{version}.priv
    And updates storage_dir/active_pubkey to point at the latest .pub
    Returns KeyVersion metadata.
    """
    os.makedirs(os.path.join(storage_dir, "keys"), exist_ok=True)
    version = label or time.strftime("%Y%m%d%H%M%S")
    pub, priv = generate_keypair()
    pub_path = os.path.join(storage_dir, "keys", f"{version}.pub")
    priv_path = os.path.join(storage_dir, "keys", f"{version}.priv")
    with open(pub_path, "w") as f:
        f.write(pub)
    with open(priv_path, "w") as f:
        f.write(priv)
    active_link = os.path.join(storage_dir, "active_pubkey")
    try:
        if os.path.islink(active_link) or os.path.exists(active_link):
            os.remove(active_link)
        os.symlink(pub_path, active_link)
    except OSError:
        # Fallback: copy
        with open(active_link, "w") as f:
            f.write(pub)
    return KeyVersion(version=version, public_hex=pub, private_hex=priv, created_ts=time.time())


def sign_config(config_text: str, private_hex: str) -> str:
    if SigningKey is None:  # pragma: no cover
        raise RuntimeError("PyNaCl not available for signing")
    sk = SigningKey(bytes.fromhex(private_hex))
    sig = sk.sign(config_text.encode("utf-8")).signature
    return hexlify(sig).decode()
