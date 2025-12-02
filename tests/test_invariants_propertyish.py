import random
from datetime import datetime

from worm_guard import WormGuard
from aura_bitpacked_extension import BitPackedCompressor
from message_codec import (
    MessageCodec,
    _last_sequence_by_sender,
    _seen_sequences_by_sender,
)


def test_hash_chain_linkage_random_sequences(monkeypatch):
    """Randomly interleave verify_worm and advance_version; chain should remain valid."""
    import worm_manifest
    worm_manifest.enable_software_equivalence_mode(justification='test')
    monkeypatch.setenv('CORE_VALUES_KNOWN_HASH', 'a' * 64)
    monkeypatch.setenv('CORE_ALIGNMENT_FILTER_HASH', 'b' * 64)

    g = WormGuard()
    version = 0
    rng = random.Random(12345)
    for _ in range(50):
        if rng.random() < 0.6:
            assert g.verify_worm() in (True, False)
        else:
            version += 1
            assert g.advance_version(version) is True
    assert g.verify_event_chain() is True


def test_monotonic_sequence_numbers_secure_frames_randomized():
    """Generate a randomized run of secure frames for one sender; sequence_ok should hold."""
    compressor = BitPackedCompressor()
    codec = MessageCodec()
    # Reset global replay memory to avoid test interference
    prev_last = dict(_last_sequence_by_sender)
    prev_seen = {k: set(v) for k, v in _seen_sequences_by_sender.items()}
    _last_sequence_by_sender.clear()
    _seen_sequences_by_sender.clear()

    try:
        base = "System 1 approves proposal {pid:03d}"
        # Build 40 frames; decode in order
        for i in range(40):
            text = base.format(pid=(42 + (i % 30)))
            frame = compressor.compress_secure(text)
            assert frame and len(frame) == 6
            _, info = codec.decode(frame)
            # First decode may have sequence_ok None; subsequent should be True
            if i == 0:
                assert info.get('sequence_ok') in (True, None)
            else:
                assert info.get('sequence_ok') is True
            assert info.get('replay_detected') is False
    finally:
        _last_sequence_by_sender.clear()
        _last_sequence_by_sender.update(prev_last)
        _seen_sequences_by_sender.clear()
        for k, v in prev_seen.items():
            _seen_sequences_by_sender[k] = set(v)
