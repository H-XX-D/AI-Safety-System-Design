import os
import json
from typing import Any

from infrastructure.memory_merkle import MemoryStorage, MemoryType, MerkleTree


def test_placeholder_worm_manifest_structures_exist():
    # Minimal smoke: ensure merkle module present and readable
    assert os.path.exists("memory_merkle.py"), "memory_merkle.py must exist"


def test_merkle_root_changes_on_tamper(tmp_path: Any):
    storage = MemoryStorage(system_id=42, private_key="k")
    # Store two entries (values ignored, just to build tree)
    storage.store_memory(MemoryType.EPISODIC, {"a": 1})
    storage.store_memory(MemoryType.EPISODIC, {"b": 2})
    roots_before = storage.get_root_hashes()
    root_before = roots_before[MemoryType.EPISODIC.value]
    assert root_before is not None

    # Export backup then tamper with a leaf directly
    backup_file = tmp_path / "backup.json"
    storage.export_for_backup(str(backup_file))

    tree: MerkleTree = storage.trees[MemoryType.EPISODIC]
    # Capture old leaf data and proof for index 0
    old_leaf_data = tree.leaves[0].data
    old_proof = tree.generate_proof(0)
    assert tree.leaves[0].data is not None
    tree.leaves[0].data = json.dumps({"tampered": True})  # simulate corruption
    # Recalculate the leaf hash, then rebuild to propagate
    tree.leaves[0].recalculate_hash()
    tree._rebuild_tree()  # type: ignore[attr-defined]

    roots_after = storage.get_root_hashes()
    root_after = roots_after[MemoryType.EPISODIC.value]
    assert root_after is not None
    assert root_after != root_before, "Merkle root should change after tampering"

    # Old proof should no longer verify after tampering
    assert old_leaf_data is not None
    assert tree.verify_entry(old_leaf_data, old_proof) is False
