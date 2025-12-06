import pytest
import tempfile
import os
from pathlib import Path
from security.ai_safety_worm_usb import WORMUSBBuilder
from infrastructure.memory_merkle import MemoryStorage

def test_worm_usb_builder_creation():
    """Test that WORMUSBBuilder can be instantiated and create a drive."""
    with tempfile.TemporaryDirectory() as temp_dir:
        builder = WORMUSBBuilder(temp_dir)
        assert builder.usb_path == Path(temp_dir)
        
        # Create a dummy memory storage
        storage = MemoryStorage(system_id="test", private_key="key")
        
        # Create WORM drive
        audit_dir = builder.create_worm_drive(storage, fill_space=False)
        assert audit_dir.exists()
        assert (audit_dir / "WORM_MANIFEST.json").exists()
