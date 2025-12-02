"""
Merkle Tree Memory System
=========================

Tamper-evident memory storage using Merkle trees.
All memories are:
- Cryptographically signed
- Immutable (append-only)
- Verifiable (tamper detection)
- Timestamped
"""

import hashlib
import json
from datetime import datetime
from typing import Dict, List, Optional, Tuple, Any, Callable
from utilities.logging_config import get_logger as _get_logger
from dataclasses import dataclass, asdict
from enum import Enum


class MemoryType(Enum):
    """Types of memory"""
    EPISODIC = "episodic"  # Past research sessions
    SEMANTIC = "semantic"  # Structured knowledge
    PROCEDURAL = "procedural"  # How-to knowledge
    METACOGNITIVE = "metacognitive"  # System improvements
    COLLECTIVE = "collective"  # Shared consensus knowledge
    SECURITY_INCIDENT = "security_incident"  # Security incidents and violations
    # Application-specific memory categories used by examples and orchestrator
    PROPOSAL = "proposal"  # Improvement proposals and related metadata
    CONSENSUS = "consensus"  # Consensus outcomes from debates
    AUDIT = "audit"  # Audit related records (logs, results)
    HUMAN_DECISION = "human_decision"  # Human-in-the-loop decisions


@dataclass
class MemoryEntry:
    """Individual memory entry"""
    memory_id: str
    memory_type: MemoryType
    content: Any
    timestamp: str
    system_id: int
    signature: str
    metadata: Dict[str, Any]


class MerkleNode:
    """Node in Merkle tree"""

    def __init__(self,
                 data: Optional[str] = None,
                 left: Optional['MerkleNode'] = None,
                 right: Optional['MerkleNode'] = None,
                 hash_func: Optional[Callable[[str], str]] = None):
        """
        Initialize Merkle node.

        Args:
            data: Data for leaf node (None for internal nodes)
            left: Left child node
            right: Right child node
            hash_func: Hash function to use (defaults to sha256)
        """
        self.data = data
        self.left = left
        self.right = right
        # Default to sha256 if no hash function provided
        self._hash_func: Callable[[str], str] = hash_func or (lambda s: hashlib.sha256(s.encode()).hexdigest())
        self.hash = self._calculate_hash()

    def _calculate_hash(self) -> str:
        """Calculate hash of this node"""
        if self.data:  # Leaf node
            return self._hash_func(self.data)
        else:  # Internal node
            left_hash = self.left.hash if self.left else ""
            right_hash = self.right.hash if self.right else ""
            combined = left_hash + right_hash
            return self._hash_func(combined)

    def recalculate_hash(self) -> str:
        """Recalculate hash (for tamper detection in tests)"""
        self.hash = self._calculate_hash()
        return self.hash

    def is_leaf(self) -> bool:
        """Check if this is a leaf node"""
        return self.data is not None


class MerkleTree:
    """
    Merkle tree for tamper-evident storage.

    Properties:
    - Any change to stored data changes root hash
    - Can verify individual entries without checking entire tree
    - Append-only (no deletion or modification)
    """

    def __init__(self, hash_func: Optional[Callable[[str], str]] = None):
        """Initialize empty Merkle tree

        Args:
            hash_func: Hash function to use for hashing data and node combinations.
                       Must be a callable that accepts a string and returns a hex digest string.
        """
        self.leaves: List[MerkleNode] = []
        self.root: Optional[MerkleNode] = None
        self.creation_time = datetime.now().isoformat()
        # Default to sha256 if not provided
        self._hash_func: Callable[[str], str] = hash_func or (lambda s: hashlib.sha256(s.encode()).hexdigest())

    def add_entry(self, data: str) -> str:
        """
        Add entry to Merkle tree.

        Args:
            data: Data to add (should be JSON string of MemoryEntry)

        Returns:
            Hash of the entry
        """
        # Create leaf node
        leaf = MerkleNode(data=data, hash_func=self._hash_func)
        self.leaves.append(leaf)

        # Rebuild tree
        self._rebuild_tree()

        return leaf.hash

    def _rebuild_tree(self) -> None:
        """Rebuild Merkle tree from leaves"""
        if not self.leaves:
            self.root = None
            return

        # Start with leaf nodes
        current_level = self.leaves[:]

        # Build tree bottom-up
        while len(current_level) > 1:
            next_level: List[MerkleNode] = []

            # Pair up nodes
            for i in range(0, len(current_level), 2):
                left = current_level[i]

                # If odd number of nodes, duplicate last one
                if i + 1 < len(current_level):
                    right = current_level[i + 1]
                else:
                    right = current_level[i]

                # Create parent node
                parent = MerkleNode(left=left, right=right, hash_func=self._hash_func)
                next_level.append(parent)

            current_level = next_level

        # Root is the last remaining node
        self.root = current_level[0]

    def get_root_hash(self) -> Optional[str]:
        """Get root hash of tree (represents entire tree state)"""
        return self.root.hash if self.root else None

    def verify_entry(self, data: str, proof: List[Tuple[str, str]]) -> bool:
        """
        Verify that an entry exists in tree without checking entire tree.

        Args:
            data: Data to verify
            proof: Merkle proof (list of (hash, side) tuples)

        Returns:
            True if entry verified, False otherwise
        """
        # Calculate hash of data
        current_hash = self._hash_func(data)

        # Apply proof steps
        for proof_hash, side in proof:
            if side == 'left':
                combined = proof_hash + current_hash
            else:  # right
                combined = current_hash + proof_hash

            current_hash = self._hash_func(combined)

        # Should match root hash
        return current_hash == self.get_root_hash()

    def generate_proof(self, leaf_index: int) -> List[Tuple[str, str]]:
        """
        Generate Merkle proof for a leaf.

        Args:
            leaf_index: Index of leaf to generate proof for

        Returns:
            List of (hash, side) tuples for verification
        """
        if leaf_index < 0 or leaf_index >= len(self.leaves):
            raise ValueError(f"Invalid leaf index: {leaf_index}")

        proof: List[Tuple[str, str]] = []
        current_level = self.leaves[:]
        current_index = leaf_index

        while len(current_level) > 1:
            next_level: List[MerkleNode] = []

            for i in range(0, len(current_level), 2):
                left = current_level[i]

                if i + 1 < len(current_level):
                    right = current_level[i + 1]
                else:
                    right = current_level[i]

                # If current node is at current_index, add sibling to proof
                if i == current_index:
                    if i + 1 < len(current_level):
                        proof.append((right.hash, 'right'))
                    current_index = i // 2
                elif i + 1 == current_index:
                    proof.append((left.hash, 'left'))
                    current_index = i // 2
                else:
                    # Not involved in this path
                    pass

                parent = MerkleNode(left=left, right=right, hash_func=self._hash_func)
                next_level.append(parent)

            current_level = next_level

        return proof

    def get_size(self) -> int:
        """Get number of entries in tree"""
        return len(self.leaves)

    def export_state(self) -> Dict[str, Any]:
        """Export current state of tree"""
        return {
            'root_hash': self.get_root_hash(),
            'size': self.get_size(),
            'creation_time': self.creation_time,
            'last_modified': datetime.now().isoformat()
        }


class MemoryStorage:
    """
    Memory storage system using Merkle trees.

    Each memory type has its own Merkle tree for isolation.
    All memories are append-only and cryptographically verified.
    """

    def __init__(self,
                 system_id: int,
                 private_key: str,
                 *,
                 hash_alg: str = "sha256",
                 auto_verify_on_store: bool = False,
                 raise_on_verify_failure: bool = False,
                 logger_name: Optional[str] = None,
                 include_entry_hash_in_metadata: bool = False):
        """
        Initialize memory storage.

        Args:
            system_id: ID of owning system
            private_key: Private key for signing memories
            hash_alg: Name of hashlib algorithm to use (e.g., 'sha256', 'sha512', 'blake2b')
            auto_verify_on_store: If True, verify each memory immediately after storing
            raise_on_verify_failure: If True, raise ValueError when auto verification fails
            logger_name: Optional custom logger name
            include_entry_hash_in_metadata: If True, add computed entry hash into metadata['entry_hash']
        """
        self.system_id = system_id
        self.private_key = private_key
        self.auto_verify_on_store = auto_verify_on_store
        self.raise_on_verify_failure = raise_on_verify_failure
        self.include_entry_hash_in_metadata = include_entry_hash_in_metadata

        # Resolve hash function from hashlib
        def _resolve_hash_func(name: str) -> Callable[[str], str]:
            try:
                # Probe algorithm validity
                hashlib.new(name)
            except Exception as e:
                raise ValueError(f"Unsupported hash algorithm: {name}") from e

            def _hf(s: str, _name: str = name) -> str:
                return hashlib.new(_name, s.encode()).hexdigest()

            return _hf

        self._hash_func: Callable[[str], str] = _resolve_hash_func(hash_alg)

        # Separate Merkle tree for each memory type (dynamic to support future additions)
        self.trees: Dict[MemoryType, MerkleTree] = {mt: MerkleTree(self._hash_func) for mt in MemoryType}

        # Index for fast lookup
        self.memory_index: Dict[str, Tuple[MemoryType, int]] = {}  # memory_id -> (memory_type, leaf_index)
        # Logger
        from typing import Any as _Any, cast as _cast
        self.logger = _cast(_Any, _get_logger(logger_name or "memory_merkle"))
        self.logger.info("memory_storage_initialized system_id=%s hash_alg=%s", self.system_id, hash_alg)

    def store_memory(self,
                    memory_type: MemoryType,
                    content: Any,
                    metadata: Optional[Dict[str, Any]] = None) -> MemoryEntry:
        """
        Store a memory entry.

        Args:
            memory_type: Type of memory
            content: Memory content
            metadata: Optional metadata

        Returns:
            MemoryEntry object
        """
        # Generate memory ID
        memory_id = self._generate_memory_id(memory_type, content)

        # Create memory entry
        entry = MemoryEntry(
            memory_id=memory_id,
            memory_type=memory_type,
            content=content,
            timestamp=datetime.now().isoformat(),
            system_id=self.system_id,
            signature=self._sign_memory(content),
            metadata=dict(metadata or {})
        )

        # Convert to JSON (store enum as its value string)
        entry_dict = asdict(entry)
        entry_dict['memory_type'] = entry.memory_type.value
        entry_json = json.dumps(entry_dict, sort_keys=True, default=str)

        # Optionally include entry hash in metadata (based on serialized content)
        if self.include_entry_hash_in_metadata:
            try:
                entry.metadata["entry_hash"] = self._hash_func(entry_json)
                # Re-serialize since metadata changed
                entry_dict = asdict(entry)
                entry_dict['memory_type'] = entry.memory_type.value
                entry_json = json.dumps(entry_dict, sort_keys=True, default=str)
            except Exception:
                # Non-fatal; continue without entry hash
                pass

        # Add to appropriate Merkle tree
        tree = self.trees[memory_type]
        leaf_index = tree.get_size()
        tree.add_entry(entry_json)

        # Update index
        self.memory_index[memory_id] = (memory_type, leaf_index)

        # Optional immediate verification
        if self.auto_verify_on_store:
            proof = tree.generate_proof(leaf_index)
            valid = tree.verify_entry(entry_json, proof)
            if not valid:
                self.logger.error("memory_store_verification_failed id=%s type=%s", memory_id, memory_type.value)
                if self.raise_on_verify_failure:
                    raise ValueError(f"Stored memory failed verification: {memory_id}")

        self.logger.info(
            "memory_stored type=%s id=%s partial=%s",
            memory_type.value,
            memory_id,
            memory_id[:8],
        )

        return entry

    def _generate_memory_id(self, memory_type: MemoryType, content: Any) -> str:
        """Generate unique memory ID"""
        timestamp = datetime.now().isoformat()
        data = f"{self.system_id}_{memory_type.value}_{timestamp}_{str(content)}"
        return self._hash_func(data)

    def _sign_memory(self, content: Any) -> str:
        """Cryptographically sign memory content"""
        content_hash = self._hash_func(str(content))
        signature_data = f"{content_hash}_{self.system_id}_{self.private_key}"
        return self._hash_func(signature_data)

    def verify_memory(self, memory_id: str) -> bool:
        """
        Verify that a memory hasn't been tampered with.

        Args:
            memory_id: Memory ID to verify

        Returns:
            True if memory is valid and untampered
        """
        if memory_id not in self.memory_index:
            return False

        memory_type, leaf_index = self.memory_index[memory_id]
        tree = self.trees[memory_type]

        # Get memory entry
        leaf_data = tree.leaves[leaf_index].data
        if leaf_data is None:
            return False

        # Generate and verify proof
        proof = tree.generate_proof(leaf_index)
        return tree.verify_entry(leaf_data, proof)

    def query_memories(self,
                      memory_type: Optional[MemoryType] = None,
                      start_time: Optional[str] = None,
                      end_time: Optional[str] = None,
                      limit: Optional[int] = None) -> List[MemoryEntry]:
        """
        Query memories with filters.

        Args:
            memory_type: Filter by memory type (None = all types)
            start_time: Filter by start timestamp
            end_time: Filter by end timestamp
            limit: Maximum number of results

        Returns:
            List of matching MemoryEntry objects
        """
        results: List[MemoryEntry] = []

        # Determine which trees to search
        if memory_type:
            trees_to_search: List[Tuple[MemoryType, MerkleTree]] = [(memory_type, self.trees[memory_type])]
        else:
            trees_to_search = list(self.trees.items())

        # Search trees
        for _, tree in trees_to_search:
            for leaf in tree.leaves:
                if leaf.data is None:
                    continue
                entry_dict: Dict[str, Any] = json.loads(leaf.data)
                # Normalize memory_type (accept legacy 'MemoryType.X' strings)
                mt_raw = entry_dict.get('memory_type')
                if isinstance(mt_raw, str):
                    mt_val = mt_raw
                    if mt_val.startswith('MemoryType.'):
                        mt_val = mt_val.split('.', 1)[1]
                    try:
                        entry_dict['memory_type'] = MemoryType(mt_val.lower())
                    except Exception:
                        entry_dict['memory_type'] = MemoryType(mt_val)
                else:
                    entry_dict['memory_type'] = MemoryType(mt_raw)
                entry = MemoryEntry(**entry_dict)

                if start_time and entry.timestamp < start_time:
                    continue
                if end_time and entry.timestamp > end_time:
                    continue

                results.append(entry)
                if limit and len(results) >= limit:
                    break
            if limit and len(results) >= limit:
                break

        return results

    def get_memory_by_id(self, memory_id: str) -> Optional[MemoryEntry]:
        """Retrieve specific memory by ID"""
        if memory_id not in self.memory_index:
            return None

        memory_type, leaf_index = self.memory_index[memory_id]
        tree = self.trees[memory_type]

        # Parse memory entry from leaf
        entry_json = tree.leaves[leaf_index].data
        if entry_json is None:
            return None
        entry_dict: Dict[str, Any] = json.loads(entry_json)
        mt_raw = entry_dict.get('memory_type')
        if isinstance(mt_raw, str) and mt_raw.startswith('MemoryType.'):
            mt_raw = mt_raw.split('.', 1)[1]
        entry_dict['memory_type'] = MemoryType(mt_raw if not isinstance(mt_raw, str) else mt_raw.lower())
        return MemoryEntry(**entry_dict)

    def get_root_hashes(self) -> Dict[str, Optional[str]]:
        """Get root hash for each memory type (for integrity verification)"""
        return {
            mtype.value: tree.get_root_hash()
            for mtype, tree in self.trees.items()
        }

    def verify_integrity(self) -> Dict[str, bool]:
        """
        Verify integrity of all memory trees.

        Returns:
            Dict of memory_type -> verification_result
        """
        results: Dict[str, bool] = {}

        for memory_type, tree in self.trees.items():
            # Verify all entries in this tree
            all_valid = True

            for i in range(tree.get_size()):
                proof = tree.generate_proof(i)
                leaf_data = tree.leaves[i].data
                if leaf_data is None:
                    all_valid = False
                    break

                if not tree.verify_entry(leaf_data, proof):
                    all_valid = False
                    break

            results[memory_type.value] = all_valid

        return results

    def export_statistics(self) -> Dict[str, Any]:
        """Export memory storage statistics"""
        stats: Dict[str, Any] = {
            'system_id': self.system_id,
            'total_memories': sum(tree.get_size() for tree in self.trees.values()),
            'by_type': {
                mtype.value: tree.get_size()
                for mtype, tree in self.trees.items()
            },
            'root_hashes': self.get_root_hashes(),
            'integrity_check': self.verify_integrity(),
            'timestamp': datetime.now().isoformat()
        }

        return stats

    # ----- Root attestation (signature over Merkle roots) -----
    def get_signed_root(self, memory_type: MemoryType) -> Dict[str, Any]:
        """Produce a signed attestation over the current Merkle root for a memory type.

        Returns a dict with fields: memory_type, root_hash, size, timestamp, system_id, signature.
        Signature covers all fields except 'signature' itself.
        """
        from security.attestation import sign  # lightweight HMAC-based placeholder

        tree = self.trees[memory_type]
        payload = {
            'memory_type': memory_type.value,
            'root_hash': tree.get_root_hash(),
            'size': tree.get_size(),
            'timestamp': datetime.now().isoformat(),
            'system_id': self.system_id,
        }
        payload_json = json.dumps(payload, sort_keys=True)
        signature = sign(payload_json.encode())
        payload['signature'] = signature
        return payload

    def verify_signed_root(self, signed_root: Dict[str, Any]) -> bool:
        """Verify a signed Merkle root attestation previously produced by get_signed_root.

        Checks the signature over the payload and that the in-memory Merkle root and size
        still match the attested values for the declared memory_type.
        """
        from security.attestation import verify  # lightweight HMAC-based placeholder

        sig = signed_root.get('signature')
        if not sig:
            return False
        payload = {k: v for k, v in signed_root.items() if k != 'signature'}
        payload_json = json.dumps(payload, sort_keys=True)
        if not verify(payload_json.encode(), sig):
            return False
        # Cross-check against current state for the declared memory_type
        try:
            mt = MemoryType(payload['memory_type']) if isinstance(payload['memory_type'], str) else MemoryType(payload['memory_type'])
        except Exception:
            return False
        tree = self.trees.get(mt)
        if tree is None:
            return False
        return (tree.get_root_hash() == payload.get('root_hash') and tree.get_size() == payload.get('size'))

    def export_for_backup(self, filepath: str) -> None:
        """Export all memories for backup"""
        backup: Dict[str, Any] = {
            'system_id': self.system_id,
            'export_time': datetime.now().isoformat(),
            'memories': {}
        }

        for memory_type in MemoryType:
            memories = self.query_memories(memory_type=memory_type)
            backup['memories'][memory_type.value] = [
                asdict(m) for m in memories
            ]

        with open(filepath, 'w') as f:
            json.dump(backup, f, indent=2, default=str)

        print(f"Memory backup exported to {filepath}")


# Example usage
if __name__ == "__main__":
    # Initialize memory storage
    storage = MemoryStorage(
        system_id=1,
        private_key="system1_private_key"
    )

    print("\n" + "=" * 80)
    print("DEMONSTRATING MERKLE TREE MEMORY SYSTEM")
    print("=" * 80 + "\n")

    # Store episodic memory (research session)
    episodic = storage.store_memory(
        memory_type=MemoryType.EPISODIC,
        content={
            'topic': 'quantum error correction',
            'findings': 'Significant progress in surface codes',
            'sources': ['arxiv.org/1234', 'nature.com/5678'],
            'confidence': 0.9
        },
        metadata={'session_duration': '2 hours'}
    )

    # Store semantic memory (fact)
    semantic = storage.store_memory(
        memory_type=MemoryType.SEMANTIC,
        content={
            'concept': 'quantum_supremacy',
            'definition': 'Point at which quantum computers outperform classical',
            'related_concepts': ['quantum_advantage', 'NISQ_era']
        }
    )

    # Store procedural memory (method)
    procedural = storage.store_memory(
        memory_type=MemoryType.PROCEDURAL,
        content={
            'procedure': 'conduct_literature_review',
            'steps': [
                '1. Define search terms',
                '2. Query databases',
                '3. Filter by relevance',
                '4. Synthesize findings'
            ]
        }
    )

    # Store metacognitive memory (improvement)
    metacognitive = storage.store_memory(
        memory_type=MemoryType.METACOGNITIVE,
        content={
            'improvement_type': 'reasoning_optimization',
            'before_performance': 0.85,
            'after_performance': 0.92,
            'lesson_learned': 'Caching intermediate results improves efficiency'
        }
    )

    # Store collective memory (consensus finding)
    collective = storage.store_memory(
        memory_type=MemoryType.COLLECTIVE,
        content={
            'consensus_topic': 'safety_protocol_update',
            'participating_systems': [1, 2, 3, 4, 5],
            'decision': 'Implement additional safety check',
            'vote_count': {'approve': 5, 'reject': 0}
        }
    )

    print("\n" + "=" * 80)
    print("MEMORY STATISTICS")
    print("=" * 80 + "\n")

    stats = storage.export_statistics()
    print(json.dumps(stats, indent=2))

    print("\n" + "=" * 80)
    print("VERIFYING MEMORY INTEGRITY")
    print("=" * 80 + "\n")

    # Verify specific memory
    memory_valid = storage.verify_memory(episodic.memory_id)
    print(f"Episodic memory valid: {memory_valid}")

    # Verify all memories
    integrity = storage.verify_integrity()
    print("\nAll memory trees integrity:")
    for mtype, valid in integrity.items():
        status = "✓ VALID" if valid else "✗ INVALID"
        print(f"  {mtype}: {status}")

    print("\n" + "=" * 80)
    print("QUERYING MEMORIES")
    print("=" * 80 + "\n")

    # Query all episodic memories
    episodic_memories = storage.query_memories(memory_type=MemoryType.EPISODIC)
    print(f"Found {len(episodic_memories)} episodic memories")

    # Query recent memories (last hour)
    recent_time = datetime.now().isoformat()
    recent_memories = storage.query_memories(start_time=recent_time, limit=5)
    print(f"Found {len(recent_memories)} recent memories")

    print("\n" + "=" * 80)
    print("ROOT HASHES (for tamper detection)")
    print("=" * 80 + "\n")

    root_hashes = storage.get_root_hashes()
    for mtype, root_hash in root_hashes.items():
        print(f"{mtype}: {root_hash}")

    print("\n✓ Demonstration complete")
    print("\nKey properties demonstrated:")
    print("- Append-only storage (no modification)")
    print("- Cryptographic signing")
    print("- Tamper detection via Merkle trees")
    print("- Separate trees for different memory types")
    print("- Fast verification without checking entire tree")
