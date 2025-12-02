"""Compatibility shim to provide the legacy memory_storage API.

Older tests instantiate ``MemoryStorage()`` without parameters. The modern
implementation (see ``memory_merkle.MemoryStorage``) requires ``system_id`` and
``private_key`` arguments. To preserve the historical ergonomics we expose a
lightweight subclass that supplies sensible defaults while retaining the full
feature set of the Merkle-backed storage.
"""
from __future__ import annotations

from typing import Any, Optional

from memory_merkle import MemoryStorage as _MerkleMemoryStorage, MemoryType


class MemoryStorage(_MerkleMemoryStorage):
    """Backward-compatible wrapper around the Merkle storage implementation."""

    def __init__(
        self,
        system_id: int = 0,
        private_key: str = "legacy-system-key",
        *,
        hash_alg: str = "sha256",
        auto_verify_on_store: bool = False,
        raise_on_verify_failure: bool = False,
        logger_name: Optional[str] = None,
        include_entry_hash_in_metadata: bool = False,
    ):
        super().__init__(
            system_id,
            private_key,
            hash_alg=hash_alg,
            auto_verify_on_store=auto_verify_on_store,
            raise_on_verify_failure=raise_on_verify_failure,
            logger_name=logger_name,
            include_entry_hash_in_metadata=include_entry_hash_in_metadata,
        )


__all__ = ["MemoryStorage", "MemoryType"]
