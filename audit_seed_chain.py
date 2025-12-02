"""Audit Seed Chain Module
===========================

Provides deterministic hourly audit seed derivation and selection proof
structure. Production will replace simple SHA256 chaining with a VRF (e.g.,
Ed25519 + Ristretto group) to make selection unpredictability externally
verifiable.

Seed Derivation
---------------
Given previous seed S_{n-1}, derive S_n:
    S_n = SHA256( S_{n-1} || hour_epoch || nonce )
Where:
- S_{n-1}: 32-byte previous seed (hex accepted and normalized)
- hour_epoch: integer hour boundary (unix_timestamp // 3600)
- nonce: 32 random bytes produced at hour boundary (secrets.token_bytes(32))

Selection Proof
---------------
A record encapsulates the derived seed plus a deterministic target selection
(from a provided universe of candidate paths/artifacts). The proof hash ties
seed, previous seed, nonce, hour, and targets together. VRF output is a stub
that must be replaced in production.

Dev Notes
---------
- Falls back to env AUDIT_SEED_ROOT for an initial seed when convenience is
  desired; production must load from WORM.
- Targets selection is a simple modular index; production should expand to
  multi-target sampling with collision avoidance and weighting.
"""
from __future__ import annotations
import os
import time
import hashlib
import secrets
from dataclasses import dataclass, asdict
from typing import List, Sequence, Optional
from vrf_random import get_audit_target, verify_proof
from typing import Optional as _Optional
try:
    from vrf_ed25519 import get_vrf_target as _get_vrf_target_ed, verify_vrf as _verify_vrf_ed
except Exception:  # module may exist without deps; handle dynamically
    _get_vrf_target_ed = None  # type: ignore
    _verify_vrf_ed = None  # type: ignore

HEX_64 = 64


def _h(data: bytes) -> bytes:
    return hashlib.sha256(data).digest()


def _to_bytes(seed_hex: str) -> bytes:
    seed_hex = seed_hex.strip().lower()
    if len(seed_hex) != HEX_64:
        raise ValueError(f"Seed hex must be 64 chars (32 bytes), got {len(seed_hex)}")
    try:
        return bytes.fromhex(seed_hex)
    except ValueError:
        raise ValueError("Invalid hex for seed")


def compute_hour_epoch(ts: Optional[float] = None) -> int:
    """Return integer hour index for timestamp in UTC (unix_seconds // 3600).

    Use integer arithmetic to avoid float rounding at boundaries.
    """
    if ts is None:
        ts = time.time()
    return int(int(ts) // 3600)


def derive_seed(prev_seed_hex: str, hour_epoch: int, nonce_bytes: bytes) -> str:
    prev_seed = _to_bytes(prev_seed_hex)
    if len(nonce_bytes) != 32:
        raise ValueError("Nonce must be 32 bytes")
    hour_bytes = hour_epoch.to_bytes(8, 'big')
    seed = _h(prev_seed + hour_bytes + nonce_bytes)
    return seed.hex()


def random_nonce() -> bytes:
    return secrets.token_bytes(32)


def initial_seed_root() -> Optional[str]:
    """Dev convenience: read AUDIT_SEED_ROOT; production uses WORM manifest.
    Must be a 64-char hex string."""
    root = os.getenv('AUDIT_SEED_ROOT')
    if not root:
        return None
    root = root.strip().lower()
    if len(root) != HEX_64:
        return None
    try:
        bytes.fromhex(root)
    except ValueError:
        return None
    return root


def choose_targets(seed_hex: str, universe: Sequence[str], count: int = 1) -> List[str]:
    """Deterministic target selection.
    For now: pick 'count' items via modular stepping from an offset derived
    from seed. Future: weighted sampling, domain stratification.
    """
    if not universe:
        return []
    seed_int = int(seed_hex[:16], 16)  # use first 8 bytes for offset
    chosen: List[str] = []
    for i in range(count):
        idx = (seed_int + i) % len(universe)
        chosen.append(universe[idx])
    return chosen


def vrf_stub(seed_hex: str) -> str:
    """Deprecated placeholder VRF output; use vrf_target/proof instead."""
    return hashlib.sha256((seed_hex + "|vrf").encode()).hexdigest()


@dataclass
class AuditSeedRecord:
    index: int
    hour_epoch: int
    nonce_hex: str
    prev_seed_hex: str
    seed_hex: str
    targets: List[str]
    proof_hash: str
    vrf_output: str  # deprecated
    vrf_target: Optional[str] = None
    vrf_proof: Optional[str] = None
    vrf_public_key_hex: Optional[str] = None

    def to_dict(self) -> dict[str, object]:
        return asdict(self)


def build_record(prev_seed_hex: str, index: int, hour_epoch: int, nonce_bytes: bytes, universe: Sequence[str], target_count: int = 1) -> AuditSeedRecord:
    seed_hex = derive_seed(prev_seed_hex, hour_epoch, nonce_bytes)
    nonce_hex = nonce_bytes.hex()
    targets = choose_targets(seed_hex, universe, count=target_count)
    proof_material = f"{prev_seed_hex}|{nonce_hex}|{hour_epoch}|{','.join(targets)}"
    proof_hash = hashlib.sha256((seed_hex + '|' + proof_material).encode()).hexdigest()
    # Produce target/proof; prefer Ed25519 pseudo-VRF if configured
    vrf_pub_hex: _Optional[str] = None
    env_sk = os.getenv('AUDIT_VRF_PRIV')
    if env_sk and _get_vrf_target_ed is not None:
        try:
            sk_bytes = bytes.fromhex(env_sk.strip())
            t, p, pub = _get_vrf_target_ed(seed_hex, domain="audit", signing_key_bytes=sk_bytes)
            vrf_target, vrf_proof, vrf_pub_hex = t, p, pub.hex()
        except Exception:
            vrf_target, vrf_proof = get_audit_target(seed_hex, domain="audit")
    else:
        # fallback placeholder
        vrf_target, vrf_proof = get_audit_target(seed_hex, domain="audit")
    vrf_output = vrf_stub(seed_hex)
    return AuditSeedRecord(
        index=index,
        hour_epoch=hour_epoch,
        nonce_hex=nonce_hex,
        prev_seed_hex=prev_seed_hex,
        seed_hex=seed_hex,
        targets=list(targets),
        proof_hash=proof_hash,
        vrf_output=vrf_output,
        vrf_target=vrf_target,
        vrf_proof=vrf_proof,
        vrf_public_key_hex=vrf_pub_hex,
    )


def verify_record(record: AuditSeedRecord) -> bool:
    try:
        recomputed_seed = derive_seed(record.prev_seed_hex, record.hour_epoch, bytes.fromhex(record.nonce_hex))
    except Exception:
        return False
    if recomputed_seed != record.seed_hex:
        return False
    proof_material = f"{record.prev_seed_hex}|{record.nonce_hex}|{record.hour_epoch}|{','.join(record.targets)}"
    expected_proof_hash = hashlib.sha256((record.seed_hex + '|' + proof_material).encode()).hexdigest()
    if expected_proof_hash != record.proof_hash:
        return False
    # VRF checks: maintain backward-compatible stub AND verify target/proof
    if vrf_stub(record.seed_hex) != record.vrf_output:
        return False
    if record.vrf_target is None or record.vrf_proof is None:
        return False
    # Prefer ed25519 verification if public key present
    if record.vrf_public_key_hex and _verify_vrf_ed is not None:
        pub = bytes.fromhex(record.vrf_public_key_hex)
        if not _verify_vrf_ed(record.seed_hex, record.vrf_target, record.vrf_proof, domain="audit", public_key=pub):
            return False
    else:
        if not verify_proof(record.seed_hex, record.vrf_target, record.vrf_proof, domain="audit"):
            return False
    return True


__all__ = [
    'compute_hour_epoch',
    'derive_seed',
    'random_nonce',
    'initial_seed_root',
    'choose_targets',
    'vrf_stub',
    'AuditSeedRecord',
    'build_record',
    'verify_record'
]
