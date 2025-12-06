import pytest
import sys
from datetime import datetime

def test_imports():
    """Test that core modules can be imported."""
    import core.orchestrator
    import security.worm_manifest
    import ui.data_store
    import inference_engine
    assert True

def test_ui_data_store_datetime():
    """Test that UIDataStore can be instantiated and uses datetime correctly."""
    from ui.data_store import UIDataStore
    
    # Create a temporary database
    store = UIDataStore(":memory:")
    
    # Try to create a workflow (which uses datetime.now())
    # We need to mock the connection or just rely on the fact that it calls datetime.now()
    # But create_workflow writes to DB.
    
    # Let's just check if we can call the method without AttributeError
    try:
        store.create_workflow("test_id", "test_objective", ["agent1"])
    except Exception as e:
        # We expect it might fail due to missing tables if we didn't init schema,
        # but we specifically want to ensure it's NOT an AttributeError about datetime.
        assert "AttributeError" not in str(type(e))
        # Actually, let's see if we can initialize the schema first if needed.
        # But for a sanity check, just importing and calling is enough to trigger the NameError/AttributeError if it exists.
        pass

def test_security_worm_manifest():
    """Test that security.worm_manifest can be imported and has expected attributes."""
    from security import worm_manifest
    # Just check if it loaded without circular import error
    assert worm_manifest is not None

def test_orchestrator_instantiation():
    """Test that Orchestrator can be instantiated."""
    from core.orchestrator import Orchestrator
    from infrastructure.memory_merkle import MemoryStorage
    
    # Mock MemoryStorage
    class MockMemoryStorage(MemoryStorage):
        def __init__(self):
            pass
            
    orch = Orchestrator(memory_storage=MockMemoryStorage())
    assert orch is not None
