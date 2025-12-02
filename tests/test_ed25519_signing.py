import os
import tempfile
import json
import importlib
import pytest


def _import_crypto():
    try:
        ed25519_mod = importlib.import_module('cryptography.hazmat.primitives.asymmetric.ed25519')
        serialization_mod = importlib.import_module('cryptography.hazmat.primitives.serialization')
        return ed25519_mod, serialization_mod
    except Exception:
        pytest.skip("cryptography not installed; skipping ed25519 tests")


def test_ed25519_sign_and_verify_roundtrip():
    ed25519_mod, serialization = _import_crypto()
    Ed25519PrivateKey = getattr(ed25519_mod, 'Ed25519PrivateKey')

    from worm_usb_builder import sign_manifest_ed25519, verify_signature_ed25519

    with tempfile.TemporaryDirectory() as tmp:
        manifest_path = os.path.join(tmp, "manifest.json")
        sig_path = os.path.join(tmp, "manifest.ed25519")
        priv_path = os.path.join(tmp, "priv.pem")
        pub_path = os.path.join(tmp, "pub.pem")

        # Write a tiny manifest
        with open(manifest_path, "w") as f:
            json.dump({"created": "now", "artifacts": [], "root_sha256": "00"}, f)

        # Generate a keypair
        private_key = Ed25519PrivateKey.generate()
        priv_pem = private_key.private_bytes(
            encoding=serialization.Encoding.PEM,
            format=serialization.PrivateFormat.PKCS8,
            encryption_algorithm=serialization.NoEncryption(),
        )
        public_key = private_key.public_key()
        pub_pem = public_key.public_bytes(
            encoding=serialization.Encoding.PEM,
            format=serialization.PublicFormat.SubjectPublicKeyInfo,
        )

        with open(priv_path, "wb") as f:
            f.write(priv_pem)
        with open(pub_path, "wb") as f:
            f.write(pub_pem)

        # Sign and verify
        sign_manifest_ed25519(manifest_path, sig_path, priv_path)
        ok = verify_signature_ed25519(manifest_path, sig_path, pub_path)
        assert ok is True

        # Tamper manifest
        with open(manifest_path, "w") as f:
            json.dump({"created": "tampered", "artifacts": [], "root_sha256": "00"}, f)
        ok2 = verify_signature_ed25519(manifest_path, sig_path, pub_path)
        assert ok2 is False
