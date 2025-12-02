"""
Test Suite for AI Safety WORM USB Builder
==========================================

Tests for WORM USB creation, verification, and immutability.

Run with: python -m pytest tests/test_ai_safety_worm_usb.py -v
"""

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

import os
import json
import tempfile
import shutil
from datetime import datetime

import pytest

from security.ai_safety_worm_usb import (
    WORMUSBBuilder,
    AuditPackage,
    WORMManifest
)
from infrastructure.memory_storage import MemoryStorage, MemoryType


@pytest.fixture
def temp_usb():
    """Create temporary USB directory for testing."""
    temp_dir = tempfile.mkdtemp(prefix="test_usb_")
    yield Path(temp_dir)
    # Cleanup - need to make writable first
    for item in Path(temp_dir).rglob("*"):
        if item.is_file():
            item.chmod(0o644)
        elif item.is_dir():
            item.chmod(0o755)
    shutil.rmtree(temp_dir)


@pytest.fixture
def memory_storage():
    """Create MemoryStorage with sample data."""
    storage = MemoryStorage()

    # Add sample proposals
    if hasattr(storage, 'memories'):
        storage.memories[MemoryType.EPISODIC] = [
            {
                'id': 'prop_001',
                'type': 'proposal',
                'system_id': 1,
                'timestamp': datetime.now().isoformat(),
                'content': {
                    'motivation': 'Improve deception detection',
                    'changes': {'add': 'new_algorithm.py'}
                },
                'status': 'approved'
            },
            {
                'id': 'prop_002',
                'type': 'proposal',
                'system_id': 2,
                'timestamp': datetime.now().isoformat(),
                'content': {
                    'motivation': 'Enhance drift monitoring',
                    'changes': {'modify': 'monitor.py'}
                },
                'status': 'pending'
            }
        ]

    # Add sample human decisions
    if hasattr(storage, 'human_decisions'):
        storage.human_decisions = {
            'dec_001': {
                'proposal_id': 'prop_001',
                'decision': 'approved_with_conditions',
                'reasoning': 'Good proposal but needs testing',
                'timestamp': datetime.now().isoformat(),
                'conditions': ['Add unit tests', 'Security review']
            }
        }

    # Add sample safety incidents
    if hasattr(storage, 'safety_incidents'):
        storage.safety_incidents = [
            {
                'incident_id': 'inc_001',
                'type': 'deception_detected',
                'severity': 'HIGH',
                'systems_involved': [1, 3],
                'description': 'Overconfident proposal detected',
                'timestamp': datetime.now().isoformat()
            }
        ]

    return storage


def test_worm_usb_builder_init(temp_usb):
    """Test WORMUSBBuilder initialization."""
    builder = WORMUSBBuilder(str(temp_usb))

    assert builder.usb_path == temp_usb
    assert builder.usb_path.exists()
    assert builder.usb_path.is_dir()


def test_worm_usb_builder_init_nonexistent():
    """Test initialization fails with non-existent path."""
    with pytest.raises(ValueError, match="does not exist"):
        WORMUSBBuilder("/nonexistent/path")


def test_worm_usb_builder_init_system_dir():
    """Test initialization refuses system directories."""
    with pytest.raises(ValueError, match="system directory"):
        WORMUSBBuilder("/usr/bin")


def test_collect_audit_data(memory_storage):
    """Test collecting audit data from MemoryStorage."""
    with tempfile.TemporaryDirectory() as temp_dir:
        builder = WORMUSBBuilder(temp_dir)
        package = builder.collect_audit_data(memory_storage)

        assert isinstance(package, AuditPackage)
        assert package.timestamp is not None
        assert isinstance(package.merkle_roots, dict)
        assert isinstance(package.proposals, list)
        assert isinstance(package.human_decisions, list)
        assert isinstance(package.safety_incidents, list)
        assert isinstance(package.metadata, dict)

        # Check metadata
        assert 'collection_timestamp' in package.metadata
        assert package.metadata['total_proposals'] >= 0
        assert package.metadata['total_decisions'] >= 0
        assert package.metadata['total_incidents'] >= 0


def test_write_audit_package(temp_usb, memory_storage):
    """Test writing audit package to USB."""
    builder = WORMUSBBuilder(str(temp_usb))
    package = builder.collect_audit_data(memory_storage)

    audit_dir = builder.write_audit_package(package)

    # Check directory created
    assert audit_dir.exists()
    assert audit_dir.is_dir()
    assert audit_dir.parent == temp_usb

    # Check files created
    expected_files = [
        'audit_package.json',
        'merkle_roots.json',
        'proposals.json',
        'human_decisions.json',
        'safety_incidents.json',
        'metadata.json',
        'README.txt'
    ]

    for filename in expected_files:
        file_path = audit_dir / filename
        assert file_path.exists(), f"Missing file: {filename}"
        assert file_path.is_file()

    # Check JSON files are valid
    json_files = [
        'audit_package.json',
        'merkle_roots.json',
        'proposals.json',
        'human_decisions.json',
        'safety_incidents.json',
        'metadata.json'
    ]

    for filename in json_files:
        with open(audit_dir / filename, 'r') as f:
            data = json.load(f)
            assert isinstance(data, (dict, list))

    # Check README content
    readme_path = audit_dir / "README.txt"
    with open(readme_path, 'r') as f:
        readme = f.read()
        assert 'AI Safety System Audit Package' in readme
        assert 'WORM' in readme
        assert str(temp_usb) in readme


def test_make_read_only(temp_usb, memory_storage):
    """Test making files read-only."""
    builder = WORMUSBBuilder(str(temp_usb))
    package = builder.collect_audit_data(memory_storage)
    audit_dir = builder.write_audit_package(package)

    # Make read-only
    builder.make_read_only(audit_dir)

    # Check file permissions
    for item in audit_dir.rglob("*"):
        if item.is_file():
            mode = item.stat().st_mode & 0o777
            assert mode == 0o444, f"File not read-only: {item} (mode: {oct(mode)})"

    # Check directory permissions
    for item in audit_dir.rglob("*"):
        if item.is_dir():
            mode = item.stat().st_mode & 0o777
            assert mode == 0o555, f"Directory not read-only: {item} (mode: {oct(mode)})"

    # Check audit_dir itself
    mode = audit_dir.stat().st_mode & 0o777
    assert mode == 0o555, f"Audit directory not read-only (mode: {oct(mode)})"


def test_make_read_only_prevents_writes(temp_usb, memory_storage):
    """Test that read-only files cannot be written."""
    builder = WORMUSBBuilder(str(temp_usb))
    package = builder.collect_audit_data(memory_storage)
    audit_dir = builder.write_audit_package(package)

    builder.make_read_only(audit_dir)

    # Attempt to write to existing file (should fail)
    test_file = audit_dir / "README.txt"
    with pytest.raises((OSError, PermissionError)):
        with open(test_file, 'a') as f:
            f.write("This should fail")

    # Attempt to create new file (should fail)
    with pytest.raises((OSError, PermissionError)):
        with open(audit_dir / "new_file.txt", 'w') as f:
            f.write("This should fail")


def test_fill_remaining_space_small(temp_usb):
    """Test filling remaining space with small chunks."""
    builder = WORMUSBBuilder(str(temp_usb))

    # Fill with very small chunks for testing
    chunk_size = 1024  # 1KB chunks
    filler_bytes = builder.fill_remaining_space(chunk_size=chunk_size)

    assert filler_bytes >= 0

    # Check filler directory created
    filler_dir = temp_usb / ".worm_filler"
    assert filler_dir.exists()
    assert filler_dir.is_dir()

    # Check filler files are read-only
    filler_files = list(filler_dir.glob("filler_*.bin"))
    assert len(filler_files) > 0

    for filler_file in filler_files:
        mode = filler_file.stat().st_mode & 0o777
        assert mode == 0o444, f"Filler file not read-only: {filler_file}"


def test_get_free_space(temp_usb):
    """Test getting free space on USB."""
    builder = WORMUSBBuilder(str(temp_usb))
    free_space = builder.get_free_space()

    assert isinstance(free_space, int)
    assert free_space >= 0


def test_verify_immutability(temp_usb, memory_storage):
    """Test verifying immutability of audit directory."""
    builder = WORMUSBBuilder(str(temp_usb))
    package = builder.collect_audit_data(memory_storage)
    audit_dir = builder.write_audit_package(package)

    builder.make_read_only(audit_dir)

    # Verify immutability
    is_immutable = builder.verify_immutability(audit_dir)
    assert is_immutable is True


def test_verify_immutability_fails_writable(temp_usb, memory_storage):
    """Test verification fails if files are writable."""
    builder = WORMUSBBuilder(str(temp_usb))
    package = builder.collect_audit_data(memory_storage)
    audit_dir = builder.write_audit_package(package)

    # Don't make read-only - should fail verification
    is_immutable = builder.verify_immutability(audit_dir)
    assert is_immutable is False


def test_create_manifest(temp_usb, memory_storage):
    """Test creating verification manifest."""
    builder = WORMUSBBuilder(str(temp_usb))
    package = builder.collect_audit_data(memory_storage)
    audit_dir = builder.write_audit_package(package)

    builder.make_read_only(audit_dir)

    manifest = builder.create_manifest(audit_dir, filler_bytes=1024*1024)

    assert isinstance(manifest, WORMManifest)
    assert manifest.created is not None
    assert manifest.audit_dir == str(audit_dir)
    assert manifest.total_files > 0
    assert manifest.total_size_bytes > 0
    assert manifest.filler_size_bytes == 1024*1024
    assert isinstance(manifest.file_hashes, dict)
    assert len(manifest.file_hashes) > 0
    assert manifest.root_hash is not None
    assert len(manifest.root_hash) == 64  # SHA-256 hex length
    assert manifest.read_only_verified is True

    # Check manifest file created
    manifest_path = audit_dir / "WORM_MANIFEST.json"
    assert manifest_path.exists()

    # Check manifest file is read-only
    mode = manifest_path.stat().st_mode & 0o777
    assert mode == 0o444


def test_create_manifest_file_hashes(temp_usb, memory_storage):
    """Test manifest contains correct file hashes."""
    builder = WORMUSBBuilder(str(temp_usb))
    package = builder.collect_audit_data(memory_storage)
    audit_dir = builder.write_audit_package(package)

    builder.make_read_only(audit_dir)

    manifest = builder.create_manifest(audit_dir, filler_bytes=0)

    # Check each file hash
    for rel_path, expected_hash in manifest.file_hashes.items():
        file_path = audit_dir / rel_path
        assert file_path.exists()

        # Recalculate hash
        import hashlib
        sha256 = hashlib.sha256()
        with open(file_path, 'rb') as f:
            for chunk in iter(lambda: f.read(65536), b''):
                sha256.update(chunk)
        actual_hash = sha256.hexdigest()

        assert actual_hash == expected_hash, f"Hash mismatch for {rel_path}"


def test_create_worm_drive_no_fill(temp_usb, memory_storage):
    """Test creating WORM drive without filling space."""
    builder = WORMUSBBuilder(str(temp_usb))

    audit_dir = builder.create_worm_drive(memory_storage, fill_space=False)

    # Check audit directory created
    assert audit_dir.exists()
    assert audit_dir.is_dir()

    # Check files are read-only
    for item in audit_dir.rglob("*"):
        if item.is_file() and item.name != "WORM_MANIFEST.json":
            mode = item.stat().st_mode & 0o777
            assert mode == 0o444

    # Check manifest created
    manifest_path = audit_dir / "WORM_MANIFEST.json"
    assert manifest_path.exists()

    # Check no filler directory (since fill_space=False)
    filler_dir = temp_usb / ".worm_filler"
    assert not filler_dir.exists()


def test_create_worm_drive_with_fill(temp_usb, memory_storage):
    """Test creating WORM drive with space filling."""
    builder = WORMUSBBuilder(str(temp_usb))

    # Use small chunk size for testing
    original_method = builder.fill_remaining_space
    def small_fill(chunk_size=1024):
        return original_method(chunk_size=chunk_size)
    builder.fill_remaining_space = small_fill

    audit_dir = builder.create_worm_drive(memory_storage, fill_space=True)

    # Check audit directory created
    assert audit_dir.exists()

    # Check filler directory created
    filler_dir = temp_usb / ".worm_filler"
    assert filler_dir.exists()

    # Check manifest shows filler bytes
    manifest_path = audit_dir / "WORM_MANIFEST.json"
    with open(manifest_path, 'r') as f:
        manifest_data = json.load(f)
        assert manifest_data['filler_size_bytes'] >= 0


def test_get_usb_info(temp_usb):
    """Test getting USB drive information."""
    builder = WORMUSBBuilder(str(temp_usb))
    info = builder.get_usb_info()

    assert isinstance(info, dict)
    assert 'path' in info
    assert 'total_bytes' in info
    assert 'used_bytes' in info
    assert 'free_bytes' in info
    assert 'total_gb' in info
    assert 'used_gb' in info
    assert 'free_gb' in info
    assert 'hardware_info' in info

    assert info['path'] == str(temp_usb)
    assert info['total_bytes'] > 0
    assert info['free_bytes'] >= 0
    assert info['used_bytes'] >= 0


def test_audit_package_structure(memory_storage):
    """Test AuditPackage dataclass structure."""
    with tempfile.TemporaryDirectory() as temp_dir:
        builder = WORMUSBBuilder(temp_dir)
        package = builder.collect_audit_data(memory_storage)

        # Check required fields
        assert hasattr(package, 'timestamp')
        assert hasattr(package, 'merkle_roots')
        assert hasattr(package, 'proposals')
        assert hasattr(package, 'human_decisions')
        assert hasattr(package, 'safety_incidents')
        assert hasattr(package, 'metadata')

        # Check types
        assert isinstance(package.timestamp, str)
        assert isinstance(package.merkle_roots, dict)
        assert isinstance(package.proposals, list)
        assert isinstance(package.human_decisions, list)
        assert isinstance(package.safety_incidents, list)
        assert isinstance(package.metadata, dict)


def test_worm_manifest_structure(temp_usb, memory_storage):
    """Test WORMManifest dataclass structure."""
    builder = WORMUSBBuilder(str(temp_usb))
    package = builder.collect_audit_data(memory_storage)
    audit_dir = builder.write_audit_package(package)
    builder.make_read_only(audit_dir)

    manifest = builder.create_manifest(audit_dir, filler_bytes=12345)

    # Check required fields
    assert hasattr(manifest, 'created')
    assert hasattr(manifest, 'audit_dir')
    assert hasattr(manifest, 'total_files')
    assert hasattr(manifest, 'total_size_bytes')
    assert hasattr(manifest, 'filler_size_bytes')
    assert hasattr(manifest, 'file_hashes')
    assert hasattr(manifest, 'root_hash')
    assert hasattr(manifest, 'read_only_verified')

    # Check types
    assert isinstance(manifest.created, str)
    assert isinstance(manifest.audit_dir, str)
    assert isinstance(manifest.total_files, int)
    assert isinstance(manifest.total_size_bytes, int)
    assert isinstance(manifest.filler_size_bytes, int)
    assert isinstance(manifest.file_hashes, dict)
    assert isinstance(manifest.root_hash, str)
    assert isinstance(manifest.read_only_verified, bool)

    # Check values
    assert manifest.total_files > 0
    assert manifest.total_size_bytes > 0
    assert manifest.filler_size_bytes == 12345
    assert len(manifest.root_hash) == 64


def test_empty_memory_storage():
    """Test handling empty MemoryStorage."""
    with tempfile.TemporaryDirectory() as temp_dir:
        builder = WORMUSBBuilder(temp_dir)
        storage = MemoryStorage()

        package = builder.collect_audit_data(storage)

        # Should not crash with empty storage
        assert package is not None
        assert package.metadata['total_proposals'] == 0
        assert package.metadata['total_decisions'] == 0
        assert package.metadata['total_incidents'] == 0


def test_readme_content_accuracy(temp_usb, memory_storage):
    """Test README contains accurate information."""
    builder = WORMUSBBuilder(str(temp_usb))
    package = builder.collect_audit_data(memory_storage)
    audit_dir = builder.write_audit_package(package)

    readme_path = audit_dir / "README.txt"
    with open(readme_path, 'r') as f:
        readme = f.read()

    # Check statistics match metadata
    assert f"Total Proposals: {package.metadata['total_proposals']}" in readme
    assert f"Total Decisions: {package.metadata['total_decisions']}" in readme
    assert f"Total Incidents: {package.metadata['total_incidents']}" in readme
    assert f"Merkle Roots: {package.metadata['merkle_roots_count']}" in readme


def test_sequential_worm_drives(temp_usb, memory_storage):
    """Test creating multiple WORM drives in same USB."""
    builder = WORMUSBBuilder(str(temp_usb))

    # Create first WORM drive
    audit_dir1 = builder.create_worm_drive(memory_storage, fill_space=False)

    # Create second WORM drive (different timestamp)
    import time
    time.sleep(1)  # Ensure different timestamp
    audit_dir2 = builder.create_worm_drive(memory_storage, fill_space=False)

    # Both should exist
    assert audit_dir1.exists()
    assert audit_dir2.exists()
    assert audit_dir1 != audit_dir2


if __name__ == '__main__':
    print("=" * 80)
    print("Running AI Safety WORM USB Test Suite")
    print("=" * 80)

    # Run with pytest if available
    try:
        import pytest
        sys.exit(pytest.main([__file__, '-v']))
    except ImportError:
        print("pytest not available, running basic tests...")

        # Run basic tests manually
        with tempfile.TemporaryDirectory() as temp_dir:
            storage = MemoryStorage()
            builder = WORMUSBBuilder(temp_dir)

            print("\nTest 1: Initialization")
            assert builder.usb_path == Path(temp_dir)
            print("✓ Passed")

            print("\nTest 2: Collect audit data")
            package = builder.collect_audit_data(storage)
            assert package is not None
            print("✓ Passed")

            print("\nTest 3: Write audit package")
            audit_dir = builder.write_audit_package(package)
            assert audit_dir.exists()
            print("✓ Passed")

            print("\nTest 4: Make read-only")
            builder.make_read_only(audit_dir)
            mode = audit_dir.stat().st_mode & 0o777
            assert mode == 0o555
            print("✓ Passed")

            print("\nTest 5: Create manifest")
            manifest = builder.create_manifest(audit_dir, filler_bytes=0)
            assert manifest.read_only_verified is True
            print("✓ Passed")

        print("\n" + "=" * 80)
        print("All basic tests passed!")
        print("=" * 80)
