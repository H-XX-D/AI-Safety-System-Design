from communication.aura_bitpacked_extension import BitPackedCompressor
from communication.message_codec import MessageCodec, reset_replay_state


def test_sequence_wraparound_monotonic():
    reset_replay_state()
    codec = MessageCodec(replay_capacity=32)
    bp = BitPackedCompressor()
    base = "System 1 approves proposal 042"
    frames = []
    # Generate >256 secure frames to force wrap-around
    for _ in range(260):
        frame = bp.compress_secure(base)
        assert frame is not None
        frames.append(frame)
    # Decode sequentially and assert monotonicity and no replay flags on fresh stream
    for i, frame in enumerate(frames):
        text, info = codec.decode(frame)
        assert info['method'] == 'BITPACKED_SECURE'
        assert info['crc_ok'] is True
        if i == 0:
            assert info['sequence_ok'] in (True, None)
        else:
            assert info['sequence_ok'] is True
        assert info['replay_detected'] is False
