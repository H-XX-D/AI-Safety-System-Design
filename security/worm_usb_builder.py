"""WORM USB Builder
===================

Creates a write-once, read-many (WORM) style package for air-gapped review.

Capabilities:
- Collect critical artifacts (protocol spec, translator code, ESP32 decoder headers,
  Python decoder spec, reward engine, WORM manifest, config snapshot)
- Generate a hash manifest (SHA256) for each file and an overall root hash
- Sign manifest with HMAC-SHA256 (shared secret model) for quick verification
- Optional asymmetric signing using Ed25519 (PEM keys) for stronger verification
- Verify an existing WORM directory against its manifest and signature

This tool complements offline_bundle.py (packages/wheels). Use both when preparing
an air-gapped USB: one for Python packages, one for source/spec/firmware artifacts.

Usage:
  python worm_usb_builder.py prepare worm_usb_dir \
    --protocol translator_protocol.json \
    --translator translator.py \
    --hardware_head_dir esp32 \
    --python_decoder aura_bitpacked_extension.py \
    --reward_engine reward_engine.py \
    --worm_manifest worm_manifest.py \
    --config config

  python worm_usb_builder.py sign worm_usb_dir/manifest.json worm_usb_dir/manifest.sig --secret $SECRET
  python worm_usb_builder.py verify worm_usb_dir worm_usb_dir/manifest.json
  python worm_usb_builder.py verify-signature worm_usb_dir/manifest.json worm_usb_dir/manifest.sig --secret $SECRET
  
    # Ed25519 (asymmetric) signing and verification
    python worm_usb_builder.py sign-ed25519 worm_usb_dir/manifest.json worm_usb_dir/manifest.ed25519 --private-key private_key.pem
    python worm_usb_builder.py verify-ed25519 worm_usb_dir/manifest.json worm_usb_dir/manifest.ed25519 --public-key public_key.pem

Note: Real WORM enforcement is physical (read-only media or signed immutable records).
This script provides cryptographic immutability signals (hashes and signatures).
"""
from __future__ import annotations

import argparse
import hashlib
import hmac
import json
import os
from dataclasses import dataclass
from utilities.logging_config import get_logger

logger = get_logger(__name__)
import shutil
from typing import Dict, List, Any, Optional
import datetime as datetime


@dataclass
class ArtifactEntry:
    path: str
    rel_path: str
    sha256: str
    size_bytes: int

    def to_dict(self) -> Dict[str, Any]:
        return {
            'path': self.rel_path,
            'sha256': self.sha256,
            'size_bytes': self.size_bytes,
        }


def _hash_file(path: str) -> str:
    h = hashlib.sha256()
    with open(path, 'rb') as f:
        for chunk in iter(lambda: f.read(65536), b''):
            h.update(chunk)
    return h.hexdigest()


def _collect_dir(dir_path: str, base_out: str, include_exts: Optional[List[str]] = None) -> List[str]:
    files_out: List[str] = []
    include_exts = include_exts or []
    for root, _, files in os.walk(dir_path):
        for fn in sorted(files):
            if include_exts and not any(fn.endswith(ext) for ext in include_exts):
                continue
            full = os.path.join(root, fn)
            if not os.path.isfile(full):
                continue
            files_out.append(full)
    return files_out


def prepare(args: argparse.Namespace) -> Dict[str, Any]:
    out_dir = args.out_dir
    os.makedirs(out_dir, exist_ok=True)

    artifacts: List[ArtifactEntry] = []
    to_process: List[str] = []

    # Individual files
    def add_if(path: Optional[str]):
        if not path:
            return
        if not os.path.isfile(path):
            return
        to_process.append(path)

    add_if(args.protocol)
    add_if(args.translator)
    add_if(args.python_decoder)
    add_if(args.reward_engine)
    add_if(args.worm_manifest)

    # ESP32 headers / C sources
    if args.hardware_head_dir and os.path.isdir(args.hardware_head_dir):
        to_process.extend(_collect_dir(args.hardware_head_dir, out_dir, include_exts=['.h', '.hpp', '.c', '.cpp']))

    # Config snapshot (directory)
    if args.config and os.path.isdir(args.config):
        to_process.extend(_collect_dir(args.config, out_dir))

    # Optionally materialize files into out_dir/files for portability
    materialized: bool = bool(getattr(args, 'materialize', False))
    files_dir_opt: Optional[str] = os.path.join(out_dir, 'files') if materialized else None
    files_dir: Optional[str] = None
    if materialized:
        assert files_dir_opt is not None
        files_dir = files_dir_opt
        os.makedirs(files_dir, exist_ok=True)

    for src in sorted(set(to_process)):
        sha = _hash_file(src)
        size = os.path.getsize(src)
        if materialized and files_dir is not None:
            base = os.path.basename(src)
            safe_name = f"{sha[:8]}_{base}"
            # files_dir exists and is str via guard above
            dest: str = os.path.join(files_dir, safe_name)
            shutil.copy2(src, dest)
            rel: str = os.path.relpath(dest, start=os.path.dirname(out_dir))
        else:
            rel = os.path.relpath(src, start=os.path.dirname(out_dir))
        artifacts.append(ArtifactEntry(path=src, rel_path=rel, sha256=sha, size_bytes=size))

    # Sort and write files into out_dir/ARTIFACTS (copy-free manifest by default)
    # For air-gapped workflows, you may copy the referenced files next to manifest if desired.

    manifest: Dict[str, Any] = {
        'created': datetime.now().astimezone().isoformat(),
        'artifacts': [e.to_dict() for e in artifacts],
        'materialized': materialized,
    }

    # Compute root hash over concatenated (path || sha256)
    root_hasher = hashlib.sha256()
    for e in artifacts:
        root_hasher.update(e.rel_path.encode('utf-8'))
        root_hasher.update(b'::')
        root_hasher.update(e.sha256.encode('utf-8'))
    manifest['root_sha256'] = root_hasher.hexdigest()

    out_manifest = os.path.join(out_dir, 'manifest.json')
    with open(out_manifest, 'w') as f:
        json.dump(manifest, f, indent=2, sort_keys=True)

    logger.info("worm_manifest_written", path=out_manifest, artifacts=len(artifacts), root_sha256=manifest['root_sha256'])
    return manifest


def verify(worm_dir: str, manifest_path: str) -> bool:
    with open(manifest_path, 'r') as f:
        manifest = json.load(f)
    ok = True
    failures: List[str] = []

    materialized = bool(manifest.get('materialized'))

    # Verify each artifact hash
    for art in manifest.get('artifacts', []):
        rel = art['path']
        expected = art['sha256']

        # Primary resolution (original design): relative to parent of worm_dir
        candidates: List[str] = [os.path.join(os.path.dirname(worm_dir), rel)]

        # Alternate: resolve relative to worm_dir root (useful for DMG mounts)
        candidates.append(os.path.join(worm_dir, rel))

        # If the manifest was materialized, the rel path may include a top-level folder name
        # (e.g., "worm_usb_dir/files/<file>"). Try stripping the first segment.
        if os.sep in rel:
            _, rest = rel.split(os.sep, 1)
            candidates.append(os.path.join(worm_dir, rest))

        # If a 'files' directory exists inside worm_dir, prefer anchoring to it when present in rel
        if 'files' in rel.split(os.sep):
            try:
                parts = rel.split(os.sep)
                idx = parts.index('files')
                rel_from_files = os.path.join(*parts[idx:])  # type: ignore[arg-type]
                candidates.append(os.path.join(worm_dir, rel_from_files))  # type: ignore[arg-type]
            except ValueError:
                pass

        full: Optional[str] = None
        for cand in candidates:
            if os.path.exists(cand):
                full = cand
                break

        if not full:
            ok = False
            failures.append(f"missing:{rel}")
            continue

        actual = _hash_file(full)
        if actual != expected:
            ok = False
            failures.append(f"sha_mismatch:{rel}")

    # Recompute root
    root_hasher = hashlib.sha256()
    for art in manifest.get('artifacts', []):
        root_hasher.update(art['path'].encode('utf-8'))
        root_hasher.update(b'::')
        root_hasher.update(art['sha256'].encode('utf-8'))
    expected_root = manifest.get('root_sha256')
    actual_root = root_hasher.hexdigest()
    if actual_root != expected_root:
        ok = False
        failures.append(f"root_mismatch:{actual_root}!={expected_root}")

    if ok:
        logger.info("worm_verification_ok")
    else:
        # Provide a hint if likely caused by non-materialized DMG contents
        if not materialized:
            failures.append("hint: manifest not materialized (no files copied). Rebuild with --materialize or verify against original workspace paths.")
        logger.warning("worm_verification_failed", failures=failures)
    return ok


def sign_manifest(manifest_path: str, signature_path: str, secret: str) -> str:
    with open(manifest_path, 'rb') as f:
        data = f.read()
    sig = hmac.new(secret.encode('utf-8'), data, hashlib.sha256).hexdigest()
    with open(signature_path, 'w') as f:
        f.write(sig + "\n")
    logger.info("signature_written", path=signature_path)
    return sig


def verify_signature(manifest_path: str, signature_path: str, secret: str) -> bool:
    with open(signature_path, 'r') as f:
        stored = f.read().strip()
    with open(manifest_path, 'rb') as f:
        data = f.read()
    expected = hmac.new(secret.encode('utf-8'), data, hashlib.sha256).hexdigest()
    ok = hmac.compare_digest(expected, stored)
    logger.info("signature_verification", ok=ok)
    return ok


# ---------------- Ed25519 asymmetric signing (optional) ----------------
def sign_manifest_ed25519(manifest_path: str, signature_path: str, private_key_path: str) -> str:
    """Sign manifest with Ed25519 using a PEM private key.

    The signature file is written in base64.
    Dependencies are imported lazily to avoid requiring cryptography when not used.
    """
    with open(manifest_path, 'rb') as f:
        data = f.read()
    try:
        from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey  # type: ignore
        from cryptography.hazmat.primitives import serialization  # type: ignore
    except Exception as e:  # pragma: no cover - dependency error path
        raise RuntimeError("cryptography package is required for ed25519 signing") from e

    with open(private_key_path, 'rb') as f:
        key_data = f.read()
    private_key_obj = serialization.load_pem_private_key(key_data, password=None)  # type: ignore[assignment]
    if not isinstance(private_key_obj, Ed25519PrivateKey):
        raise ValueError("Private key is not an Ed25519 key")
    sig_bytes = private_key_obj.sign(data)  # type: ignore[assignment]

    import base64
    sig_b64 = base64.b64encode(bytes(sig_bytes)).decode('ascii')  # type: ignore[arg-type]
    with open(signature_path, 'w') as f:
        f.write(sig_b64 + "\n")
    logger.info("ed25519_signature_written", path=signature_path)
    return sig_b64


def verify_signature_ed25519(manifest_path: str, signature_path: str, public_key_path: str) -> bool:
    """Verify Ed25519 signature using a PEM public key (SubjectPublicKeyInfo)."""
    try:
        from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PublicKey  # type: ignore
        from cryptography.hazmat.primitives import serialization  # type: ignore
    except Exception as e:  # pragma: no cover - dependency error path
        raise RuntimeError("cryptography package is required for ed25519 verification") from e

    with open(signature_path, 'r') as f:
        import base64
        sig_b64 = f.read().strip()
        sig_bytes = base64.b64decode(sig_b64)
    with open(manifest_path, 'rb') as f:
        data = f.read()
    with open(public_key_path, 'rb') as f:
        pub_data = f.read()
    public_key_obj = serialization.load_pem_public_key(pub_data)  # type: ignore[assignment]
    if not isinstance(public_key_obj, Ed25519PublicKey):
        raise ValueError("Public key is not an Ed25519 key")
    try:
        public_key_obj.verify(sig_bytes, data)  # type: ignore[arg-type]
        logger.info("ed25519_signature_verification_ok")
        return True
    except Exception:
        logger.warning("ed25519_signature_verification_failed")
        return False


def _args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description='WORM USB Builder')
    sub = p.add_subparsers(dest='cmd', required=True)

    pr = sub.add_parser('prepare', help='Prepare a WORM manifest for artifacts')
    pr.add_argument('out_dir', help='Output directory for manifest')
    pr.add_argument('--protocol', help='Protocol spec file (JSON/MD)')
    pr.add_argument('--translator', help='Translator code (Python)')
    pr.add_argument('--hardware_head_dir', help='Directory of ESP32 headers/sources')
    pr.add_argument('--python_decoder', help='Python decoder spec (e.g., aura_bitpacked_extension.py)')
    pr.add_argument('--reward_engine', help='reward_engine.py path')
    pr.add_argument('--worm_manifest', help='worm_manifest.py path')
    pr.add_argument('--config', help='Config directory to snapshot')
    pr.add_argument('--materialize', action='store_true', help='Copy files into out_dir/files for portable, self-contained USB')

    sg = sub.add_parser('sign', help='Sign manifest (HMAC)')
    sg.add_argument('manifest_path')
    sg.add_argument('signature_path')
    sg.add_argument('--secret', required=True)

    vf = sub.add_parser('verify', help='Verify WORM directory against manifest')
    vf.add_argument('worm_dir')
    vf.add_argument('manifest_path')

    vs = sub.add_parser('verify-signature', help='Verify HMAC signature of manifest')
    vs.add_argument('manifest_path')
    vs.add_argument('signature_path')
    vs.add_argument('--secret', required=True)

    se = sub.add_parser('sign-ed25519', help='Sign manifest (Ed25519, PEM private key)')
    se.add_argument('manifest_path')
    se.add_argument('signature_path')
    se.add_argument('--private-key', required=True)

    ve = sub.add_parser('verify-ed25519', help='Verify Ed25519 signature of manifest')
    ve.add_argument('manifest_path')
    ve.add_argument('signature_path')
    ve.add_argument('--public-key', required=True)

    return p.parse_args()


def main() -> int:
    ns = _args()
    try:
        if ns.cmd == 'prepare':
            prepare(ns)
            return 0
        if ns.cmd == 'verify':
            return 0 if verify(ns.worm_dir, ns.manifest_path) else 2
        if ns.cmd == 'sign':
            sign_manifest(ns.manifest_path, ns.signature_path, ns.secret)
            return 0
        if ns.cmd == 'verify-signature':
            return 0 if verify_signature(ns.manifest_path, ns.signature_path, ns.secret) else 3
        if ns.cmd == 'sign-ed25519':
            sign_manifest_ed25519(ns.manifest_path, ns.signature_path, ns.private_key)
            return 0
        if ns.cmd == 'verify-ed25519':
            return 0 if verify_signature_ed25519(ns.manifest_path, ns.signature_path, ns.public_key) else 3
        logger.warning('unknown_command')
        return 1
    except Exception as e:
        logger.exception("error_running_worm_usb_builder", exc_info=True)
        return 10


if __name__ == '__main__':  # pragma: no cover
    raise SystemExit(main())
