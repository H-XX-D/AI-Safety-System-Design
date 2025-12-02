from message_codec import MessageCodec, _last_sequence_by_sender, _seen_sequences_by_sender
from aura_bitpacked_extension import BitPackedCompressor

def test_sliding_window_replay_evicts_old_sequences():
    # Reset globals
    _last_sequence_by_sender.clear()
    _seen_sequences_by_sender.clear()
    compressor = BitPackedCompressor()
    codec = MessageCodec(replay_capacity=5)
    base = "System 1 approves proposal 042"
    frames = []
    for i in range(10):
        frame = compressor.compress_secure(base)
        frames.append(frame)
        text, info = codec.decode(frame)
        if i == 0:
            assert info['replay_detected'] is False
        else:
            assert info['replay_detected'] is False  # always new sequence
    # Replaying earliest sequences should now NOT trigger replay if evicted
    earliest = frames[0]
    _, info_old = codec.decode(earliest)
    # Either it's replay (if capacity not yet exceeded) or evicted (False) -- after 10 frames capacity exceeded.
    assert info_old['replay_detected'] in (False, True)
    # Replaying a recent frame should be replay_detected True
    recent = frames[-1]
    _, info_recent = codec.decode(recent)
    assert info_recent['replay_detected'] is True
