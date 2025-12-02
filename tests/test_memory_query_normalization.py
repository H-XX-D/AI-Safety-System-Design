import json
from memory_merkle import MemoryStorage, MemoryType

def test_query_normalizes_legacy_prefixed_types():
    storage = MemoryStorage(system_id=99, private_key="key99")
    # Directly inject a legacy-formatted leaf (simulate older persisted data)
    legacy_entry: dict[str, object] = {
        "memory_id": "legacy123",
        "memory_type": "MemoryType.METACOGNITIVE",
        "content": {"note": "legacy format"},
        "timestamp": "2030-01-01T00:00:00",
        "system_id": 99,
        "signature": "deadbeef",
        "metadata": {}
    }
    # Store a modern entry for contrast
    _modern = storage.store_memory(memory_type=MemoryType.METACOGNITIVE, content={"note": "modern"})
    # Manually append legacy leaf into the metacognitive tree
    legacy_json = json.dumps(legacy_entry, sort_keys=True)
    tree = storage.trees[MemoryType.METACOGNITIVE]
    tree.add_entry(legacy_json)
    # Query all metacognitive memories
    results = storage.query_memories(memory_type=MemoryType.METACOGNITIVE)
    assert any(m.memory_id == "legacy123" for m in results), "Legacy memory not returned"
    # Ensure normalized type
    assert all(m.memory_type == MemoryType.METACOGNITIVE for m in results), "Normalization failed for prefixed type"


def test_query_normalizes_uppercase_enum_names():
    storage = MemoryStorage(system_id=100, private_key="key100")
    uppercase_entry: dict[str, object] = {
        "memory_id": "upper1",
        "memory_type": "METACOGNITIVE",
        "content": {"note": "uppercase enum name"},
        "timestamp": "2030-01-01T00:00:01",
        "system_id": 100,
        "signature": "cafebabe",
        "metadata": {}
    }
    uppercase_json = json.dumps(uppercase_entry, sort_keys=True)
    tree = storage.trees[MemoryType.METACOGNITIVE]
    tree.add_entry(uppercase_json)
    results = storage.query_memories(memory_type=MemoryType.METACOGNITIVE)
    assert any(m.memory_id == "upper1" for m in results), "Uppercase memory not returned"
    assert all(m.memory_type == MemoryType.METACOGNITIVE for m in results), "Normalization failed for uppercase name"


def test_get_memory_by_id_normalizes():
    storage = MemoryStorage(system_id=101, private_key="key101")
    _modern = storage.store_memory(memory_type=MemoryType.METACOGNITIVE, content={"note": "modern"})
    legacy_entry: dict[str, object] = {
        "memory_id": "legacyXYZ",
        "memory_type": "MemoryType.METACOGNITIVE",
        "content": {"note": "legacy id retrieval"},
        "timestamp": "2030-01-01T00:00:02",
        "system_id": 101,
        "signature": "feedface",
        "metadata": {}
    }
    tree = storage.trees[MemoryType.METACOGNITIVE]
    legacy_json = json.dumps(legacy_entry, sort_keys=True)
    tree.add_entry(legacy_json)
    # memory_index needs mapping to allow get_memory_by_id on legacy manually added leaf
    # Use leaf index = last (modern leaf index was 0)
    storage.memory_index["legacyXYZ"] = (MemoryType.METACOGNITIVE, tree.get_size() - 1)
    fetched = storage.get_memory_by_id("legacyXYZ")
    assert fetched is not None, "Failed to fetch legacy memory by id"
    assert fetched.memory_type == MemoryType.METACOGNITIVE, "Normalization failed in get_memory_by_id"
