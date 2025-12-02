import pytest
from pathlib import Path

from models.key_rotation import generate_keypair, sign_config, rotate_key
from utilities.config_loader import verify_signature_ed25519, verify_signature_with_keyring

pytestmark = pytest.mark.skipif('nacl' not in globals(), reason='PyNaCl may be missing')


def test_key_rotation_and_verification(tmp_path: Path):
    # Generate initial key
    pub1, priv1 = generate_keypair()
    text = "setting: value\nflag: true"
    sig1 = sign_config(text, priv1)
    assert verify_signature_ed25519(text.encode(), sig1, pub1) is True
    # Rotate key
    storage: Path = tmp_path / 'rot'
    storage.mkdir()
    kv = rotate_key(str(storage))
    pub2, priv2 = kv.public_hex, kv.private_hex
    sig2 = sign_config(text, priv2)
    # Old signature should fail under new key alone
    assert verify_signature_ed25519(text.encode(), sig1, pub2) is False
    # With keyring including both (not revoked) -> success for old and new
    assert verify_signature_with_keyring(text.encode(), sig1, [pub1, pub2]) is True
    assert verify_signature_with_keyring(text.encode(), sig2, [pub1, pub2]) is True
    # Revoking old key causes old signature rejection
    assert verify_signature_with_keyring(text.encode(), sig1, [pub1, pub2], revoked_hex={pub1}) is False
    assert verify_signature_with_keyring(text.encode(), sig2, [pub1, pub2], revoked_hex={pub1}) is True
