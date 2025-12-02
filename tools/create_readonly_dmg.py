#!/usr/bin/env python3
"""Create a read-only DMG from a WORM staging directory (macOS)

This helper wraps `hdiutil` to produce a UDRO (read-only) or UDBZ (compressed read-only)
disk image from a source folder (defaults to `worm_usb_dir`). It can optionally attach the
image and verify the manifest using the project-local `worm_usb_builder.py`.

Examples:
  # Create read-only (UDRO) image with default names
  python tools/create_readonly_dmg.py --src worm_usb_dir --volname WORM_AI_SAFETY --out WORM_AI_SAFETY.dmg

  # Create compressed read-only (UDBZ) and verify after attaching
  python tools/create_readonly_dmg.py --src worm_usb_dir --volname WORM_AI_SAFETY \
    --out WORM_AI_SAFETY_udbz.dmg --format UDBZ --verify
"""
from __future__ import annotations

import argparse
import os
import subprocess
import sys
from typing import Optional

# Local import for verification
import worm_usb_builder as worm


def _run(cmd: list[str]) -> subprocess.CompletedProcess:
    return subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, check=True)


def _attach(dmg_path: str) -> str:
    # Returns the mount point (e.g., /Volumes/<VOL>)
    cp = _run(["hdiutil", "attach", dmg_path, "-readonly"])
    # Try to find a line with a mount path
    mount_point: Optional[str] = None
    for line in cp.stdout.splitlines():
        # Typical output ends with the mounted path
        parts = line.split("\t")
        if len(parts) >= 3 and parts[-1].startswith("/Volumes/"):
            mount_point = parts[-1].strip()
    if not mount_point:
        # Fallback: list /Volumes and hope the newest or named one is present; prefer explicit volname usage
        raise RuntimeError("Could not determine mount point from hdiutil output:\n" + cp.stdout)
    return mount_point


def _detach(mount_point: str) -> None:
    _run(["hdiutil", "detach", mount_point])


def create_readonly_dmg(src: str, volname: str, out_path: str, fmt: str, verify: bool) -> int:
    if not os.path.isdir(src):
        print(f"Source directory not found: {src}")
        return 2
    manifest_path = os.path.join(src, "manifest.json")
    if not os.path.isfile(manifest_path):
        print(f"manifest.json not found in source dir: {manifest_path}")
        return 2

    # Build the image
    print(f"Creating {fmt} image → {out_path}")
    _run(["hdiutil", "create", "-fs", "HFS+", "-srcfolder", src, "-volname", volname, "-format", fmt, out_path])

    if not verify:
        print("DMG created. Skipping verification (use --verify to validate).")
        return 0

    # Attach and verify
    print("Attaching image (read-only) for verification...")
    mount_point = _attach(out_path)
    try:
        print(f"Mounted at: {mount_point}")
        ok = worm.verify(mount_point, os.path.join(mount_point, "manifest.json"))
        print("Verification:", "PASS" if ok else "FAIL")
        return 0 if ok else 3
    finally:
        print("Detaching image...")
        _detach(mount_point)


def _args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Create a read-only DMG from WORM staging (macOS)")
    p.add_argument("--src", default="worm_usb_dir", help="Source folder (must contain manifest.json)")
    p.add_argument("--volname", default="WORM_AI_SAFETY", help="Volume name inside the DMG")
    p.add_argument("--out", default="WORM_AI_SAFETY.dmg", help="Output DMG path")
    p.add_argument("--format", dest="fmt", default="UDRO", choices=["UDRO", "UDBZ"], help="Image format: UDRO (ro) or UDBZ (compressed ro)")
    p.add_argument("--verify", action="store_true", help="Attach and verify manifest after creating the image")
    return p.parse_args()


def main() -> int:
    ns = _args()
    try:
        return create_readonly_dmg(ns.src, ns.volname, ns.out, ns.fmt, ns.verify)
    except subprocess.CalledProcessError as e:
        print("Command failed:", e.cmd)
        print(e.stdout)
        return 10
    except Exception as e:
        print("Error:", e)
        return 11


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
