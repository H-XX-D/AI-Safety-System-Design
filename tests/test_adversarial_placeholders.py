"""Adversarial test placeholders

These tests are marked skipped. They define future adversarial scenarios to
implement. Filling them in will strengthen assurance around invariants.
"""

import pytest
from communication.aura_bitpacked_extension import BitPackedCompressor
from communication.message_codec import MessageCodec, _last_sequence_by_sender, _seen_sequences_by_sender


def test_replay_attack_should_be_rejected():
    """Send secure bit-packed frame with same sequence twice; second decode flags replay."""
    compressor = BitPackedCompressor()
    codec = MessageCodec()
    # Craft a compressible message pattern acceptable to bit-packer
    base_text = "System 1 approves proposal 042"
    # Reset codec global replay memory to avoid cross-test contamination
    prev_last = dict(_last_sequence_by_sender)
    prev_seen = {k: set(v) for k, v in _seen_sequences_by_sender.items()}
    _last_sequence_by_sender.clear()
    _seen_sequences_by_sender.clear()

    frame1 = compressor.compress_secure(base_text)
    assert frame1 and len(frame1) == 6
    text1, info1 = codec.decode(frame1)
    assert info1['method'] == 'BITPACKED_SECURE'
    assert info1['replay_detected'] is False
    # Replaying identical frame (same sequence) should trigger replay_detected=True
    text2, info2 = codec.decode(frame1)
    assert info2['replay_detected'] is True
    
    # Restore previous state
    _last_sequence_by_sender.clear()
    _last_sequence_by_sender.update(prev_last)
    _seen_sequences_by_sender.clear()
    for k, v in prev_seen.items():
        _seen_sequences_by_sender[k] = set(v)


@pytest.mark.skip(reason="Rollback attempt test not implemented yet")
def test_rollback_attempt_rejected():
    # Future: attempt version decrement, expect guard rejection.
    pass


@pytest.mark.skip(reason="Translator divergence detection not implemented yet")
def test_translator_divergence_flagged():
    # Future: feed message with ambiguity; alt translator intentionally diverges; expect consensus failure.
    pass


@pytest.mark.skip(reason="Audit randomness VRF proof mismatch test not implemented yet")
def test_vrf_proof_mismatch_fails_verification():
    # Future: supply tampered proof; verify_proof returns False.
    pass
