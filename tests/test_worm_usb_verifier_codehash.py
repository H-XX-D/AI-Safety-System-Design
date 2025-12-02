import hashlib
from worm_usb_verifier import WORMConfiguration


def test_validate_code_hash_returns_computed_crc():
    valid, computed = WORMConfiguration.validate_code_hash()
    assert isinstance(computed, str)
    # Computed nec should be SHA256 length 64
    assert len(computed) in (64, 0)  # empty string indicates read error
    if computed:
        # confirm it's hex
        int(computed, 16)