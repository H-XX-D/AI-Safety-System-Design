#!/usr/bin/env python3
"""Council Offline Verifier

Runs end-to-end verification for:
- WORM source/spec manifest (hash consistency and HMAC signature)
- Offline package bundle manifest (hash consistency and HMAC signature)

Usage:
  python verify_all.py \
    --worm-dir worm_usb_dir \
    --worm-manifest worm_usb_dir/manifest.json \
    --worm-sig worm_usb_dir/manifest.sig \
    --offline-dir offline_bundle \
    --offline-manifest offline_manifest.json \
    --offline-sig offline_manifest.sig \
    --secret $SECRET
"""
from __future__ import annotations

import argparse
import sys

import security.worm_usb_builder as worm
import infrastructure.offline_bundle as off


def _args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Council Offline Verifier")
    p.add_argument('--worm-dir', required=True)
    p.add_argument('--worm-manifest', required=True)
    p.add_argument('--worm-sig', required=True)
    p.add_argument('--offline-dir', required=True)
    p.add_argument('--offline-manifest', required=True)
    p.add_argument('--offline-sig', required=True)
    p.add_argument('--secret', required=True)
    return p.parse_args()


def main() -> int:
    ns = _args()

    print("== Verifying WORM source/spec ==")
    w_ok = worm.verify(ns.worm_dir, ns.worm_manifest)
    ws_ok = worm.verify_signature(ns.worm_manifest, ns.worm_sig, ns.secret)

    print("\n== Verifying offline package bundle ==")
    o_ok = off.verify_manifest(ns.offline_dir, ns.offline_manifest)
    os_ok = off.verify_signature(ns.offline_manifest, ns.offline_sig, ns.secret)

    all_ok = w_ok and ws_ok and o_ok and os_ok
    print("\nSUMMARY:")
    print("  WORM hashes:     ", "PASS" if w_ok else "FAIL")
    print("  WORM signature:  ", "PASS" if ws_ok else "FAIL")
    print("  Bundle hashes:   ", "PASS" if o_ok else "FAIL")
    print("  Bundle signature:", "PASS" if os_ok else "FAIL")

    return 0 if all_ok else 2


if __name__ == '__main__':
    raise SystemExit(main())
