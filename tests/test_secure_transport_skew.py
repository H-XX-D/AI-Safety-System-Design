import time
import os

from communication.aura_secure_transport import TransportContext, pack_secure, unpack_secure, ReplayError


def _ctx():
    return TransportContext(
        sender_id=6,
        recipient_id=7,
        session_id=123,
        secret_key=bytes.fromhex('00112233445566778899aabbccddeeff00112233445566778899aabbccddeeff'),
        ed25519_private_hex=None,
        ed25519_public_hex=None,
    )


def test_unpack_rejects_future_dated_frames():
    ctx = _ctx()
    payload = b"hello"
    seq = 1
    future_ts = int(time.time() + 60)  # 60s in the future
    frame = pack_secure(payload, ctx=ctx, sequence=seq, timestamp=future_ts)
    try:
        unpack_secure(frame, ctx=ctx, expected_sequence=None, max_age_seconds=300, max_future_skew_seconds=15)
        assert False, "Expected ReplayError for future-dated frame"
    except ReplayError:
        pass


def test_unpack_rejects_stale_frames():
    ctx = _ctx()
    payload = b"hello"
    seq = 2
    stale_ts = int(time.time() - 3600)  # 1 hour ago
    frame = pack_secure(payload, ctx=ctx, sequence=seq, timestamp=stale_ts)
    try:
        unpack_secure(frame, ctx=ctx, expected_sequence=None, max_age_seconds=300, max_future_skew_seconds=15)
        assert False, "Expected ReplayError for stale frame"
    except ReplayError:
        pass

