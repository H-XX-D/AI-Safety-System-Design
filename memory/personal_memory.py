"""
TIER 2: Personal Memory (On-Device)

Persistent, agent-specific memory stored locally.
- SQLite for structured data (proposals, outcomes, metadata)
- FAISS/NumPy for vector embeddings (semantic search)
- Survives restarts, agent-specific learning
"""

import os
import json
import time
import sqlite3
import hashlib
import numpy as np
from typing import Dict, List, Any, Optional, Tuple
from dataclasses import dataclass
from pathlib import Path
import threading


@dataclass
class ProposalRecord:
    """A proposal with its outcome and metadata."""
    id: str
    title: str
    content: str
    outcome: str  # 'approved', 'rejected', 'pending', 'revised'
    confidence_initial: float
    confidence_final: float
    reward: float
    reviews: List[Dict[str, Any]]
    created_at: float
    updated_at: float
    embedding: Optional[np.ndarray] = None
    metadata: Dict[str, Any] = None
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            'id': self.id,
            'title': self.title,
            'content': self.content,
            'outcome': self.outcome,
            'confidence_initial': self.confidence_initial,
            'confidence_final': self.confidence_final,
            'reward': self.reward,
            'reviews': self.reviews,
            'created_at': self.created_at,
            'updated_at': self.updated_at,
            'metadata': self.metadata or {}
        }


@dataclass
class LearningPattern:
    """A learned pattern from proposal history."""
    pattern_type: str  # 'success_factor', 'failure_mode', 'reviewer_preference'
    description: str
    evidence_count: int
    confidence: float
    examples: List[str]  # Proposal IDs
    created_at: float
    updated_at: float


class EmbeddingStore:
    """
    Simple numpy-based vector store for embeddings.
    Uses cosine similarity for retrieval.
    Can be upgraded to FAISS for larger scale.
    """
    
    def __init__(self, dimension: int = 384):
        self.dimension = dimension
        self.embeddings: List[np.ndarray] = []
        self.ids: List[str] = []
        self._lock = threading.RLock()
    
    def add(self, id: str, embedding: np.ndarray) -> None:
        """Add an embedding."""
        with self._lock:
            if embedding.shape[0] != self.dimension:
                raise ValueError(f"Expected dimension {self.dimension}, got {embedding.shape[0]}")
            
            # Check if ID exists, update if so
            if id in self.ids:
                idx = self.ids.index(id)
                self.embeddings[idx] = embedding / np.linalg.norm(embedding)
            else:
                self.ids.append(id)
                self.embeddings.append(embedding / np.linalg.norm(embedding))
    
    def search(self, query_embedding: np.ndarray, k: int = 5) -> List[Tuple[str, float]]:
        """Search for k most similar embeddings."""
        with self._lock:
            if not self.embeddings:
                return []
            
            query_norm = query_embedding / np.linalg.norm(query_embedding)
            
            # Compute cosine similarities
            embeddings_matrix = np.array(self.embeddings)
            similarities = embeddings_matrix @ query_norm
            
            # Get top k
            top_indices = np.argsort(similarities)[::-1][:k]
            
            return [(self.ids[i], float(similarities[i])) for i in top_indices]
    
    def remove(self, id: str) -> bool:
        """Remove an embedding by ID."""
        with self._lock:
            if id in self.ids:
                idx = self.ids.index(id)
                self.ids.pop(idx)
                self.embeddings.pop(idx)
                return True
            return False
    
    def save(self, path: str) -> None:
        """Save embeddings to disk."""
        with self._lock:
            np.savez(
                path,
                embeddings=np.array(self.embeddings) if self.embeddings else np.array([]).reshape(0, self.dimension),
                ids=np.array(self.ids, dtype=object)
            )
    
    def load(self, path: str) -> None:
        """Load embeddings from disk."""
        with self._lock:
            if os.path.exists(path):
                data = np.load(path, allow_pickle=True)
                self.embeddings = list(data['embeddings'])
                self.ids = list(data['ids'])
    
    def __len__(self) -> int:
        return len(self.ids)


class PersonalMemory:
    """
    On-device persistent memory for a single agent.
    
    Features:
    - SQLite for structured proposal/outcome storage
    - Vector embeddings for semantic search
    - Learned patterns from history
    - Statistics and trends
    """
    
    def __init__(
        self,
        agent_id: str,
        data_dir: str = "./data/memory",
        embedding_dim: int = 384
    ):
        self.agent_id = agent_id
        self.data_dir = Path(data_dir) / agent_id
        self.data_dir.mkdir(parents=True, exist_ok=True)
        
        self.db_path = self.data_dir / "personal_memory.db"
        self.embeddings_path = self.data_dir / "embeddings.npz"
        
        self._lock = threading.RLock()
        self._init_database()
        
        # Initialize embedding store
        self.embedding_store = EmbeddingStore(dimension=embedding_dim)
        if self.embeddings_path.exists():
            self.embedding_store.load(str(self.embeddings_path))
    
    def _init_database(self) -> None:
        """Initialize SQLite database schema."""
        with sqlite3.connect(str(self.db_path)) as conn:
            conn.executescript("""
                -- Proposals table
                CREATE TABLE IF NOT EXISTS proposals (
                    id TEXT PRIMARY KEY,
                    title TEXT NOT NULL,
                    content TEXT NOT NULL,
                    outcome TEXT DEFAULT 'pending',
                    confidence_initial REAL DEFAULT 0.5,
                    confidence_final REAL DEFAULT 0.5,
                    reward REAL DEFAULT 0.0,
                    reviews TEXT DEFAULT '[]',
                    created_at REAL NOT NULL,
                    updated_at REAL NOT NULL,
                    metadata TEXT DEFAULT '{}'
                );
                
                -- Learned patterns table
                CREATE TABLE IF NOT EXISTS patterns (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    pattern_type TEXT NOT NULL,
                    description TEXT NOT NULL,
                    evidence_count INTEGER DEFAULT 1,
                    confidence REAL DEFAULT 0.5,
                    examples TEXT DEFAULT '[]',
                    created_at REAL NOT NULL,
                    updated_at REAL NOT NULL
                );
                
                -- Feedback history (from reviews, ORKA, etc.)
                CREATE TABLE IF NOT EXISTS feedback (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    proposal_id TEXT,
                    source TEXT NOT NULL,
                    feedback_type TEXT NOT NULL,
                    content TEXT NOT NULL,
                    sentiment REAL DEFAULT 0.0,
                    created_at REAL NOT NULL,
                    FOREIGN KEY (proposal_id) REFERENCES proposals(id)
                );
                
                -- Agent statistics
                CREATE TABLE IF NOT EXISTS stats (
                    key TEXT PRIMARY KEY,
                    value TEXT NOT NULL,
                    updated_at REAL NOT NULL
                );
                
                -- Indexes
                CREATE INDEX IF NOT EXISTS idx_proposals_outcome ON proposals(outcome);
                CREATE INDEX IF NOT EXISTS idx_proposals_created ON proposals(created_at);
                CREATE INDEX IF NOT EXISTS idx_feedback_proposal ON feedback(proposal_id);
            """)
    
    def _get_connection(self) -> sqlite3.Connection:
        """Get a database connection."""
        conn = sqlite3.connect(str(self.db_path))
        conn.row_factory = sqlite3.Row
        return conn
    
    # ========== Proposal Operations ==========
    
    def store_proposal(
        self,
        title: str,
        content: str,
        confidence: float = 0.5,
        metadata: Optional[Dict[str, Any]] = None,
        embedding: Optional[np.ndarray] = None
    ) -> str:
        """Store a new proposal."""
        with self._lock:
            proposal_id = hashlib.sha256(
                f"{title}{content}{time.time()}".encode()
            ).hexdigest()[:16]
            
            now = time.time()
            
            with self._get_connection() as conn:
                conn.execute("""
                    INSERT INTO proposals 
                    (id, title, content, confidence_initial, confidence_final, created_at, updated_at, metadata)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    proposal_id, title, content, confidence, confidence,
                    now, now, json.dumps(metadata or {})
                ))
            
            # Store embedding if provided
            if embedding is not None:
                self.embedding_store.add(proposal_id, embedding)
                self._save_embeddings()
            
            return proposal_id
    
    def update_proposal_outcome(
        self,
        proposal_id: str,
        outcome: str,
        confidence_final: float,
        reward: float,
        reviews: List[Dict[str, Any]]
    ) -> None:
        """Update a proposal with its outcome."""
        with self._lock:
            with self._get_connection() as conn:
                conn.execute("""
                    UPDATE proposals 
                    SET outcome = ?, confidence_final = ?, reward = ?, reviews = ?, updated_at = ?
                    WHERE id = ?
                """, (outcome, confidence_final, reward, json.dumps(reviews), time.time(), proposal_id))
            
            # Update statistics
            self._update_stats_after_outcome(outcome, reward)
    
    def get_proposal(self, proposal_id: str) -> Optional[ProposalRecord]:
        """Get a proposal by ID."""
        with self._get_connection() as conn:
            row = conn.execute(
                "SELECT * FROM proposals WHERE id = ?", (proposal_id,)
            ).fetchone()
            
            if row:
                return self._row_to_proposal(row)
            return None
    
    def get_proposals_by_outcome(
        self,
        outcome: str,
        limit: int = 50
    ) -> List[ProposalRecord]:
        """Get proposals filtered by outcome."""
        with self._get_connection() as conn:
            rows = conn.execute("""
                SELECT * FROM proposals 
                WHERE outcome = ? 
                ORDER BY created_at DESC 
                LIMIT ?
            """, (outcome, limit)).fetchall()
            
            return [self._row_to_proposal(row) for row in rows]
    
    def get_recent_proposals(self, limit: int = 20) -> List[ProposalRecord]:
        """Get most recent proposals."""
        with self._get_connection() as conn:
            rows = conn.execute("""
                SELECT * FROM proposals 
                ORDER BY created_at DESC 
                LIMIT ?
            """, (limit,)).fetchall()
            
            return [self._row_to_proposal(row) for row in rows]
    
    def search_proposals_semantic(
        self,
        query_embedding: np.ndarray,
        k: int = 5,
        outcome_filter: Optional[str] = None
    ) -> List[Tuple[ProposalRecord, float]]:
        """Search proposals by semantic similarity."""
        with self._lock:
            # Get similar IDs from embedding store
            similar = self.embedding_store.search(query_embedding, k=k * 2)  # Get more, filter later
            
            results = []
            for proposal_id, similarity in similar:
                proposal = self.get_proposal(proposal_id)
                if proposal:
                    if outcome_filter is None or proposal.outcome == outcome_filter:
                        results.append((proposal, similarity))
                        if len(results) >= k:
                            break
            
            return results
    
    def _row_to_proposal(self, row: sqlite3.Row) -> ProposalRecord:
        """Convert a database row to a ProposalRecord."""
        return ProposalRecord(
            id=row['id'],
            title=row['title'],
            content=row['content'],
            outcome=row['outcome'],
            confidence_initial=row['confidence_initial'],
            confidence_final=row['confidence_final'],
            reward=row['reward'],
            reviews=json.loads(row['reviews']),
            created_at=row['created_at'],
            updated_at=row['updated_at'],
            metadata=json.loads(row['metadata'])
        )
    
    # ========== Feedback Operations ==========
    
    def store_feedback(
        self,
        proposal_id: str,
        source: str,
        feedback_type: str,
        content: str,
        sentiment: float = 0.0
    ) -> None:
        """Store feedback from reviews, ORKA, etc."""
        with self._get_connection() as conn:
            conn.execute("""
                INSERT INTO feedback (proposal_id, source, feedback_type, content, sentiment, created_at)
                VALUES (?, ?, ?, ?, ?, ?)
            """, (proposal_id, source, feedback_type, content, sentiment, time.time()))
    
    def get_feedback_for_proposal(self, proposal_id: str) -> List[Dict[str, Any]]:
        """Get all feedback for a proposal."""
        with self._get_connection() as conn:
            rows = conn.execute("""
                SELECT * FROM feedback WHERE proposal_id = ? ORDER BY created_at
            """, (proposal_id,)).fetchall()
            
            return [dict(row) for row in rows]
    
    # ========== Pattern Learning ==========
    
    def record_pattern(
        self,
        pattern_type: str,
        description: str,
        example_id: str,
        confidence: float = 0.5
    ) -> None:
        """Record or update a learned pattern."""
        with self._lock:
            with self._get_connection() as conn:
                # Check if pattern exists
                existing = conn.execute("""
                    SELECT id, evidence_count, examples, confidence 
                    FROM patterns 
                    WHERE pattern_type = ? AND description = ?
                """, (pattern_type, description)).fetchone()
                
                now = time.time()
                
                if existing:
                    # Update existing pattern
                    examples = json.loads(existing['examples'])
                    if example_id not in examples:
                        examples.append(example_id)
                    
                    # Bayesian-ish confidence update
                    new_evidence = existing['evidence_count'] + 1
                    new_confidence = (existing['confidence'] * existing['evidence_count'] + confidence) / new_evidence
                    
                    conn.execute("""
                        UPDATE patterns 
                        SET evidence_count = ?, examples = ?, confidence = ?, updated_at = ?
                        WHERE id = ?
                    """, (new_evidence, json.dumps(examples), new_confidence, now, existing['id']))
                else:
                    # Create new pattern
                    conn.execute("""
                        INSERT INTO patterns (pattern_type, description, evidence_count, confidence, examples, created_at, updated_at)
                        VALUES (?, ?, 1, ?, ?, ?, ?)
                    """, (pattern_type, description, confidence, json.dumps([example_id]), now, now))
    
    def get_patterns(
        self,
        pattern_type: Optional[str] = None,
        min_confidence: float = 0.0,
        limit: int = 20
    ) -> List[LearningPattern]:
        """Get learned patterns."""
        with self._get_connection() as conn:
            if pattern_type:
                rows = conn.execute("""
                    SELECT * FROM patterns 
                    WHERE pattern_type = ? AND confidence >= ?
                    ORDER BY confidence DESC, evidence_count DESC
                    LIMIT ?
                """, (pattern_type, min_confidence, limit)).fetchall()
            else:
                rows = conn.execute("""
                    SELECT * FROM patterns 
                    WHERE confidence >= ?
                    ORDER BY confidence DESC, evidence_count DESC
                    LIMIT ?
                """, (min_confidence, limit)).fetchall()
            
            return [
                LearningPattern(
                    pattern_type=row['pattern_type'],
                    description=row['description'],
                    evidence_count=row['evidence_count'],
                    confidence=row['confidence'],
                    examples=json.loads(row['examples']),
                    created_at=row['created_at'],
                    updated_at=row['updated_at']
                )
                for row in rows
            ]
    
    # ========== Statistics ==========
    
    def _update_stats_after_outcome(self, outcome: str, reward: float) -> None:
        """Update statistics after a proposal outcome."""
        stats_to_update = {
            f'total_{outcome}': lambda old: int(old or 0) + 1,
            'total_proposals': lambda old: int(old or 0) + 1,
            'total_reward': lambda old: float(old or 0) + reward,
            'last_outcome': lambda _: outcome,
            'last_reward': lambda _: reward
        }
        
        with self._get_connection() as conn:
            for key, update_fn in stats_to_update.items():
                # Get current value
                row = conn.execute("SELECT value FROM stats WHERE key = ?", (key,)).fetchone()
                old_value = row['value'] if row else None
                
                # Compute new value
                new_value = str(update_fn(old_value))
                
                # Upsert
                conn.execute("""
                    INSERT INTO stats (key, value, updated_at) VALUES (?, ?, ?)
                    ON CONFLICT(key) DO UPDATE SET value = ?, updated_at = ?
                """, (key, new_value, time.time(), new_value, time.time()))
    
    def get_stats(self) -> Dict[str, Any]:
        """Get agent statistics."""
        with self._get_connection() as conn:
            rows = conn.execute("SELECT key, value FROM stats").fetchall()
            stats = {row['key']: row['value'] for row in rows}
            
            # Compute derived stats
            total = int(stats.get('total_proposals', 0))
            approved = int(stats.get('total_approved', 0))
            rejected = int(stats.get('total_rejected', 0))
            
            if total > 0:
                stats['approval_rate'] = approved / total
                stats['rejection_rate'] = rejected / total
                stats['avg_reward'] = float(stats.get('total_reward', 0)) / total
            
            stats['embedding_count'] = len(self.embedding_store)
            
            return stats
    
    # ========== Utility ==========
    
    def _save_embeddings(self) -> None:
        """Save embeddings to disk."""
        self.embedding_store.save(str(self.embeddings_path))
    
    def get_contrastive_examples(
        self,
        n_positive: int = 10,
        n_negative: int = 10
    ) -> Tuple[List[ProposalRecord], List[ProposalRecord]]:
        """
        Get contrastive examples for steering vector computation.
        Positive = approved with high reward
        Negative = rejected with low reward
        """
        with self._get_connection() as conn:
            # Get best approved proposals
            positive_rows = conn.execute("""
                SELECT * FROM proposals 
                WHERE outcome = 'approved' 
                ORDER BY reward DESC, confidence_final DESC
                LIMIT ?
            """, (n_positive,)).fetchall()
            
            # Get worst rejected proposals
            negative_rows = conn.execute("""
                SELECT * FROM proposals 
                WHERE outcome = 'rejected'
                ORDER BY reward ASC, confidence_final ASC
                LIMIT ?
            """, (n_negative,)).fetchall()
            
            positive = [self._row_to_proposal(row) for row in positive_rows]
            negative = [self._row_to_proposal(row) for row in negative_rows]
            
            return positive, negative
    
    def export_for_training(self) -> List[Dict[str, Any]]:
        """Export data in format suitable for LoRA training."""
        proposals = self.get_recent_proposals(limit=1000)
        
        training_data = []
        for p in proposals:
            if p.outcome in ('approved', 'rejected'):
                training_data.append({
                    'input': f"Propose an improvement: {p.title}",
                    'output': p.content,
                    'outcome': p.outcome,
                    'reward': p.reward,
                    'label': 1 if p.outcome == 'approved' else 0
                })
        
        return training_data
    
    def close(self) -> None:
        """Save and close."""
        self._save_embeddings()

