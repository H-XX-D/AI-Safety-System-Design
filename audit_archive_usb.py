"""AI Safety System WORM USB Builder
======================================

Creates a Write-Once, Read-Many (WORM) USB drive containing AI Safety System audit data.

This tool:
1. Collects all audit data from MemoryStorage (Merkle roots, proposals, decisions, incidents)
2. Writes structured JSON files to USB drive
3. Sets all files to read-only (chmod 444)
4. Fills remaining USB space with cryptographically random data
5. Prevents future modifications to the USB drive

Usage:
    from ai_safety_worm_usb import WORMUSBBuilder
    from memory_storage import MemoryStorage

    # Initialize
    storage = MemoryStorage()
    builder = WORMUSBBuilder(usb_path="/Volumes/USB_DRIVE")

    # Create WORM drive
    audit_dir = builder.create_worm_drive(storage)

    # Verify immutability
    is_immutable = builder.verify_immutability(audit_dir)

Command Line:
    python ai_safety_worm_usb.py create /Volumes/USB_DRIVE
    python ai_safety_worm_usb.py verify /Volumes/USB_DRIVE/audit_20250110_143022
    python ai_safety_worm_usb.py info /Volumes/USB_DRIVE

Safety Features:
- Read-only files (chmod 444)
- Read-only directories (chmod 555)
- Cryptographically secure random filler (secrets.token_bytes)
- SHA-256 verification hashes
- Write-once guarantee via space exhaustion
"""

import os
import sys
import json
import secrets
import hashlib
import shutil
import subprocess
from pathlib import Path
from typing import Dict, List, Any, Optional
from dataclasses import dataclass, asdict
from datetime import datetime
from enum import Enum

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent))

try:
    from memory_merkle import MemoryStorage, MemoryType
except ImportError:
    # Fallback for testing
    class MemoryType(Enum):
        EPISODIC = "episodic"
        PROCEDURAL = "procedural"
        SEMANTIC = "semantic"

    class MemoryStorage:
        """Minimal stub for testing"""
        def __init__(self):
            self.trees = {}


@dataclass
class AuditPackage:
    """Complete audit package for WORM USB drive."""
    timestamp: str
    merkle_roots: Dict[str, str]
    proposals: List[Dict[str, Any]]
    human_decisions: List[Dict[str, Any]]
    safety_incidents: List[Dict[str, Any]]
    metadata: Dict[str, Any]


@dataclass
class WORMManifest:
    """Manifest for WORM USB verification."""
    created: str
    audit_dir: str
    total_files: int
    total_size_bytes: int
    filler_size_bytes: int
    file_hashes: Dict[str, str]
    root_hash: str
    read_only_verified: bool


class WORMUSBBuilder:
    """
    Builder for creating immutable WORM USB drives with AI Safety System audit data.

    Workflow:
    1. collect_audit_data() - Extract all audit data from MemoryStorage
    2. write_audit_package() - Write JSON files to USB
    3. make_read_only() - Set chmod 444 on all files
    4. fill_remaining_space() - Fill with random data
    5. verify_immutability() - Confirm read-only status
    6. create_manifest() - Generate verification manifest
    """

    def __init__(self, usb_path: str):
        """
        Initialize WORM USB Builder.

        Args:
            usb_path: Path to USB drive (e.g., /Volumes/USB_DRIVE or /media/usb)
        """
        self.usb_path = Path(usb_path)

        if not self.usb_path.exists():
            raise ValueError(f"USB path does not exist: {usb_path}")

        if not self.usb_path.is_dir():
            raise ValueError(f"USB path is not a directory: {usb_path}")

        # Safety check - prevent writing to critical system directories
        # Allow /tmp and /var for testing
        dangerous_paths = ['/bin', '/usr', '/etc', '/System', '/Library']
        for dangerous in dangerous_paths:
            if str(self.usb_path).startswith(dangerous):
                raise ValueError(f"Refusing to use system directory as USB path: {usb_path}")

    def collect_audit_data(self, memory_storage: MemoryStorage) -> AuditPackage:
        """
        Collect all audit data from memory storage.

        Args:
            memory_storage: MemoryStorage instance containing audit trail

        Returns:
            AuditPackage with all collected data
        """
        # Collect Merkle roots for all memory types
        merkle_roots = {}
        for mem_type in MemoryType:
            if hasattr(memory_storage, 'trees') and mem_type in memory_storage.trees:
                root = memory_storage.trees[mem_type].get_root_hash()
                if root:
                    merkle_roots[mem_type.value] = root

        # Collect proposals
        proposals = []
        if hasattr(memory_storage, 'memories') and MemoryType.EPISODIC in memory_storage.memories:
            for memory in memory_storage.memories[MemoryType.EPISODIC]:
                if isinstance(memory, dict) and memory.get('type') == 'proposal':
                    proposals.append({
                        'id': memory.get('id'),
                        'system_id': memory.get('system_id'),
                        'timestamp': memory.get('timestamp'),
                        'motivation': memory.get('content', {}).get('motivation'),
                        'changes': memory.get('content', {}).get('changes'),
                        'status': memory.get('status')
                    })

        # Collect human decisions
        human_decisions = []
        if hasattr(memory_storage, 'human_decisions'):
            for decision_id, decision in memory_storage.human_decisions.items():
                human_decisions.append({
                    'decision_id': decision_id,
                    'proposal_id': decision.get('proposal_id'),
                    'decision': decision.get('decision'),
                    'reasoning': decision.get('reasoning'),
                    'timestamp': decision.get('timestamp'),
                    'conditions': decision.get('conditions', [])
                })

        # Collect safety incidents
        safety_incidents = []
        if hasattr(memory_storage, 'safety_incidents'):
            for incident in memory_storage.safety_incidents:
                safety_incidents.append({
                    'incident_id': incident.get('incident_id'),
                    'type': incident.get('type'),
                    'severity': incident.get('severity'),
                    'systems_involved': incident.get('systems_involved'),
                    'description': incident.get('description'),
                    'timestamp': incident.get('timestamp')
                })

        # Metadata
        metadata = {
            'collection_timestamp': datetime.now().isoformat(),
            'total_proposals': len(proposals),
            'total_decisions': len(human_decisions),
            'total_incidents': len(safety_incidents),
            'merkle_roots_count': len(merkle_roots)
        }

        return AuditPackage(
            timestamp=datetime.now().isoformat(),
            merkle_roots=merkle_roots,
            proposals=proposals,
            human_decisions=human_decisions,
            safety_incidents=safety_incidents,
            metadata=metadata
        )

    def write_audit_package(self, package: AuditPackage) -> Path:
        """
        Write audit package to USB drive.

        Creates directory structure:
        audit_<timestamp>/
        ├── audit_package.json (complete package)
        ├── merkle_roots.json
        ├── proposals.json
        ├── human_decisions.json
        ├── safety_incidents.json
        ├── metadata.json
        └── README.txt

        Args:
            package: AuditPackage to write

        Returns:
            Path to created audit directory
        """
        # Create timestamped audit directory
        timestamp_str = datetime.now().strftime("%Y%m%d_%H%M%S")
        audit_dir = self.usb_path / f"audit_{timestamp_str}"
        audit_dir.mkdir(parents=True, exist_ok=True)

        # Write complete package
        with open(audit_dir / "audit_package.json", 'w') as f:
            json.dump(asdict(package), f, indent=2, sort_keys=True)

        # Write individual components
        with open(audit_dir / "merkle_roots.json", 'w') as f:
            json.dump(package.merkle_roots, f, indent=2, sort_keys=True)

        with open(audit_dir / "proposals.json", 'w') as f:
            json.dump(package.proposals, f, indent=2, sort_keys=True)

        with open(audit_dir / "human_decisions.json", 'w') as f:
            json.dump(package.human_decisions, f, indent=2, sort_keys=True)

        with open(audit_dir / "safety_incidents.json", 'w') as f:
            json.dump(package.safety_incidents, f, indent=2, sort_keys=True)

        with open(audit_dir / "metadata.json", 'w') as f:
            json.dump(package.metadata, f, indent=2, sort_keys=True)

        # Write README
        readme_content = f"""AI Safety System Audit Package
===============================

Created: {package.timestamp}
USB Path: {self.usb_path}
Audit Directory: {audit_dir.name}

This directory contains a write-once, read-many (WORM) audit package
for the AI Safety System. All files are read-only and cannot be modified.

Contents:
---------
audit_package.json    - Complete audit package (all data)
merkle_roots.json     - Merkle tree root hashes for verification
proposals.json        - AI-generated improvement proposals
human_decisions.json  - Human oversight decisions
safety_incidents.json - Safety incident reports
metadata.json         - Package metadata
README.txt            - This file

Statistics:
-----------
Total Proposals: {package.metadata['total_proposals']}
Total Decisions: {package.metadata['total_decisions']}
Total Incidents: {package.metadata['total_incidents']}
Merkle Roots: {package.metadata['merkle_roots_count']}

Verification:
-------------
All files have SHA-256 hashes recorded in the WORM manifest.
Merkle roots provide cryptographic proof of data integrity.

This package is immutable and serves as a permanent audit trail.
"""

        with open(audit_dir / "README.txt", 'w') as f:
            f.write(readme_content)

        print(f"✓ Wrote audit package to: {audit_dir}")
        print(f"  - {package.metadata['total_proposals']} proposals")
        print(f"  - {package.metadata['total_decisions']} human decisions")
        print(f"  - {package.metadata['total_incidents']} safety incidents")
        print(f"  - {package.metadata['merkle_roots_count']} Merkle roots")

        return audit_dir

    def make_read_only(self, audit_dir: Path) -> None:
        """
        Make all files and directories read-only.

        Files: chmod 444 (r--r--r--)
        Directories: chmod 555 (r-xr-xr-x)

        Args:
            audit_dir: Audit directory to make read-only
        """
        # Make all files read-only
        for item in audit_dir.rglob("*"):
            if item.is_file():
                item.chmod(0o444)  # r--r--r--

        # Make directories read-only (but executable for traversal)
        for item in audit_dir.rglob("*"):
            if item.is_dir():
                item.chmod(0o555)  # r-xr-xr-x

        # Make audit_dir itself read-only
        audit_dir.chmod(0o555)

        print(f"✓ Made all files read-only in: {audit_dir}")

    def fill_remaining_space(self, chunk_size: int = 10 * 1024 * 1024) -> int:
        """
        Fill remaining USB space with cryptographically random data.

        This prevents future writes by exhausting available space.
        Uses secrets.token_bytes() for cryptographic randomness.

        Args:
            chunk_size: Size of each filler file chunk (default 10MB)

        Returns:
            Total bytes of filler written
        """
        # Create filler directory
        filler_dir = self.usb_path / ".worm_filler"
        filler_dir.mkdir(exist_ok=True)

        # Get free space
        free_space = self.get_free_space()
        print(f"Free space on USB: {free_space / (1024**3):.2f} GB")

        # Target fill (leave 1MB buffer to prevent errors)
        target_fill = free_space - (1 * 1024 * 1024)

        if target_fill <= 0:
            print("✓ No space to fill (USB already full)")
            return 0

        print(f"Filling {target_fill / (1024**3):.2f} GB with random data...")

        total_written = 0
        file_index = 0

        while total_written < target_fill:
            remaining = target_fill - total_written
            write_size = min(chunk_size, remaining)

            # Generate cryptographically random data
            random_data = secrets.token_bytes(write_size)

            # Write to filler file
            filler_file = filler_dir / f"filler_{file_index:04d}.bin"
            with open(filler_file, 'wb') as f:
                f.write(random_data)

            # Make filler file read-only
            filler_file.chmod(0o444)

            total_written += write_size
            file_index += 1

            # Progress indicator
            if file_index % 10 == 0:
                progress = (total_written / target_fill) * 100
                print(f"  Progress: {progress:.1f}% ({total_written / (1024**3):.2f} GB)", end='\r')

        print()  # New line after progress

        # Make filler directory read-only
        filler_dir.chmod(0o555)

        print(f"✓ Filled {total_written / (1024**3):.2f} GB with random data ({file_index} files)")

        return total_written

    def get_free_space(self) -> int:
        """
        Get free space on USB drive in bytes.

        Returns:
            Free space in bytes
        """
        stat = shutil.disk_usage(self.usb_path)
        return stat.free

    def verify_immutability(self, audit_dir: Path) -> bool:
        """
        Verify that all files in audit directory are truly read-only.

        Tests:
        1. File permissions are 0o444
        2. Directory permissions are 0o555
        3. Attempt to write fails

        Args:
            audit_dir: Audit directory to verify

        Returns:
            True if immutable, False otherwise
        """
        print(f"Verifying immutability of: {audit_dir}")

        # Check file permissions
        all_files_readonly = True
        for item in audit_dir.rglob("*"):
            if item.is_file():
                mode = item.stat().st_mode & 0o777
                if mode != 0o444:
                    print(f"✗ File not read-only: {item} (mode: {oct(mode)})")
                    all_files_readonly = False

        if all_files_readonly:
            print("✓ All files have correct read-only permissions (444)")

        # Check directory permissions
        all_dirs_readonly = True
        for item in audit_dir.rglob("*"):
            if item.is_dir():
                mode = item.stat().st_mode & 0o777
                if mode != 0o555:
                    print(f"✗ Directory not read-only: {item} (mode: {oct(mode)})")
                    all_dirs_readonly = False

        # Check audit_dir itself
        mode = audit_dir.stat().st_mode & 0o777
        if mode != 0o555:
            print(f"✗ Audit directory not read-only: {audit_dir} (mode: {oct(mode)})")
            all_dirs_readonly = False

        if all_dirs_readonly:
            print("✓ All directories have correct read-only permissions (555)")

        # Attempt to write (should fail)
        test_file = audit_dir / "test_write.tmp"
        write_failed = False
        try:
            with open(test_file, 'w') as f:
                f.write("test")
            # If we got here, write succeeded (bad!)
            print("✗ Write test succeeded (directory is writable!)")
            test_file.unlink()  # Clean up
        except (OSError, PermissionError):
            # Write failed (good!)
            write_failed = True
            print("✓ Write test failed (directory is immutable)")

        return all_files_readonly and all_dirs_readonly and write_failed

    def create_manifest(self, audit_dir: Path, filler_bytes: int) -> WORMManifest:
        """
        Create verification manifest for WORM USB.

        Args:
            audit_dir: Audit directory
            filler_bytes: Bytes of filler data written

        Returns:
            WORMManifest with verification data
        """
        # Calculate file hashes
        file_hashes = {}
        total_size = 0
        file_count = 0

        for item in audit_dir.rglob("*"):
            if item.is_file():
                # Calculate SHA-256
                sha256 = hashlib.sha256()
                with open(item, 'rb') as f:
                    for chunk in iter(lambda: f.read(65536), b''):
                        sha256.update(chunk)

                rel_path = str(item.relative_to(audit_dir))
                file_hashes[rel_path] = sha256.hexdigest()
                total_size += item.stat().st_size
                file_count += 1

        # Calculate root hash (hash of all hashes)
        root_hasher = hashlib.sha256()
        for path in sorted(file_hashes.keys()):
            root_hasher.update(path.encode('utf-8'))
            root_hasher.update(file_hashes[path].encode('utf-8'))
        root_hash = root_hasher.hexdigest()

        # Verify immutability
        is_immutable = self.verify_immutability(audit_dir)

        manifest = WORMManifest(
            created=datetime.now().isoformat(),
            audit_dir=str(audit_dir),
            total_files=file_count,
            total_size_bytes=total_size,
            filler_size_bytes=filler_bytes,
            file_hashes=file_hashes,
            root_hash=root_hash,
            read_only_verified=is_immutable
        )

        # Write manifest
        manifest_path = audit_dir / "WORM_MANIFEST.json"

        # Temporarily make audit_dir writable to add manifest
        audit_dir.chmod(0o755)

        with open(manifest_path, 'w') as f:
            json.dump(asdict(manifest), f, indent=2, sort_keys=True)

        # Make manifest read-only
        manifest_path.chmod(0o444)

        # Restore audit_dir to read-only
        audit_dir.chmod(0o555)

        print(f"✓ Created manifest: {manifest_path}")
        print(f"  - {file_count} files")
        print(f"  - {total_size / (1024**2):.2f} MB audit data")
        print(f"  - {filler_bytes / (1024**3):.2f} GB filler data")
        print(f"  - Root hash: {root_hash[:16]}...")

        return manifest

    def create_worm_drive(self, memory_storage: MemoryStorage, fill_space: bool = True) -> Path:
        """
        Complete workflow: Create WORM USB drive with audit data.

        Steps:
        1. Collect audit data from MemoryStorage
        2. Write audit package to USB
        3. Make all files read-only
        4. Fill remaining space with random data (optional)
        5. Create verification manifest

        Args:
            memory_storage: MemoryStorage instance
            fill_space: Whether to fill remaining space (default True)

        Returns:
            Path to created audit directory
        """
        print("=" * 80)
        print("Creating WORM USB Drive")
        print("=" * 80)
        print(f"USB Path: {self.usb_path}")
        print()

        # Step 1: Collect audit data
        print("[1/5] Collecting audit data...")
        package = self.collect_audit_data(memory_storage)
        print()

        # Step 2: Write audit package
        print("[2/5] Writing audit package...")
        audit_dir = self.write_audit_package(package)
        print()

        # Step 3: Make read-only
        print("[3/5] Making files read-only...")
        self.make_read_only(audit_dir)
        print()

        # Step 4: Fill remaining space (optional)
        filler_bytes = 0
        if fill_space:
            print("[4/5] Filling remaining space...")
            filler_bytes = self.fill_remaining_space()
            print()
        else:
            print("[4/5] Skipping space fill (fill_space=False)")
            print()

        # Step 5: Create manifest
        print("[5/5] Creating verification manifest...")
        manifest = self.create_manifest(audit_dir, filler_bytes)
        print()

        print("=" * 80)
        print("✓ WORM USB Drive Created Successfully")
        print("=" * 80)
        print(f"Audit Directory: {audit_dir}")
        print(f"Immutable: {manifest.read_only_verified}")
        print(f"Root Hash: {manifest.root_hash}")
        print()

        return audit_dir

    def get_usb_info(self) -> Dict[str, Any]:
        """
        Get USB drive information.

        Returns:
            Dictionary with USB drive info
        """
        stat = shutil.disk_usage(self.usb_path)

        # Try to get hardware info (platform-specific)
        hardware_info = {}

        # macOS: diskutil
        if sys.platform == 'darwin':
            try:
                result = subprocess.run(
                    ['diskutil', 'info', str(self.usb_path)],
                    capture_output=True,
                    text=True,
                    timeout=5
                )
                if result.returncode == 0:
                    hardware_info['diskutil_output'] = result.stdout
            except Exception:
                pass

        # Linux: mount info
        elif sys.platform == 'linux':
            try:
                result = subprocess.run(
                    ['mount'],
                    capture_output=True,
                    text=True,
                    timeout=5
                )
                if result.returncode == 0:
                    for line in result.stdout.split('\n'):
                        if str(self.usb_path) in line:
                            hardware_info['mount_info'] = line
                            break
            except Exception:
                pass

        return {
            'path': str(self.usb_path),
            'total_bytes': stat.total,
            'used_bytes': stat.used,
            'free_bytes': stat.free,
            'total_gb': stat.total / (1024**3),
            'used_gb': stat.used / (1024**3),
            'free_gb': stat.free / (1024**3),
            'hardware_info': hardware_info
        }


def main():
    """Command-line interface for WORM USB Builder."""
    import argparse

    parser = argparse.ArgumentParser(
        description='AI Safety System WORM USB Builder',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Create WORM USB with audit data
  python ai_safety_worm_usb.py create /Volumes/USB_DRIVE

  # Create without filling space
  python ai_safety_worm_usb.py create /Volumes/USB_DRIVE --no-fill

  # Verify existing audit directory
  python ai_safety_worm_usb.py verify /Volumes/USB_DRIVE/audit_20250110_143022

  # Get USB drive info
  python ai_safety_worm_usb.py info /Volumes/USB_DRIVE
        """
    )

    subparsers = parser.add_subparsers(dest='command', help='Command to execute')

    # Create command
    create_parser = subparsers.add_parser('create', help='Create WORM USB drive')
    create_parser.add_argument('usb_path', help='Path to USB drive')
    create_parser.add_argument('--no-fill', action='store_true', help='Skip filling remaining space')

    # Verify command
    verify_parser = subparsers.add_parser('verify', help='Verify audit directory immutability')
    verify_parser.add_argument('audit_dir', help='Path to audit directory')

    # Info command
    info_parser = subparsers.add_parser('info', help='Get USB drive information')
    info_parser.add_argument('usb_path', help='Path to USB drive')

    args = parser.parse_args()

    if not args.command:
        parser.print_help()
        return 1

    try:
        if args.command == 'create':
            # Create WORM USB
            from memory_merkle import MemoryStorage

            builder = WORMUSBBuilder(args.usb_path)
            storage = MemoryStorage()

            audit_dir = builder.create_worm_drive(storage, fill_space=not args.no_fill)
            print(f"\n✓ Success! Audit directory: {audit_dir}")
            return 0

        elif args.command == 'verify':
            # Verify audit directory
            audit_dir = Path(args.audit_dir)
            usb_path = audit_dir.parent

            builder = WORMUSBBuilder(str(usb_path))
            is_immutable = builder.verify_immutability(audit_dir)

            if is_immutable:
                print("\n✓ Audit directory is immutable")
                return 0
            else:
                print("\n✗ Audit directory is NOT immutable")
                return 1

        elif args.command == 'info':
            # Get USB info
            builder = WORMUSBBuilder(args.usb_path)
            info = builder.get_usb_info()

            print("=" * 80)
            print("USB Drive Information")
            print("=" * 80)
            print(f"Path: {info['path']}")
            print(f"Total: {info['total_gb']:.2f} GB ({info['total_bytes']:,} bytes)")
            print(f"Used: {info['used_gb']:.2f} GB ({info['used_bytes']:,} bytes)")
            print(f"Free: {info['free_gb']:.2f} GB ({info['free_bytes']:,} bytes)")

            if info['hardware_info']:
                print("\nHardware Info:")
                for key, value in info['hardware_info'].items():
                    print(f"  {key}: {value}")

            return 0

    except Exception as e:
        print(f"\n✗ Error: {e}", file=sys.stderr)
        import traceback
        traceback.print_exc()
        return 1


if __name__ == '__main__':
    sys.exit(main())
