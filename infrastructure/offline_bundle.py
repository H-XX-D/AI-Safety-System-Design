"""Offline Bundle Manifest Tooling
=================================

Utilities to:
 - generate manifest JSON with SHA256 + size for wheel artifacts
 - verify manifest against directory contents
 - sign / verify manifest using HMAC-SHA256 (shared secret model)

Usage (staging):
  python offline_bundle.py generate offline_bundle offline_manifest.json
  python offline_bundle.py sign offline_manifest.json offline_manifest.sig --secret $SECRET

Usage (air-gapped):
  python offline_bundle.py verify offline_bundle offline_manifest.json
  python offline_bundle.py verify-signature offline_manifest.json offline_manifest.sig --secret $SECRET

Exit codes: 0 success; non-zero indicates failure.
"""
from __future__ import annotations

import argparse
import hashlib
import hmac
import json
import os
from dataclasses import dataclass
from typing import List, Dict, Any
from datetime import datetime


@dataclass
class PackageEntry:
    filename: str
    sha256: str
    size_bytes: int
    name: str

    def to_dict(self) -> Dict[str, Any]:
        return {
            'filename': self.filename,
            'sha256': self.sha256,
            'size_bytes': self.size_bytes,
            'name': self.name
        }


def _hash_file(path: str) -> str:
    h = hashlib.sha256()
    with open(path, 'rb') as f:
        for chunk in iter(lambda: f.read(65536), b''):
            h.update(chunk)
    return h.hexdigest()


def _infer_name(filename: str) -> str:
    # Best-effort extraction: split at '-' for wheels.
    if filename.endswith('.whl'):
        return filename.split('-')[0]
    return os.path.splitext(filename)[0]


def generate_manifest(bundle_dir: str, manifest_path: str) -> Dict[str, Any]:
    entries: List[PackageEntry] = []
    for fn in sorted(os.listdir(bundle_dir)):
        # Include Python packages and hardware/firmware artifacts needed for air-gapped translators
        if (fn.endswith('.whl') or fn.endswith('.tar.gz') or
            fn.endswith('.bin') or fn.endswith('.hex') or
            fn.endswith('.h') or fn.endswith('.hpp') or
            fn.endswith('.c') or fn.endswith('.cpp')):
            full = os.path.join(bundle_dir, fn)
            if not os.path.isfile(full):
                continue
            sha = _hash_file(full)
            size = os.path.getsize(full)
            entries.append(PackageEntry(filename=fn, sha256=sha, size_bytes=size, name=_infer_name(fn)))
    manifest: Dict[str, Any] = {
        'created': datetime.now().astimezone().isoformat(),
        'packages': [e.to_dict() for e in entries]
    }
    with open(manifest_path, 'w') as f:
        json.dump(manifest, f, indent=2, sort_keys=True)
    return manifest


def verify_manifest(bundle_dir: str, manifest_path: str) -> bool:
    with open(manifest_path, 'r') as f:
        manifest = json.load(f)
    ok = True
    failures: List[str] = []
    for pkg in manifest.get('packages', []):
        fn = pkg['filename']
        expected_sha = pkg['sha256']
        full = os.path.join(bundle_dir, fn)
        if not os.path.exists(full):
            ok = False
            failures.append(f"missing:{fn}")
            continue
        actual_sha = _hash_file(full)
        if actual_sha != expected_sha:
            ok = False
            failures.append(f"sha_mismatch:{fn}")
    if not ok:
        print("Verification failed:", failures)
    else:
        print("Verification succeeded; all hashes match.")
    return ok


def sign_manifest(manifest_path: str, signature_path: str, secret: str) -> str:
    with open(manifest_path, 'rb') as f:
        data = f.read()
    sig = hmac.new(secret.encode('utf-8'), data, hashlib.sha256).hexdigest()
    with open(signature_path, 'w') as f:
        f.write(sig + "\n")
    return sig


def verify_signature(manifest_path: str, signature_path: str, secret: str) -> bool:
    with open(signature_path, 'r') as f:
        stored = f.read().strip()
    with open(manifest_path, 'rb') as f:
        data = f.read()
    expected = hmac.new(secret.encode('utf-8'), data, hashlib.sha256).hexdigest()
    if hmac.compare_digest(expected, stored):
        print("Signature verification OK.")
        return True
    print("Signature verification FAILED.")
    return False


def _parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Offline bundle manifest tooling")
    sub = p.add_subparsers(dest='cmd', required=True)

    g = sub.add_parser('generate', help='Generate manifest JSON from bundle directory')
    g.add_argument('bundle_dir')
    g.add_argument('manifest_path')

    v = sub.add_parser('verify', help='Verify manifest hashes against bundle directory')
    v.add_argument('bundle_dir')
    v.add_argument('manifest_path')

    s = sub.add_parser('sign', help='Sign manifest with HMAC-SHA256')
    s.add_argument('manifest_path')
    s.add_argument('signature_path')
    s.add_argument('--secret', required=True)

    vs = sub.add_parser('verify-signature', help='Verify HMAC signature of manifest')
    vs.add_argument('manifest_path')
    vs.add_argument('signature_path')
    vs.add_argument('--secret', required=True)

    return p.parse_args()


def main() -> int:
    ns = _parse_args()
    try:
        if ns.cmd == 'generate':
            generate_manifest(ns.bundle_dir, ns.manifest_path)
            return 0
        if ns.cmd == 'verify':
            return 0 if verify_manifest(ns.bundle_dir, ns.manifest_path) else 2
        if ns.cmd == 'sign':
            sign_manifest(ns.manifest_path, ns.signature_path, ns.secret)
            return 0
        if ns.cmd == 'verify-signature':
            return 0 if verify_signature(ns.manifest_path, ns.signature_path, ns.secret) else 3
        print("Unknown command")
        return 1
    except Exception as e:
        print(f"Error: {e}")
        return 10


if __name__ == '__main__':  # pragma: no cover
    raise SystemExit(main())
