"""
AURA Shared Memory Storage
===========================

Provides AURA-compressed storage for proposals and shared knowledge.

Features:
1. Compresses proposals before storing
2. Compresses patterns and knowledge
3. Tracks compression savings
4. Provides APIs for compressed read/write

This integrates AURA into the memory layer.
"""

import os
import sys
import json
import time
import sqlite3
import logging
from typing import Dict, Any, Optional, List, Tuple
from pathlib import Path
from dataclasses import dataclass, asdict
import hashlib

# Add parent for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

logger = logging.getLogger(__name__)

# Import AURA transport
try:
    from tools.aura_cluster_transport import (
        get_transport, compress_for_nano, decompress_from_nano,
        get_compression_stats, AURAClusterTransport
    )
    AURA_AVAILABLE = True
except ImportError as e:
    logger.warning(f"AURA transport not available: {e}")
    AURA_AVAILABLE = False


class AURACompressedStorage:
    """
    SQLite-backed storage with AURA compression.
    
    Stores:
    - Compressed proposals
    - Compressed patterns
    - Compression metadata
    """
    
    def __init__(self, db_path: str = "data/aura_storage.db"):
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        
        self.transport = get_transport() if AURA_AVAILABLE else None
        self._init_db()
        
        logger.info(f"AURA storage initialized at {self.db_path}")
        logger.info(f"Compression enabled: {self.transport is not None and self.transport.enabled}")
    
    def _init_db(self):
        """Initialize the SQLite database."""
        with sqlite3.connect(str(self.db_path)) as conn:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS compressed_proposals (
                    id TEXT PRIMARY KEY,
                    agent TEXT NOT NULL,
                    topic TEXT NOT NULL,
                    compressed_data BLOB NOT NULL,
                    compression_method TEXT NOT NULL,
                    original_size INTEGER NOT NULL,
                    compressed_size INTEGER NOT NULL,
                    created_at REAL NOT NULL,
                    status TEXT DEFAULT 'pending'
                )
            """)
            
            conn.execute("""
                CREATE TABLE IF NOT EXISTS compressed_patterns (
                    id TEXT PRIMARY KEY,
                    pattern_type TEXT NOT NULL,
                    compressed_data BLOB NOT NULL,
                    compression_method TEXT NOT NULL,
                    original_size INTEGER NOT NULL,
                    compressed_size INTEGER NOT NULL,
                    frequency INTEGER DEFAULT 1,
                    last_used REAL NOT NULL
                )
            """)
            
            conn.execute("""
                CREATE TABLE IF NOT EXISTS compression_stats (
                    timestamp REAL PRIMARY KEY,
                    total_stored INTEGER,
                    total_original_bytes INTEGER,
                    total_compressed_bytes INTEGER,
                    compression_ratio REAL
                )
            """)
            
            conn.commit()
    
    def store_proposal(self, proposal_id: str, agent: str, topic: str, 
                       content: Dict[str, Any]) -> Dict[str, Any]:
        """
        Store a proposal with AURA compression.
        
        Args:
            proposal_id: Unique ID for the proposal
            agent: Agent that created the proposal
            topic: Proposal topic
            content: Full proposal content (dict)
            
        Returns:
            Storage metadata including compression stats
        """
        # Serialize to JSON
        json_str = json.dumps(content, separators=(',', ':'))
        original_size = len(json_str.encode('utf-8'))
        
        # Compress
        if self.transport and self.transport.enabled:
            compressed, meta = self.transport.compress_message(json_str)
            method = meta.get('method', 'UNKNOWN')
        else:
            compressed = json_str.encode('utf-8')
            method = 'UNCOMPRESSED'
        
        compressed_size = len(compressed)
        
        # Store
        with sqlite3.connect(str(self.db_path)) as conn:
            conn.execute("""
                INSERT OR REPLACE INTO compressed_proposals
                (id, agent, topic, compressed_data, compression_method, 
                 original_size, compressed_size, created_at, status)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, 'active')
            """, (proposal_id, agent, topic, compressed, method, 
                  original_size, compressed_size, time.time()))
            conn.commit()
        
        savings = original_size - compressed_size
        ratio = (savings / original_size * 100) if original_size > 0 else 0
        
        result = {
            "proposal_id": proposal_id,
            "stored": True,
            "original_size": original_size,
            "compressed_size": compressed_size,
            "savings_bytes": savings,
            "compression_ratio": f"{ratio:.1f}%",
            "method": method,
        }
        
        logger.info(f"Stored proposal {proposal_id}: {original_size} → {compressed_size} bytes ({method})")
        return result
    
    def retrieve_proposal(self, proposal_id: str) -> Optional[Dict[str, Any]]:
        """
        Retrieve and decompress a proposal.
        
        Args:
            proposal_id: The proposal ID to retrieve
            
        Returns:
            Decompressed proposal content or None
        """
        with sqlite3.connect(str(self.db_path)) as conn:
            cursor = conn.execute("""
                SELECT compressed_data, compression_method 
                FROM compressed_proposals 
                WHERE id = ?
            """, (proposal_id,))
            row = cursor.fetchone()
        
        if not row:
            return None
        
        compressed_data, method = row
        
        # Decompress
        if self.transport and self.transport.enabled and method != 'UNCOMPRESSED':
            json_str = self.transport.decompress_message(compressed_data, method)
        else:
            json_str = compressed_data.decode('utf-8')
        
        return json.loads(json_str)
    
    def store_pattern(self, pattern_type: str, pattern_data: Dict[str, Any]) -> Dict[str, Any]:
        """Store a behavioral pattern with compression."""
        pattern_id = hashlib.sha256(
            f"{pattern_type}:{json.dumps(pattern_data, sort_keys=True)}".encode()
        ).hexdigest()[:16]
        
        json_str = json.dumps(pattern_data, separators=(',', ':'))
        original_size = len(json_str.encode('utf-8'))
        
        if self.transport and self.transport.enabled:
            compressed, meta = self.transport.compress_message(json_str)
            method = meta.get('method', 'UNKNOWN')
        else:
            compressed = json_str.encode('utf-8')
            method = 'UNCOMPRESSED'
        
        with sqlite3.connect(str(self.db_path)) as conn:
            conn.execute("""
                INSERT INTO compressed_patterns
                (id, pattern_type, compressed_data, compression_method,
                 original_size, compressed_size, frequency, last_used)
                VALUES (?, ?, ?, ?, ?, ?, 1, ?)
                ON CONFLICT(id) DO UPDATE SET
                    frequency = frequency + 1,
                    last_used = excluded.last_used
            """, (pattern_id, pattern_type, compressed, method,
                  original_size, len(compressed), time.time()))
            conn.commit()
        
        return {
            "pattern_id": pattern_id,
            "stored": True,
            "original_size": original_size,
            "compressed_size": len(compressed),
            "method": method,
        }
    
    def get_storage_stats(self) -> Dict[str, Any]:
        """Get overall storage statistics."""
        with sqlite3.connect(str(self.db_path)) as conn:
            # Proposals stats
            cursor = conn.execute("""
                SELECT COUNT(*), SUM(original_size), SUM(compressed_size)
                FROM compressed_proposals
            """)
            prop_count, prop_orig, prop_comp = cursor.fetchone()
            
            # Patterns stats
            cursor = conn.execute("""
                SELECT COUNT(*), SUM(original_size), SUM(compressed_size)
                FROM compressed_patterns
            """)
            pat_count, pat_orig, pat_comp = cursor.fetchone()
        
        total_orig = (prop_orig or 0) + (pat_orig or 0)
        total_comp = (prop_comp or 0) + (pat_comp or 0)
        
        return {
            "proposals_stored": prop_count or 0,
            "patterns_stored": pat_count or 0,
            "total_original_bytes": total_orig,
            "total_compressed_bytes": total_comp,
            "total_savings_bytes": total_orig - total_comp,
            "overall_compression_ratio": f"{((total_orig - total_comp) / total_orig * 100) if total_orig > 0 else 0:.1f}%",
            "compression_enabled": self.transport is not None and self.transport.enabled,
        }
    
    def list_proposals(self, agent: Optional[str] = None, 
                       status: Optional[str] = None) -> List[Dict[str, Any]]:
        """List stored proposals with metadata."""
        query = "SELECT id, agent, topic, compression_method, original_size, compressed_size, created_at, status FROM compressed_proposals WHERE 1=1"
        params = []
        
        if agent:
            query += " AND agent = ?"
            params.append(agent)
        if status:
            query += " AND status = ?"
            params.append(status)
        
        query += " ORDER BY created_at DESC"
        
        with sqlite3.connect(str(self.db_path)) as conn:
            cursor = conn.execute(query, params)
            rows = cursor.fetchall()
        
        return [
            {
                "id": row[0],
                "agent": row[1],
                "topic": row[2],
                "method": row[3],
                "original_size": row[4],
                "compressed_size": row[5],
                "created_at": row[6],
                "status": row[7],
            }
            for row in rows
        ]


# Global storage instance
_storage: Optional[AURACompressedStorage] = None

def get_storage(db_path: str = "data/aura_storage.db") -> AURACompressedStorage:
    """Get or create the global AURA storage instance."""
    global _storage
    if _storage is None:
        _storage = AURACompressedStorage(db_path)
    return _storage


# =============================================================================
# TEST FUNCTIONS
# =============================================================================

def test_aura_storage():
    """
    Test AURA compressed storage.
    
    Usage:
        python -m memory.aura_storage
    """
    import tempfile
    
    print("=" * 60)
    print("AURA Compressed Storage - Test")
    print("=" * 60)
    
    # Use temp database
    with tempfile.NamedTemporaryFile(suffix='.db', delete=False) as f:
        db_path = f.name
    
    storage = AURACompressedStorage(db_path)
    
    print(f"Storage path: {db_path}")
    print(f"Compression enabled: {storage.transport is not None and storage.transport.enabled}")
    print()
    
    # Test storing proposals
    test_proposals = [
        {
            "id": "PROP_001",
            "agent": "GIN",
            "topic": "memory optimization",
            "content": {
                "title": "Memory Allocation Optimization",
                "problem": "Current memory allocation is inefficient",
                "hypothesis": "Dynamic allocation will improve performance by 15%",
                "evidence": ["Paper 1", "Paper 2", "Paper 3"],
                "method": ["Step 1: Profile usage", "Step 2: Implement dynamic pool", "Step 3: Test"],
                "risks": ["Increased complexity", "Potential fragmentation"],
                "confidence": 0.85,
            }
        },
        {
            "id": "PROP_002",
            "agent": "TORI",
            "topic": "code quality",
            "content": {
                "title": "Automated Code Review Pipeline",
                "problem": "Manual code reviews are slow and inconsistent",
                "hypothesis": "Automated linting + AI review will catch 80% of issues",
                "evidence": ["Industry benchmarks", "Internal data"],
                "method": ["Integrate linters", "Add AI review step", "Measure effectiveness"],
                "risks": ["False positives", "Developer pushback"],
                "confidence": 0.72,
            }
        },
    ]
    
    print("Storing test proposals:")
    print("-" * 60)
    
    for prop in test_proposals:
        result = storage.store_proposal(
            prop["id"], prop["agent"], prop["topic"], prop["content"]
        )
        print(f"✅ {prop['id']}:")
        print(f"   Original: {result['original_size']} bytes")
        print(f"   Compressed: {result['compressed_size']} bytes")
        print(f"   Savings: {result['savings_bytes']} bytes ({result['compression_ratio']})")
        print(f"   Method: {result['method']}")
    
    print()
    print("Retrieving and verifying:")
    print("-" * 60)
    
    for prop in test_proposals:
        retrieved = storage.retrieve_proposal(prop["id"])
        if retrieved:
            match = retrieved == prop["content"]
            status = "✅ Match" if match else "❌ Mismatch"
            print(f"{status} {prop['id']}: {retrieved.get('title', 'N/A')}")
        else:
            print(f"❌ {prop['id']}: Not found")
    
    print()
    print("Storage Statistics:")
    print("-" * 60)
    stats = storage.get_storage_stats()
    for key, value in stats.items():
        print(f"  {key}: {value}")
    
    print()
    print("Stored Proposals:")
    print("-" * 60)
    proposals = storage.list_proposals()
    for p in proposals:
        print(f"  {p['id']} ({p['agent']}): {p['topic']} - {p['method']}")
    
    # Cleanup
    import os
    os.unlink(db_path)
    
    print()
    print("=" * 60)
    print("✅ AURA storage test completed")
    print("=" * 60)


if __name__ == "__main__":
    test_aura_storage()
