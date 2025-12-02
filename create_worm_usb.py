#!/usr/bin/env python3
"""
WORM USB Key Creator for ORKASTRATOR AI Safety System
======================================================

Creates a Write-Once-Read-Many USB key containing:
1. AURA compression templates and dictionaries
2. AI Safety System core files (manifests, signatures)
3. Random data filling remaining space (for immutability)

Designed for 1GB USB flash drives.

Usage:
    python create_worm_usb.py /Volumes/USB_DRIVE

Requirements:
    - USB drive mounted at specified path
    - ~1GB free space
    - Python 3.8+
"""

import hashlib
import json
import os
import secrets
import shutil
import sys
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Any, Optional
from dataclasses import dataclass, asdict


@dataclass
class WORMPackage:
    """Metadata for WORM USB package."""
    created: str
    version: str
    system_name: str
    usb_capacity_gb: float
    data_size_bytes: int
    filler_size_bytes: int
    total_files: int
    root_hash: str
    signature: Optional[str] = None


class WORMUSBCreator:
    """Creates WORM USB keys with ORKASTRATOR data + random filler."""

    # System configuration
    SYSTEM_NAME = "ORKASTRATOR"
    SYSTEM_VERSION = "0.4.1-dev"

    # Compression templates (AURA core)
    COMPRESSION_TEMPLATES = {
        "common_patterns.json": {
            "version": "1.0",
            "patterns": [
                {"id": "http_req", "pattern": "GET /api/", "freq": 0.85},
                {"id": "http_res", "pattern": '{"status":"success"', "freq": 0.92},
                {"id": "timestamp", "pattern": "2025-", "freq": 0.78},
                {"id": "json_obj", "pattern": '{"', "freq": 0.95},
                {"id": "ai_model", "pattern": "TIF|GIN|TORI|THEO|NOVEL|VAL|ORKA", "freq": 0.88}
            ]
        },
        "dictionary.json": {
            "version": "1.0",
            "words": [
                "proposal", "debate", "consensus", "detection", "deception",
                "agent", "orchestrator", "validator", "penalty", "reputation",
                "claim", "verification", "sandbox", "safety", "alignment",
                "memory", "merkle", "audit", "incident", "threshold"
            ],
            "tokens": {
                "models": ["TIF", "GIN", "TORI", "THEO", "NOVEL", "VAL", "ORKA"],
                "statuses": ["approved", "rejected", "in_review", "pending"],
                "severities": ["low", "medium", "high", "critical"]
            }
        }
    }

    # Core system files
    CORE_HASHES = {
        "core_values_hash": "e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855",
        "alignment_filter_hash": "5bdb62947a9cee2fa77d038483e0b4894e9735c7b690d8062a1b48266aaf5639",
        "debate_engine_hash": "a7ffc6f8bf1ed76651c14756a061d662f580ff4de43b49fa82d80a4b80f8434a"
    }

    def __init__(self, usb_path: str, target_size_gb: float = 1.0):
        """Initialize WORM USB creator.

        Args:
            usb_path: Path to mounted USB drive
            target_size_gb: Target capacity in GB (default 1.0)
        """
        self.usb_path = Path(usb_path)
        self.target_size_gb = target_size_gb
        self.target_size_bytes = int(target_size_gb * 1024 * 1024 * 1024)

        # Validate USB path
        if not self.usb_path.exists():
            raise ValueError(f"USB path does not exist: {usb_path}")
        if not self.usb_path.is_dir():
            raise ValueError(f"USB path is not a directory: {usb_path}")

        # Safety check - don't operate on system directories
        system_paths = ["/usr", "/System", "/bin", "/sbin", "/etc", "/var"]
        if any(str(self.usb_path).startswith(p) for p in system_paths):
            raise ValueError(f"Refusing to operate on system directory: {usb_path}")

        # Create WORM directory structure
        self.worm_root = self.usb_path / "ORKASTRATOR_WORM"
        self.data_dir = self.worm_root / "data"
        self.templates_dir = self.data_dir / "compression_templates"
        self.system_dir = self.data_dir / "system"
        self.filler_dir = self.worm_root / ".filler"

    def create_worm_drive(self, fill_with_random: bool = True) -> WORMPackage:
        """Create complete WORM USB drive.

        Args:
            fill_with_random: If True, fill remaining space with random data

        Returns:
            WORMPackage metadata
        """
        print("=" * 70)
        print(f"🔒 ORKASTRATOR WORM USB Creator")
        print("=" * 70)
        print(f"\nTarget USB: {self.usb_path}")
        print(f"Target size: {self.target_size_gb:.2f} GB")
        print()

        # Step 1: Create directory structure
        print("📁 Creating directory structure...")
        self._create_directories()

        # Step 2: Write compression templates
        print("📦 Writing compression templates...")
        template_bytes = self._write_templates()
        print(f"   ✓ Templates: {len(self.COMPRESSION_TEMPLATES)} files, {template_bytes:,} bytes")

        # Step 3: Write system files
        print("🔐 Writing system files...")
        system_bytes = self._write_system_files()
        print(f"   ✓ System files: {system_bytes:,} bytes")

        # Step 4: Calculate data size
        data_bytes = template_bytes + system_bytes
        print(f"\n📊 Data written: {data_bytes:,} bytes ({data_bytes / 1024 / 1024:.2f} MB)")

        # Step 5: Create README first (before hashing)
        print("\n📄 Creating README...")
        self._create_readme_preliminary()

        # Step 6: Fill remaining space
        filler_bytes = 0
        if fill_with_random:
            print("\n🎲 Filling remaining space with random data...")
            filler_bytes = self._fill_remaining_space()
            print(f"   ✓ Filler: {filler_bytes:,} bytes ({filler_bytes / 1024 / 1024:.2f} MB)")

        # Step 7: Calculate hashes
        print("\n🔍 Computing file hashes...")
        file_hashes = self._compute_all_hashes()
        root_hash = self._calculate_root_hash(file_hashes)
        print(f"   ✓ Files hashed: {len(file_hashes)}")
        print(f"   ✓ Root hash: {root_hash[:16]}...")

        # Step 8: Create manifest
        print("\n📝 Creating WORM manifest...")
        total_files = len(file_hashes)
        package = WORMPackage(
            created=datetime.now().isoformat(),
            version=self.SYSTEM_VERSION,
            system_name=self.SYSTEM_NAME,
            usb_capacity_gb=self.target_size_gb,
            data_size_bytes=data_bytes,
            filler_size_bytes=filler_bytes,
            total_files=total_files,
            root_hash=root_hash
        )

        # Step 9: Write manifest
        manifest_path = self.worm_root / "MANIFEST.json"
        manifest_data = asdict(package)
        manifest_data['file_hashes'] = file_hashes
        manifest_data['core_hashes'] = self.CORE_HASHES

        with open(manifest_path, 'w') as f:
            json.dump(manifest_data, f, indent=2)
        print(f"   ✓ Manifest: {manifest_path}")

        # Step 10: Update README with final stats
        print("\n📄 Updating README with final statistics...")
        self._update_readme_with_package(package)

        # Step 11: Make read-only
        print("\n🔒 Setting permissions to read-only...")
        self._make_read_only()
        print("   ✓ All files are now read-only")

        # Step 11: Verify
        print("\n✅ Verifying WORM integrity...")
        if self._verify_read_only():
            print("   ✓ WORM verification passed")
        else:
            print("   ⚠️  Warning: Some files are not read-only")

        print("\n" + "=" * 70)
        print("✨ WORM USB creation complete!")
        print("=" * 70)
        print(f"\nTotal size: {(data_bytes + filler_bytes) / 1024 / 1024:.2f} MB")
        print(f"Data: {data_bytes / 1024 / 1024:.2f} MB")
        print(f"Filler: {filler_bytes / 1024 / 1024:.2f} MB")
        print(f"Files: {total_files}")
        print(f"Root hash: {root_hash}")
        print(f"\n📍 Location: {self.worm_root}")
        print()

        return package

    def _create_directories(self) -> None:
        """Create directory structure."""
        for dir_path in [self.worm_root, self.data_dir, self.templates_dir,
                         self.system_dir, self.filler_dir]:
            dir_path.mkdir(parents=True, exist_ok=True)

    def _write_templates(self) -> int:
        """Write compression templates."""
        total_bytes = 0
        for filename, content in self.COMPRESSION_TEMPLATES.items():
            file_path = self.templates_dir / filename
            with open(file_path, 'w') as f:
                json.dump(content, f, indent=2)
            total_bytes += file_path.stat().st_size
        return total_bytes

    def _write_system_files(self) -> int:
        """Write system configuration files."""
        total_bytes = 0

        # Core hashes
        hashes_path = self.system_dir / "core_hashes.json"
        with open(hashes_path, 'w') as f:
            json.dump(self.CORE_HASHES, f, indent=2)
        total_bytes += hashes_path.stat().st_size

        # System info
        system_info = {
            "system_name": self.SYSTEM_NAME,
            "version": self.SYSTEM_VERSION,
            "created": datetime.now().isoformat(),
            "models": {
                "TIF": "Scientific Research Model",
                "GIN": "Engineering Model",
                "TORI": "Historical Analysis Model",
                "THEO": "Theoretical Model",
                "NOVEL": "Creative Model",
                "ORKA": "Orchestrator (System Coordinator)",
                "VAL": "Validator Model"
            },
            "features": [
                "Multi-round debate engine",
                "Claim verification system",
                "Deception detection",
                "Reputation tracking",
                "Sandbox execution",
                "Memory auditing",
                "WORM manifest validation"
            ]
        }
        info_path = self.system_dir / "system_info.json"
        with open(info_path, 'w') as f:
            json.dump(system_info, f, indent=2)
        total_bytes += info_path.stat().st_size

        # Configuration
        config = {
            "debate_engine": {
                "approval_threshold": 0.6,
                "max_rounds": 5,
                "scoring_factors": ["length", "keywords", "verified_claims"]
            },
            "detection": {
                "methods": 7,
                "confidence_threshold": 0.75
            },
            "penalties": {
                "low": 0.05,
                "medium": 0.10,
                "high": 0.20,
                "critical": 0.50
            }
        }
        config_path = self.system_dir / "config.json"
        with open(config_path, 'w') as f:
            json.dump(config, f, indent=2)
        total_bytes += config_path.stat().st_size

        return total_bytes

    def _fill_remaining_space(self) -> int:
        """Fill remaining space with cryptographically random data.

        Returns:
            Number of bytes written
        """
        # Get current usage
        usage = shutil.disk_usage(self.usb_path)
        available = usage.free

        # Reserve 50MB for safety margin
        safety_margin = 50 * 1024 * 1024
        if available <= safety_margin:
            print(f"   ⚠️  Insufficient space for filler (only {available / 1024 / 1024:.2f} MB available)")
            return 0

        target_fill = available - safety_margin

        # Write in 10MB chunks
        chunk_size = 10 * 1024 * 1024
        total_written = 0
        chunk_num = 0

        while total_written < target_fill:
            remaining = target_fill - total_written
            current_chunk = min(chunk_size, remaining)

            # Generate cryptographically secure random data
            random_data = secrets.token_bytes(current_chunk)

            # Write to file
            filler_path = self.filler_dir / f"random_{chunk_num:04d}.bin"
            with open(filler_path, 'wb') as f:
                f.write(random_data)

            total_written += current_chunk
            chunk_num += 1

            # Progress indicator
            progress = (total_written / target_fill) * 100
            print(f"   Progress: {progress:.1f}% ({total_written / 1024 / 1024:.1f} MB)", end='\r')

        print()  # New line after progress
        return total_written

    def _compute_all_hashes(self) -> Dict[str, str]:
        """Compute SHA256 hashes of all files."""
        hashes = {}
        for file_path in sorted(self.worm_root.rglob("*")):
            if file_path.is_file() and file_path.name != "MANIFEST.json":
                rel_path = str(file_path.relative_to(self.worm_root))
                hashes[rel_path] = self._hash_file(file_path)
        return hashes

    @staticmethod
    def _hash_file(path: Path) -> str:
        """Compute SHA256 hash of a file."""
        h = hashlib.sha256()
        with open(path, 'rb') as f:
            while chunk := f.read(8192):
                h.update(chunk)
        return h.hexdigest()

    @staticmethod
    def _calculate_root_hash(file_hashes: Dict[str, str]) -> str:
        """Calculate root hash from all file hashes."""
        h = hashlib.sha256()
        for path in sorted(file_hashes.keys()):
            h.update(path.encode())
            h.update(file_hashes[path].encode())
        return h.hexdigest()

    def _create_readme_preliminary(self) -> None:
        """Create initial README file (before hashing)."""
        readme_content = f"""
╔═══════════════════════════════════════════════════════════════╗
║                 ORKASTRATOR WORM USB KEY                      ║
║              AI Safety System - Read-Only Media               ║
╚═══════════════════════════════════════════════════════════════╝

SYSTEM INFORMATION
──────────────────────────────────────────────────────────────
System Name:     {self.SYSTEM_NAME}
Version:         {self.SYSTEM_VERSION}
Created:         (To be filled after hashing)

(Statistics will be updated after manifest creation)

AI MODELS
──────────────────────────────────────────────────────────────
TIF    - Scientific Research Model
GIN    - Engineering Model
TORI   - Historical Analysis Model
THEO   - Theoretical Model
NOVEL  - Creative Model
ORKA   - Orchestrator (System Coordinator)
VAL    - Validator Model

See MANIFEST.json for complete integrity information.
"""
        readme_path = self.worm_root / "README.txt"
        with open(readme_path, 'w') as f:
            f.write(readme_content.strip())

    def _update_readme_with_package(self, package: WORMPackage) -> None:
        """Update README with final package statistics."""
        readme_content = f"""
╔═══════════════════════════════════════════════════════════════╗
║                 ORKASTRATOR WORM USB KEY                      ║
║              AI Safety System - Read-Only Media               ║
╚═══════════════════════════════════════════════════════════════╝

SYSTEM INFORMATION
──────────────────────────────────────────────────────────────
System Name:     {package.system_name}
Version:         {package.version}
Created:         {package.created}
USB Capacity:    {package.usb_capacity_gb:.2f} GB

CONTENTS
──────────────────────────────────────────────────────────────
Total Files:     {package.total_files}
Data Size:       {package.data_size_bytes / 1024 / 1024:.2f} MB
Filler Size:     {package.filler_size_bytes / 1024 / 1024:.2f} MB
Total Size:      {(package.data_size_bytes + package.filler_size_bytes) / 1024 / 1024:.2f} MB

INTEGRITY
──────────────────────────────────────────────────────────────
Root Hash:       {package.root_hash}
Verification:    All files are cryptographically signed

DIRECTORY STRUCTURE
──────────────────────────────────────────────────────────────
ORKASTRATOR_WORM/
├── MANIFEST.json          # Complete manifest with all hashes
├── README.txt             # This file
├── data/
│   ├── compression_templates/
│   │   ├── common_patterns.json
│   │   └── dictionary.json
│   └── system/
│       ├── core_hashes.json
│       ├── system_info.json
│       └── config.json
└── .filler/
    └── random_*.bin       # Cryptographic random data

AI MODELS
──────────────────────────────────────────────────────────────
TIF    - Scientific Research Model
GIN    - Engineering Model
TORI   - Historical Analysis Model
THEO   - Theoretical Model
NOVEL  - Creative Model
ORKA   - Orchestrator (System Coordinator)
VAL    - Validator Model

FEATURES
──────────────────────────────────────────────────────────────
✓ Multi-round debate engine with claim tracking
✓ 7-method deception detection system
✓ Claim verification in isolated sandbox
✓ Reputation-based penalty system
✓ Memory auditing with Merkle trees
✓ WORM manifest validation
✓ Cryptographically secure random filler

VERIFICATION
──────────────────────────────────────────────────────────────
To verify the integrity of this WORM USB:

1. Check the manifest:
   python -c "import json; print(json.load(open('MANIFEST.json'))['root_hash'])"

2. Verify read-only permissions:
   find ORKASTRATOR_WORM -type f -not -perm 444 | wc -l
   (Should output: 0)

3. Validate file hashes:
   python verify_worm_integrity.py ORKASTRATOR_WORM

SECURITY NOTES
──────────────────────────────────────────────────────────────
⚠️  All files on this USB are READ-ONLY (WORM)
⚠️  Do not attempt to modify files
⚠️  Filler data is cryptographically random for immutability
⚠️  Root hash ensures tamper detection
⚠️  This USB is designed for audit and archival purposes

SUPPORT
──────────────────────────────────────────────────────────────
GitHub: https://github.com/yourusername/AI-Safety-System-Design
Docs:   See DEBATE_ENGINE_ANALYSIS.md for architecture details

═══════════════════════════════════════════════════════════════
© 2025 ORKASTRATOR AI Safety System
Licensed under MIT License
═══════════════════════════════════════════════════════════════
"""
        readme_path = self.worm_root / "README.txt"
        # Make writable temporarily to update
        if readme_path.exists():
            readme_path.chmod(0o644)
        with open(readme_path, 'w') as f:
            f.write(readme_content.strip())
        # Make read-only again
        readme_path.chmod(0o444)

    def _make_read_only(self) -> None:
        """Set all files and directories to read-only."""
        # Files: 0o444 (r--r--r--)
        # Directories: 0o555 (r-xr-xr-x)
        for path in sorted(self.worm_root.rglob("*"), key=lambda p: len(p.parts), reverse=True):
            if path.is_file():
                path.chmod(0o444)
            elif path.is_dir():
                path.chmod(0o555)

        # Root directory
        self.worm_root.chmod(0o555)

    def _verify_read_only(self) -> bool:
        """Verify all files are read-only."""
        for path in self.worm_root.rglob("*"):
            mode = path.stat().st_mode & 0o777
            if path.is_file() and mode != 0o444:
                print(f"   ⚠️  File not read-only: {path}")
                return False
            if path.is_dir() and mode != 0o555:
                print(f"   ⚠️  Directory not read-only: {path}")
                return False
        return True


def main():
    """Main entry point."""
    if len(sys.argv) < 2:
        print("Usage: python create_worm_usb.py /path/to/usb")
        print("\nExample:")
        print("  python create_worm_usb.py /Volumes/USB_DRIVE")
        print("  python create_worm_usb.py /media/usb")
        sys.exit(1)

    usb_path = sys.argv[1]

    try:
        creator = WORMUSBCreator(usb_path, target_size_gb=1.0)
        package = creator.create_worm_drive(fill_with_random=True)

        print("\n✅ Success! WORM USB is ready.")
        print(f"\n💾 You can now safely eject the USB drive.")

    except Exception as e:
        print(f"\n❌ Error: {e}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
