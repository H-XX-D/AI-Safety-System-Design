#!/usr/bin/env python3
"""Update WORM USB MANIFEST.json with all current files including AURA templates"""

import json
import hashlib
from pathlib import Path
from datetime import datetime, timezone

def hash_file(file_path: Path) -> str:
    """Calculate SHA-256 hash of a file"""
    h = hashlib.sha256()
    with open(file_path, 'rb') as f:
        while chunk := f.read(8192):
            h.update(chunk)
    return h.hexdigest()

def update_manifest(worm_root: str):
    """Update MANIFEST.json with all files"""

    worm_path = Path(worm_root)

    if not worm_path.exists():
        print(f"Error: {worm_root} does not exist")
        return

    print(f"Scanning {worm_root}...")

    # Collect all files and their hashes
    file_hashes = {}
    total_size = 0
    data_size = 0
    filler_size = 0

    for file_path in sorted(worm_path.rglob("*")):
        if file_path.is_file() and file_path.name != "MANIFEST.json":
            rel_path = str(file_path.relative_to(worm_path))

            # Skip system files but INCLUDE .filler directory
            if file_path.name in ['.DS_Store', 'desktop.ini', 'Thumbs.db', '.Spotlight-V100', '.Trashes']:
                continue
            if rel_path.startswith('.') and not rel_path.startswith('.filler/'):
                continue

            file_hash = hash_file(file_path)
            file_size = file_path.stat().st_size

            file_hashes[rel_path] = file_hash
            total_size += file_size

            if rel_path.startswith(".filler/"):
                filler_size += file_size
            else:
                data_size += file_size

            print(f"  ✓ {rel_path} ({file_size:,} bytes)")

    # Calculate root hash
    h = hashlib.sha256()
    for path in sorted(file_hashes.keys()):
        h.update(path.encode())
        h.update(file_hashes[path].encode())
    root_hash = h.hexdigest()

    # Read core hashes from data/system/core_hashes.json
    core_hashes_path = worm_path / "data/system/core_hashes.json"
    if core_hashes_path.exists():
        with open(core_hashes_path, 'r') as f:
            core_hashes = json.load(f)
    else:
        core_hashes = {
            "core_values_hash": "e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855",
            "alignment_filter_hash": "5bdb62947a9cee2fa77d038483e0b4894e9735c7b690d8062a1b48266aaf5639",
            "debate_engine_hash": "a7ffc6f8bf1ed76651c14756a061d662f580ff4de43b49fa82d80a4b80f8434a"
        }

    # Create manifest
    manifest = {
        "created": datetime.now(timezone.utc).isoformat(),
        "version": "0.4.1-dev",
        "system_name": "ORKASTRATOR",
        "usb_capacity_gb": 1.0,
        "data_size_bytes": data_size,
        "filler_size_bytes": filler_size,
        "total_size_bytes": total_size,
        "total_files": len(file_hashes),
        "root_hash": root_hash,
        "signature": None,
        "file_hashes": file_hashes,
        "core_hashes": core_hashes,
        "aura_methods": {
            "total_methods": 6,
            "template_files": [
                "aura_templates/binary_semantic_templates_65536.json",
                "aura_templates/brio_dictionaries.json",
                "aura_templates/auralite_templates.json",
                "aura_templates/bitpacked_enums.json",
                "aura_templates/method_manifest.json",
                "aura_templates/template_store_65000.json",
                "aura_templates/template_index.json"
            ],
            "manifest_hash": "5105101b8f9fd88f8e302c8de5936bd82a84c226d04f88ebb7391f7b4b9411da"
        }
    }

    # Write manifest
    manifest_path = worm_path / "MANIFEST.json"
    with open(manifest_path, 'w') as f:
        json.dump(manifest, f, indent=2)

    print(f"\n{'='*70}")
    print(f"✅ MANIFEST.json Updated")
    print(f"{'='*70}")
    print(f"Total files: {len(file_hashes)}")
    print(f"Data size: {data_size / (1024*1024):.2f} MB")
    print(f"Filler size: {filler_size / (1024*1024):.2f} MB")
    print(f"Total size: {total_size / (1024*1024):.2f} MB")
    print(f"Root hash: {root_hash[:32]}...")
    print(f"\nMANIFEST written to: {manifest_path}")

if __name__ == "__main__":
    import sys
    try:
        from security.worm_paths import resolve_worm_root  # type: ignore
    except Exception:
        resolve_worm_root = None  # type: ignore

    if len(sys.argv) > 1:
        worm_root = sys.argv[1]
    else:
        worm_root = resolve_worm_root() if resolve_worm_root else "/Volumes/NO NAME/ORKASTRATOR_WORM"

    update_manifest(worm_root)
