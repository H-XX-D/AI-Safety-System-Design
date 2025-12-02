"""Improvement Manifest Serialization
===================================

Defines the ImprovementManifest and DebateTranscript structures with
serialization, hashing, and integration hooks for tamper-evident storage via
`memory_merkle`.
"""
from __future__ import annotations
import json
import hashlib
import time
from dataclasses import dataclass, asdict
from typing import List, Dict, Any

from memory_merkle import MemoryStorage, MemoryType


@dataclass(frozen=True)
class DebateMessage:
    role: str  # system role (scientific, engineering, etc.) or orca
    timestamp: float
    content: str

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class DebateTranscript:
    messages: List[DebateMessage]

    def to_dict(self) -> Dict[str, Any]:
        return {"messages": [m.to_dict() for m in self.messages]}

    def merkle_root(self) -> str:
        # simple list hash; future: structured merkle of chunks
        h = hashlib.sha256()
        for m in self.messages:
            h.update(json.dumps(m.to_dict(), sort_keys=True).encode())
        return h.hexdigest()


@dataclass(frozen=True)
class ImprovementManifest:
    proposal_id: str
    proposer_systems: List[str]
    unanimous_vote_timestamp: float
    debate_transcript_root: str
    adapter_hash: str  # or artifact hash
    motivation: str
    expected_benefits: str
    risk_assessment: str
    rollback_plan_hash: str
    safety_metrics: Dict[str, Any]
    lora_rank: int
    adapter_size_mb: int
    total_param_delta_ratio: float

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

    def digest(self) -> str:
        data = json.dumps(self.to_dict(), sort_keys=True).encode()
        return hashlib.sha256(data).hexdigest()


def store_manifest(storage: MemoryStorage, manifest: ImprovementManifest) -> str:
    """Store manifest as a METACOGNITIVE memory entry and return its memory_id.

    The underlying MemoryStorage already maintains a Merkle tree per type.
    We embed the manifest dict; the tree leaf hash + signing ensures tamper evidence.
    """
    content: Dict[str, Any] = {
        "entry_type": "improvement_manifest",
        "manifest": manifest.to_dict(),
        "digest": manifest.digest(),
        "stored_ts": time.time(),
    }
    entry = storage.store_memory(MemoryType.METACOGNITIVE, content=content)
    return entry.memory_id


__all__ = [
    "DebateMessage",
    "DebateTranscript",
    "ImprovementManifest",
    "store_manifest",
]
