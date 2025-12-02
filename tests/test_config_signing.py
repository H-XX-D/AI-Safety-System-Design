import pytest
from binascii import hexlify

try:
    from nacl.signing import SigningKey
except Exception:  # pragma: no cover
    SigningKey = None  # type: ignore

from config_loader import verify_signature_ed25519


def test_verify_signature_ed25519_roundtrip():
    if SigningKey is None:
        pytest.skip("PyNaCl not installed in active interpreter")
    sk = SigningKey.generate()
    vk = sk.verify_key
    msg = b"hello world"
    sig = sk.sign(msg).signature
    ok = verify_signature_ed25519(msg, hexlify(sig).decode(), vk.encode().hex())
    assert ok is True
    # Tamper
    bad = bytearray(sig)
    bad[0] ^= 0x01
    ok2 = verify_signature_ed25519(msg, hexlify(bytes(bad)).decode(), vk.encode().hex())
    assert ok2 is False
