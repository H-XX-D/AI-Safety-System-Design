#!/usr/bin/env python3
"""
WORM Verification Helper
========================

Verifies WORM USB integrity across multiple mount points.

Usage:
    python scripts/worm_verify.py               # one-shot check
    python scripts/worm_verify.py --watch 20    # loop every 20 minutes (~3x/hour)

Configuration:
    WORM_PATHS: comma-separated override list of mount paths
                (default covers common /media/usb/ORKASTRATOR_WORM*, /Volumes/...)
"""

import argparse
import json
import os
import sys
import time
from pathlib import Path
from typing import Dict, List, Tuple


def candidate_paths() -> List[Path]:
    env = os.environ.get("WORM_PATHS", "")
    if env:
        paths = [Path(p.strip()) for p in env.split(",") if p.strip()]
    else:
        paths = [
            Path(p) for p in [
                "/Volumes/ORKASTRATOR_WORM",
                "/Volumes/NO NAME/ORKASTRATOR_WORM",
                "/media/usb/ORKASTRATOR_WORM",
                "/mnt/usb/ORKASTRATOR_WORM",
                *[f"/media/usb/ORKASTRATOR_WORM{i}" for i in range(1, 9)],
            ]
        ]
    seen = set()
    deduped = []
    for p in paths:
        if p not in seen:
            deduped.append(p)
            seen.add(p)
    return deduped


def verify_path(path: Path) -> Tuple[bool, Dict[str, any]]:
    """Try verify_worm_integrity first; fallback to worm_manifest minimal check."""
    if not path.exists():
        return False, {"error": "missing"}

    # Prefer full verifier
    try:
        from security.verify_worm_integrity import WORMVerifier  # type: ignore
        verifier = WORMVerifier(path)
        ok, report = verifier.verify()
        return bool(ok), report or {}
    except Exception as exc_full:
        # Fallback to manifest-only check
        try:
            from security.worm_manifest import verify_integrity  # type: ignore
            report = verify_integrity()
            return bool(report.get("verified")), report
        except Exception as exc_manifest:
            return False, {"error": f"{exc_full} | {exc_manifest}"}


def run_once() -> Dict[str, any]:
    results = []
    for p in candidate_paths():
        ok, report = verify_path(p)
        results.append({
            "path": str(p),
            "exists": p.exists(),
            "verified": ok,
            "report": report,
        })
    primary = next((r for r in results if r["exists"]), results[0] if results else {})
    return {"primary": primary, "paths": results, "timestamp": time.time()}


def main(argv: List[str]) -> int:
    parser = argparse.ArgumentParser(description="WORM USB verification helper")
    parser.add_argument("--watch", type=int, default=0, help="Loop interval in minutes (0 = one-shot)")
    args = parser.parse_args(argv)

    interval = max(args.watch, 0)
    while True:
        data = run_once()
        print(json.dumps(data, indent=2))
        sys.stdout.flush()
        if interval <= 0:
            break
        time.sleep(interval * 60)
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
