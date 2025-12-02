import random
from aura_bitpacked_extension import BitPackedCompressor
from message_codec import MessageCodec


def corrupt_bytes(b: bytes) -> bytes:
    if not b:
        return b
    arr = bytearray(b)
    # Flip 1-2 random bits
    flips = random.randint(1, 2)
    for _ in range(flips):
        i = random.randrange(len(arr))
        arr[i] ^= 1 << random.randrange(0, 8)
    return bytes(arr)


def test_decode_handles_corruption_without_crash():
    random.seed(1234)
    compressor = BitPackedCompressor()
    codec = MessageCodec()
    base = "System 1 approves proposal 042"
    frames = [compressor.compress_secure(base) for _ in range(50)]
    frames = [f for f in frames if f is not None]
    assert frames
    crashes = 0
    for frame in frames:
        # Try a few corruptions and ensure we either raise ValueError or return sane info
        for _ in range(5):
            c = corrupt_bytes(frame)
            try:
                _text, info = codec.decode(c)
                # If decode returns, method must be AURA or BITPACKED_*; basic keys exist
                assert "method" in info
            except ValueError:
                # Expected for bad CRC/format
                pass
    assert crashes == 0
