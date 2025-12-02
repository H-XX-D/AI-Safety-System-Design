import pytest
try:
    from hypothesis import given, settings, strategies as st
except Exception:  # pragma: no cover
    pytest.skip("hypothesis not installed in active interpreter", allow_module_level=True)
from security.worm_guard import WormGuard
from communication.aura_bitpacked_extension import BitPackedCompressor
from communication.message_codec import MessageCodec, reset_replay_state


@given(st.lists(st.booleans(), min_size=10, max_size=60))
@settings(deadline=None, max_examples=25)
def test_guard_chain_invariant(event_pattern: list[bool]):
    # event_pattern True => call verify_worm, False => attempt version advance
    g = WormGuard()
    version = 0
    for flag in event_pattern:
        if flag:
            g.verify_worm()
        else:
            version += 1
            g.advance_version(version)
    assert g.verify_event_chain() is True


@given(st.integers(min_value=5, max_value=40))
@settings(deadline=None, max_examples=20)
def test_secure_frame_sequence_monotonic(n: int):
    reset_replay_state()
    compressor = BitPackedCompressor()
    codec = MessageCodec(replay_capacity=16)
    base = "System 1 approves proposal 042"
    frames = [compressor.compress_secure(base) for _ in range(n)]
    for i, frame in enumerate(frames):
        assert frame is not None
        _text, info = codec.decode(frame)
        assert info['method'] == 'BITPACKED_SECURE'
        assert info['crc_ok'] is True
        if i == 0:
            assert info['sequence_ok'] in (True, None)
        else:
            assert info['sequence_ok'] is True
        assert info['replay_detected'] is False

