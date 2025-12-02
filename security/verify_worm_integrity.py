#!/usr/bin/env python3
"""
WORM USB Integrity Verification Tool
=====================================

Verifies the integrity of ORKASTRATOR WORM USB keys by:
1. Checking read-only permissions
2. Validating file hashes against manifest
3. Verifying root hash integrity
4. Checking for unauthorized modifications

Usage:
    python verify_worm_integrity.py /path/to/ORKASTRATOR_WORM
"""

import hashlib
import json
import sys
from pathlib import Path
from typing import Dict, Tuple


class WORMVerifier:
    """Verifies WORM USB integrity."""

    def __init__(self, worm_path: str):
        """Initialize verifier.

        Args:
            worm_path: Path to ORKASTRATOR_WORM directory
        """
        self.worm_path = Path(worm_path)
        if not self.worm_path.exists():
            raise ValueError(f"WORM path does not exist: {worm_path}")
        if not self.worm_path.is_dir():
            raise ValueError(f"WORM path is not a directory: {worm_path}")

        self.manifest_path = self.worm_path / "MANIFEST.json"
        if not self.manifest_path.exists():
            raise ValueError(f"MANIFEST.json not found in {worm_path}")

    def verify(self) -> Tuple[bool, Dict[str, any]]:
        """Perform full verification.

        Returns:
            (success, results_dict)
        """
        print("=" * 70)
        print("🔍 WORM USB Integrity Verification")
        print("=" * 70)
        print(f"\nVerifying: {self.worm_path}")
        print()

        results = {
            "worm_path": str(self.worm_path),
            "checks": {}
        }

        # Load manifest
        print("📋 Loading manifest...")
        try:
            with open(self.manifest_path, 'r') as f:
                manifest = json.load(f)
            print(f"   ✓ Manifest loaded")
            print(f"   ✓ Created: {manifest.get('created', 'unknown')}")
            print(f"   ✓ Version: {manifest.get('version', 'unknown')}")
            print(f"   ✓ Total files: {manifest.get('total_files', 0)}")
            results['manifest'] = manifest
        except Exception as e:
            print(f"   ✗ Failed to load manifest: {e}")
            results['checks']['manifest_load'] = False
            return False, results

        results['checks']['manifest_load'] = True

        # Check 1: Read-only permissions
        print("\n🔒 Checking read-only permissions...")
        ro_check = self._verify_read_only()
        results['checks']['read_only'] = ro_check
        if ro_check:
            print("   ✓ All files are read-only")
        else:
            print("   ✗ Some files are writable (SECURITY RISK)")

        # Check 2: File existence
        print("\n📁 Verifying file existence...")
        file_hashes = manifest.get('file_hashes', {})
        missing_files = []
        for rel_path in file_hashes.keys():
            full_path = self.worm_path / rel_path
            if not full_path.exists():
                missing_files.append(rel_path)

        if missing_files:
            print(f"   ✗ Missing files: {len(missing_files)}")
            for f in missing_files[:5]:  # Show first 5
                print(f"      - {f}")
            results['checks']['file_existence'] = False
            results['missing_files'] = missing_files
        else:
            print(f"   ✓ All {len(file_hashes)} files present")
            results['checks']['file_existence'] = True

        # Check 3: File hash validation
        print("\n🔍 Validating file hashes...")
        hash_mismatches = []
        verified_count = 0

        for rel_path, expected_hash in file_hashes.items():
            full_path = self.worm_path / rel_path
            if not full_path.exists():
                continue  # Already reported as missing

            actual_hash = self._hash_file(full_path)
            if actual_hash != expected_hash:
                hash_mismatches.append({
                    'file': rel_path,
                    'expected': expected_hash,
                    'actual': actual_hash
                })
            else:
                verified_count += 1

            # Progress indicator
            progress = (verified_count + len(hash_mismatches)) / len(file_hashes) * 100
            print(f"   Progress: {progress:.1f}%", end='\r')

        print()  # New line after progress

        if hash_mismatches:
            print(f"   ✗ Hash mismatches: {len(hash_mismatches)}")
            for mismatch in hash_mismatches[:5]:  # Show first 5
                print(f"      - {mismatch['file']}")
                print(f"        Expected: {mismatch['expected'][:16]}...")
                print(f"        Actual:   {mismatch['actual'][:16]}...")
            results['checks']['file_hashes'] = False
            results['hash_mismatches'] = hash_mismatches
        else:
            print(f"   ✓ All {verified_count} file hashes verified")
            results['checks']['file_hashes'] = True

        # Check 4: Root hash validation
        print("\n🌳 Verifying root hash...")
        expected_root = manifest.get('root_hash')
        actual_root = self._calculate_root_hash(file_hashes, actual_hashes=True)

        if actual_root == expected_root:
            print(f"   ✓ Root hash matches")
            print(f"     {expected_root[:32]}...")
            results['checks']['root_hash'] = True
        else:
            print(f"   ✗ Root hash mismatch (TAMPERING DETECTED)")
            print(f"     Expected: {expected_root[:32]}...")
            print(f"     Actual:   {actual_root[:32]}...")
            results['checks']['root_hash'] = False

        # Check 5: Unexpected files
        print("\n📦 Checking for unexpected files...")
        all_files = set()
        for file_path in self.worm_path.rglob("*"):
            if file_path.is_file() and file_path.name != "MANIFEST.json":
                rel_path = str(file_path.relative_to(self.worm_path))
                all_files.add(rel_path)

        expected_files = set(file_hashes.keys())
        unexpected_files = all_files - expected_files

        if unexpected_files:
            print(f"   ⚠️  Unexpected files found: {len(unexpected_files)}")
            for f in list(unexpected_files)[:5]:  # Show first 5
                print(f"      - {f}")
            results['checks']['unexpected_files'] = False
            results['unexpected_files'] = list(unexpected_files)
        else:
            print(f"   ✓ No unexpected files")
            results['checks']['unexpected_files'] = True

        # Summary
        print("\n" + "=" * 70)
        all_passed = all(results['checks'].values())
        if all_passed:
            print("✅ VERIFICATION PASSED - WORM USB is intact")
        else:
            print("❌ VERIFICATION FAILED - WORM USB may be compromised")

        print("\nCheck Results:")
        for check, passed in results['checks'].items():
            status = "✓" if passed else "✗"
            print(f"  {status} {check.replace('_', ' ').title()}")

        print("=" * 70)
        print()

        return all_passed, results

    def _verify_read_only(self) -> bool:
        """Verify all files are read-only."""
        for path in self.worm_path.rglob("*"):
            mode = path.stat().st_mode & 0o777
            if path.is_file() and mode != 0o444:
                return False
            if path.is_dir() and mode != 0o555:
                return False
        return True

    @staticmethod
    def _hash_file(path: Path) -> str:
        """Compute SHA256 hash of a file."""
        h = hashlib.sha256()
        with open(path, 'rb') as f:
            while chunk := f.read(8192):
                h.update(chunk)
        return h.hexdigest()

    def _calculate_root_hash(self, file_hashes: Dict[str, str],
                            actual_hashes: bool = False) -> str:
        """Calculate root hash from file hashes.

        Args:
            file_hashes: Expected file hashes from manifest
            actual_hashes: If True, recompute hashes from actual files
        """
        if actual_hashes:
            # Recompute from actual files
            computed_hashes = {}
            for rel_path in file_hashes.keys():
                full_path = self.worm_path / rel_path
                if full_path.exists():
                    computed_hashes[rel_path] = self._hash_file(full_path)
            file_hashes = computed_hashes

        h = hashlib.sha256()
        for path in sorted(file_hashes.keys()):
            h.update(path.encode())
            h.update(file_hashes[path].encode())
        return h.hexdigest()


def _default_worm_path() -> str:
    try:
        from security.worm_paths import resolve_worm_root  # type: ignore
        return resolve_worm_root()
    except Exception:
        return "/Volumes/NO NAME/ORKASTRATOR_WORM"


def main():
    """Main entry point."""
    if len(sys.argv) < 2:
        worm_path = _default_worm_path()
        print(f"Using default WORM path: {worm_path}")
    else:
        worm_path = sys.argv[1]

    try:
        verifier = WORMVerifier(worm_path)
        success, results = verifier.verify()

        # Exit code
        sys.exit(0 if success else 1)

    except Exception as e:
        print(f"\n❌ Error: {e}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
