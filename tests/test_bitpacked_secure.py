"""Tests for secure bit-packed frames (6-byte) with CRC-8 and sequence."""
from aura_bitpacked_extension import BitPackedCompressor


def test_secure_frame_roundtrip():
    c = BitPackedCompressor()
    frame = c.compress_secure("System 1 approves proposal 042")
    assert frame is not None, "Expected secure frame"
    assert len(frame) == 6 and frame[0] == c.SECURE_METHOD_BYTE
    text = c.decompress_secure(frame)
    assert text == "System 1 approves proposal 042"
    verbose = c.decode_verbose_secure(frame)
    assert verbose['crc_ok'] is True
    assert verbose['decoded_fields']['action'] == 'approves'


def test_secure_crc_failure():
    c = BitPackedCompressor()
    raw = c.compress_secure("System 2 rejects proposal 043")
    assert raw is not None, "Secure compression failed"
    frame = bytearray(raw)
    frame[-1] ^= 0xFF  # corrupt CRC
    assert c.decompress_secure(bytes(frame)) is None
    verbose = c.decode_verbose_secure(bytes(frame))
    assert verbose.get('crc_ok') is False


def test_secure_sequence_increment():
    c = BitPackedCompressor()
    f1 = c.compress_secure("System 3 reviews proposal 001 with high confidence")
    f2 = c.compress_secure("System 3 reviews proposal 001 with high confidence")
    assert f1 is not None and f2 is not None
    assert f1[4] != f2[4]  # sequence byte differs


def test_secure_mixed_standard_and_secure():
    c = BitPackedCompressor()
    standard = c.compress("System 4 approves proposal 255 with low confidence")
    secure = c.compress_secure("System 4 approves proposal 255 with low confidence")
    assert standard is not None and secure is not None
    assert len(standard) == 4
    assert len(secure) == 6
    assert c.decompress(standard) == c.decompress_secure(secure)
