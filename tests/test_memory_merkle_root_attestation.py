from infrastructure.memory_merkle import MemoryStorage, MemoryType


def test_signed_root_attestation_and_tamper():
    storage = MemoryStorage(system_id=7, private_key="k7")
    # Store a few memories to build Merkle structure
    for i in range(3):
        storage.store_memory(MemoryType.EPISODIC, content={"session": i, "finding": f"f{i}"})
    signed = storage.get_signed_root(MemoryType.EPISODIC)
    assert signed['memory_type'] == 'episodic'
    assert signed['root_hash'] is not None
    assert signed['size'] == 3
    assert storage.verify_signed_root(signed) is True

    # Tamper: modify size field
    tampered = dict(signed)
    tampered['size'] = 99
    assert storage.verify_signed_root(tampered) is False

    # Append new memory; old signed root should now fail state match
    storage.store_memory(MemoryType.EPISODIC, content={"session": 3, "finding": "f3"})
    assert storage.verify_signed_root(signed) is False
