import pytest
from infrastructure.memory_merkle import MemoryStorage, MemoryType
from security import worm_manifest

def test_memory_storage_store_memory():
    """Test storing a memory in MemoryStorage."""
    storage = MemoryStorage(system_id="test_sys", private_key="test_key")
    entry = storage.store_memory(MemoryType.EPISODIC, "test data")
    assert entry is not None
    assert entry.content == "test data"
    assert entry.timestamp is not None

def test_worm_manifest_software_equivalence():
    """Test enabling and disabling software equivalence mode."""
    worm_manifest.disable_software_equivalence_mode()
    assert worm_manifest._software_equivalence_state['enabled'] is False
    
    worm_manifest.enable_software_equivalence_mode(justification="Testing")
    assert worm_manifest._software_equivalence_state['enabled'] is True
    assert worm_manifest._software_equivalence_state['justification'] == "Testing"
    
    worm_manifest.disable_software_equivalence_mode()
    assert worm_manifest._software_equivalence_state['enabled'] is False
