import re
from core.ai_safety_system_core import *  # If needed; not used here
from infrastructure.memory_merkle import MemoryStorage, MemoryType


def test_memory_storage_hash_alg_and_entry_hash_metadata():
    storage = MemoryStorage(
        system_id=123,
        private_key="key",
        hash_alg="sha512",
        include_entry_hash_in_metadata=True,
    )

    entry = storage.store_memory(
        memory_type=MemoryType.SEMANTIC,
        content={"k": "v"},
        metadata={"note": "t"},
    )

    # entry_hash should be present and be a hex digest of sha512 (128 hex chars)
    assert "entry_hash" in entry.metadata
    entry_hash = entry.metadata["entry_hash"]
    assert isinstance(entry_hash, str)
    assert re.fullmatch(r"[0-9a-f]{128}", entry_hash) is not None

    # Root hash for SEMANTIC tree should also be sha512 length
    root_hashes = storage.get_root_hashes()
    assert root_hashes[MemoryType.SEMANTIC.value]
    assert len(root_hashes[MemoryType.SEMANTIC.value]) == 128

    # Verify integrity remains True
    assert storage.verify_integrity()[MemoryType.SEMANTIC.value] is True
