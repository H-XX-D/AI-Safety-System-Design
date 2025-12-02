"""
Hardened AURA Transport

Implements integrity (HMAC), authenticity (optional Ed25519 signature),
freshness (sequence + timestamp), and context binding for compressed payloads.

Design aims to address the documented cryptographic gaps without forcing a
runtime dependency when signatures are not required.
"""
from __future__ import annotations

import hmac
import hashlib
import struct
import time
from dataclasses import dataclass
from typing import Optional, Tuple


@dataclass
class TransportContext:
    sender_id: int
    recipient_id: int
    session_id: int
    secret_key: bytes  # for HMAC
    # optional Ed25519 signing (private/public hex via PyNaCl if present)
    ed25519_private_hex: Optional[str] = None
    ed25519_public_hex: Optional[str] = None


class IntegrityError(Exception):
    pass


class AuthenticationError(Exception):
    pass


class ReplayError(Exception):
    pass


def _sign_ed25519(message: bytes, priv_hex: Optional[str]) -> Optional[bytes]:
    if not priv_hex:
        return None
    try:
        from nacl import signing  # type: ignore
        sk = signing.SigningKey(bytes.fromhex(priv_hex))
        sig = sk.sign(message).signature
        return sig
    except Exception:
        return None


def _verify_ed25519(message: bytes, signature: bytes, pub_hex: Optional[str]) -> bool:
    if not pub_hex:
        return False
    try:
        from nacl import signing  # type: ignore
        vk = signing.VerifyKey(bytes.fromhex(pub_hex))
        vk.verify(message, signature)
        return True
    except Exception:
        return False


def pack_secure(
    compressed: bytes,
    *,
    ctx: TransportContext,
    sequence: int,
    timestamp: Optional[int] = None,
) -> bytes:
    """Pack a secure frame around compressed data.

    Frame layout (variable signature):
      [sender_id:1][recipient_id:1][session:8][seq:8][ts:8][sig_len:1][sig][payload][hmac16]
    """
    ts = int(timestamp if timestamp is not None else time.time())
    header = struct.pack('>BBQQQ', ctx.sender_id & 0xFF, ctx.recipient_id & 0xFF, ctx.session_id, sequence, ts)
    msg_for_sig = header + compressed
    sig = _sign_ed25519(msg_for_sig, ctx.ed25519_private_hex) or b''
    sig_len = len(sig)
    if sig_len not in (0, 64):  # Ed25519 sized only
        sig = b''
        sig_len = 0
    frame_wo_mac = header + bytes([sig_len]) + sig + compressed
    mac = hmac.new(ctx.secret_key, frame_wo_mac, hashlib.sha256).digest()[:16]
    return frame_wo_mac + mac


def unpack_secure(
    frame: bytes,
    *,
    ctx: TransportContext,
    expected_sequence: Optional[int] = None,
    max_age_seconds: int = 300,
    max_future_skew_seconds: int = 15,
) -> Tuple[bytes, int, int]:
    """Unpack and verify secure frame.

    Returns (compressed, sequence, timestamp).
    Raises IntegrityError, AuthenticationError, ReplayError on failure.
    """
    if len(frame) < (1 + 1 + 8 + 8 + 8 + 1 + 16):
        raise IntegrityError('frame too short')
    off = 0
    sender_id, recipient_id, session_id, seq, ts = struct.unpack('>BBQQQ', frame[off:off+26]); off += 26
    sig_len = frame[off]; off += 1
    sig = frame[off:off+sig_len]; off += sig_len
    mac = frame[-16:]
    payload = frame[off:-16]

    # Verify HMAC first
    framed_wo_mac = frame[:-16]
    expected_mac = hmac.new(ctx.secret_key, framed_wo_mac, hashlib.sha256).digest()[:16]
    if not hmac.compare_digest(mac, expected_mac):
        raise IntegrityError('HMAC mismatch')

    # Verify context
    if sender_id != (ctx.sender_id & 0xFF):
        raise AuthenticationError('sender mismatch')
    if recipient_id != (ctx.recipient_id & 0xFF):
        raise AuthenticationError('recipient mismatch')
    if session_id != ctx.session_id:
        raise AuthenticationError('session mismatch')

    # Verify signature when provided/configured
    if sig_len:
        if not _verify_ed25519(frame[:26] + payload, sig, ctx.ed25519_public_hex):
            raise AuthenticationError('invalid signature')

    # Freshness checks
    if expected_sequence is not None and seq != expected_sequence:
        raise ReplayError('sequence mismatch')
    now = time.time()
    if max_age_seconds > 0:
        age = now - ts
        if age > max_age_seconds:
            raise ReplayError('stale frame')
    # Reject frames with timestamps too far in the future (clock skew abuse)
    if max_future_skew_seconds >= 0 and ts > (now + max_future_skew_seconds):
        raise ReplayError('future-dated frame')
    return payload, seq, ts
