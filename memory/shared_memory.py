"""
TIER 3: Shared Memory (Orchestra-level)

Network-accessible memory shared across all agents in the orchestra.
- Approved proposals become collective knowledge
- Cross-agent learning (what worked for Agent A helps Agent B)
- Centralized on orchestra server, synced to agents
"""

import os
import json
import time
import sqlite3
import hashlib
import requests
import numpy as np
from typing import Dict, List, Any, Optional, Tuple
from dataclasses import dataclass
from pathlib import Path
import threading
from concurrent.futures import ThreadPoolExecutor
import logging

logger = logging.getLogger(__name__)


@dataclass
class SharedProposal:
    """A proposal in shared memory (approved and vetted)."""
    id: str
    title: str
    content: str
    agent_id: str  # Which agent created it
    domain: str  # 'safety', 'performance', 'security', etc.
    reward: float
    peer_reviews: List[Dict[str, Any]]
    orka_assessment: Dict[str, Any]
    deployment_status: str  # 'deployed', 'pending', 'rolled_back'
    created_at: float
    approved_at: float
    metadata: Dict[str, Any]


@dataclass
class CollectivePattern:
    """A pattern learned across multiple agents."""
    id: str
    pattern_type: str
    description: str
    contributing_agents: List[str]
    evidence_count: int
    confidence: float
    domain: str
    created_at: float
    updated_at: float


class SharedMemoryClient:
    """
    Client for accessing shared memory from an agent.
    Communicates with the orchestra server.
    """
    
    def __init__(
        self,
        agent_id: str,
        orchestra_url: str = "http://localhost:5000",
        local_cache_dir: str = "./data/shared_cache",
        sync_interval_seconds: float = 60.0
    ):
        self.agent_id = agent_id
        self.orchestra_url = orchestra_url.rstrip('/')
        self.cache_dir = Path(local_cache_dir) / agent_id
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        self.sync_interval = sync_interval_seconds
        
        self._lock = threading.RLock()
        self._last_sync = 0.0
        self._local_cache: Dict[str, Any] = {}
        
        # Load local cache
        self._load_local_cache()
    
    def _load_local_cache(self) -> None:
        """Load cached shared memory from disk."""
        cache_file = self.cache_dir / "shared_cache.json"
        if cache_file.exists():
            try:
                with open(cache_file, 'r') as f:
                    self._local_cache = json.load(f)
                    self._last_sync = self._local_cache.get('_last_sync', 0.0)
            except Exception as e:
                logger.warning(f"Failed to load shared cache: {e}")
                self._local_cache = {}
    
    def _save_local_cache(self) -> None:
        """Save shared memory cache to disk."""
        cache_file = self.cache_dir / "shared_cache.json"
        try:
            self._local_cache['_last_sync'] = self._last_sync
            with open(cache_file, 'w') as f:
                json.dump(self._local_cache, f)
        except Exception as e:
            logger.warning(f"Failed to save shared cache: {e}")
    
    def _api_call(
        self,
        method: str,
        endpoint: str,
        data: Optional[Dict] = None,
        timeout: float = 10.0
    ) -> Optional[Dict[str, Any]]:
        """Make an API call to the orchestra server."""
        url = f"{self.orchestra_url}/api/shared{endpoint}"
        headers = {'X-Agent-ID': self.agent_id}
        
        try:
            if method == 'GET':
                response = requests.get(url, headers=headers, timeout=timeout)
            elif method == 'POST':
                response = requests.post(url, json=data, headers=headers, timeout=timeout)
            elif method == 'PUT':
                response = requests.put(url, json=data, headers=headers, timeout=timeout)
            else:
                raise ValueError(f"Unknown method: {method}")
            
            response.raise_for_status()
            return response.json()
        except requests.exceptions.RequestException as e:
            logger.warning(f"API call failed: {e}")
            return None
    
    # ========== Proposal Operations ==========
    
    def submit_approved_proposal(
        self,
        proposal_id: str,
        title: str,
        content: str,
        domain: str,
        reward: float,
        peer_reviews: List[Dict[str, Any]],
        orka_assessment: Dict[str, Any],
        metadata: Optional[Dict[str, Any]] = None
    ) -> bool:
        """Submit an approved proposal to shared memory."""
        data = {
            'proposal_id': proposal_id,
            'title': title,
            'content': content,
            'agent_id': self.agent_id,
            'domain': domain,
            'reward': reward,
            'peer_reviews': peer_reviews,
            'orka_assessment': orka_assessment,
            'metadata': metadata or {}
        }
        
        result = self._api_call('POST', '/proposals', data)
        
        if result and result.get('success'):
            # Update local cache
            with self._lock:
                if 'proposals' not in self._local_cache:
                    self._local_cache['proposals'] = {}
                self._local_cache['proposals'][proposal_id] = data
                self._save_local_cache()
            return True
        
        return False
    
    def get_shared_proposals(
        self,
        domain: Optional[str] = None,
        limit: int = 50,
        min_reward: float = 0.0
    ) -> List[SharedProposal]:
        """Get approved proposals from shared memory."""
        params = f"?limit={limit}&min_reward={min_reward}"
        if domain:
            params += f"&domain={domain}"
        
        result = self._api_call('GET', f'/proposals{params}')
        
        if result and 'proposals' in result:
            return [self._dict_to_shared_proposal(p) for p in result['proposals']]
        
        # Fall back to local cache
        cached = self._local_cache.get('proposals', {})
        proposals = [
            self._dict_to_shared_proposal(p) 
            for p in cached.values()
            if (domain is None or p.get('domain') == domain) and p.get('reward', 0) >= min_reward
        ]
        return sorted(proposals, key=lambda x: x.reward, reverse=True)[:limit]
    
    def search_shared_proposals(
        self,
        query: str,
        limit: int = 10
    ) -> List[Tuple[SharedProposal, float]]:
        """Search shared proposals by text similarity."""
        result = self._api_call('POST', '/proposals/search', {
            'query': query,
            'limit': limit
        })
        
        if result and 'results' in result:
            return [
                (self._dict_to_shared_proposal(r['proposal']), r['score'])
                for r in result['results']
            ]
        
        # Simple local fallback
        return self._local_search(query, limit)
    
    def _local_search(self, query: str, limit: int) -> List[Tuple[SharedProposal, float]]:
        """Simple keyword search in local cache."""
        query_words = set(query.lower().split())
        results = []
        
        for p_data in self._local_cache.get('proposals', {}).values():
            content = f"{p_data.get('title', '')} {p_data.get('content', '')}".lower()
            content_words = set(content.split())
            overlap = len(query_words & content_words)
            if overlap > 0:
                score = overlap / len(query_words)
                results.append((self._dict_to_shared_proposal(p_data), score))
        
        results.sort(key=lambda x: x[1], reverse=True)
        return results[:limit]
    
    def _dict_to_shared_proposal(self, data: Dict[str, Any]) -> SharedProposal:
        """Convert dict to SharedProposal."""
        return SharedProposal(
            id=data.get('proposal_id', data.get('id', '')),
            title=data.get('title', ''),
            content=data.get('content', ''),
            agent_id=data.get('agent_id', ''),
            domain=data.get('domain', 'general'),
            reward=data.get('reward', 0.0),
            peer_reviews=data.get('peer_reviews', []),
            orka_assessment=data.get('orka_assessment', {}),
            deployment_status=data.get('deployment_status', 'pending'),
            created_at=data.get('created_at', 0.0),
            approved_at=data.get('approved_at', 0.0),
            metadata=data.get('metadata', {})
        )
    
    # ========== Pattern Operations ==========
    
    def submit_pattern(
        self,
        pattern_type: str,
        description: str,
        domain: str,
        confidence: float,
        evidence: List[str]
    ) -> bool:
        """Submit a learned pattern to shared memory."""
        data = {
            'pattern_type': pattern_type,
            'description': description,
            'domain': domain,
            'confidence': confidence,
            'evidence': evidence,
            'agent_id': self.agent_id
        }
        
        result = self._api_call('POST', '/patterns', data)
        return result is not None and result.get('success', False)
    
    def get_patterns(
        self,
        pattern_type: Optional[str] = None,
        domain: Optional[str] = None,
        min_confidence: float = 0.5
    ) -> List[CollectivePattern]:
        """Get collective patterns from shared memory."""
        params = f"?min_confidence={min_confidence}"
        if pattern_type:
            params += f"&type={pattern_type}"
        if domain:
            params += f"&domain={domain}"
        
        result = self._api_call('GET', f'/patterns{params}')
        
        if result and 'patterns' in result:
            return [
                CollectivePattern(
                    id=p.get('id', ''),
                    pattern_type=p.get('pattern_type', ''),
                    description=p.get('description', ''),
                    contributing_agents=p.get('contributing_agents', []),
                    evidence_count=p.get('evidence_count', 0),
                    confidence=p.get('confidence', 0.0),
                    domain=p.get('domain', 'general'),
                    created_at=p.get('created_at', 0.0),
                    updated_at=p.get('updated_at', 0.0)
                )
                for p in result['patterns']
            ]
        
        return []
    
    # ========== Sync Operations ==========
    
    def sync(self, force: bool = False) -> bool:
        """
        Synchronize with orchestra server.
        Downloads new shared knowledge, uploads local contributions.
        """
        now = time.time()
        if not force and (now - self._last_sync) < self.sync_interval:
            return True
        
        try:
            # Get updates since last sync
            result = self._api_call('GET', f'/sync?since={self._last_sync}')
            
            if result:
                with self._lock:
                    # Merge new proposals
                    if 'proposals' in result:
                        if 'proposals' not in self._local_cache:
                            self._local_cache['proposals'] = {}
                        for p in result['proposals']:
                            pid = p.get('proposal_id', p.get('id'))
                            self._local_cache['proposals'][pid] = p
                    
                    # Merge new patterns
                    if 'patterns' in result:
                        if 'patterns' not in self._local_cache:
                            self._local_cache['patterns'] = {}
                        for p in result['patterns']:
                            self._local_cache['patterns'][p.get('id')] = p
                    
                    self._last_sync = now
                    self._save_local_cache()
                
                logger.info(f"Synced shared memory: {len(result.get('proposals', []))} proposals, {len(result.get('patterns', []))} patterns")
                return True
            
            return False
        except Exception as e:
            logger.error(f"Sync failed: {e}")
            return False
    
    def get_stats(self) -> Dict[str, Any]:
        """Get shared memory statistics."""
        result = self._api_call('GET', '/stats')
        
        if result:
            return result
        
        # Fall back to local cache stats
        return {
            'cached_proposals': len(self._local_cache.get('proposals', {})),
            'cached_patterns': len(self._local_cache.get('patterns', {})),
            'last_sync': self._last_sync,
            'orchestra_url': self.orchestra_url,
            'status': 'offline'
        }


class SharedMemoryServer:
    """
    Server-side shared memory (runs on orchestra).
    Stores approved proposals and patterns from all agents.
    """
    
    def __init__(self, data_dir: str = "./data/orchestra"):
        self.data_dir = Path(data_dir)
        self.data_dir.mkdir(parents=True, exist_ok=True)
        
        self.db_path = self.data_dir / "shared_memory.db"
        self.embeddings_path = self.data_dir / "shared_embeddings.npz"
        
        self._lock = threading.RLock()
        self._init_database()
        
        # Embedding store for semantic search
        from .personal_memory import EmbeddingStore
        self.embedding_store = EmbeddingStore(dimension=384)
        if self.embeddings_path.exists():
            self.embedding_store.load(str(self.embeddings_path))
    
    def _init_database(self) -> None:
        """Initialize shared database schema."""
        with sqlite3.connect(str(self.db_path)) as conn:
            conn.executescript("""
                -- Shared proposals (approved and vetted)
                CREATE TABLE IF NOT EXISTS proposals (
                    id TEXT PRIMARY KEY,
                    title TEXT NOT NULL,
                    content TEXT NOT NULL,
                    agent_id TEXT NOT NULL,
                    domain TEXT DEFAULT 'general',
                    reward REAL DEFAULT 0.0,
                    peer_reviews TEXT DEFAULT '[]',
                    orka_assessment TEXT DEFAULT '{}',
                    deployment_status TEXT DEFAULT 'pending',
                    created_at REAL NOT NULL,
                    approved_at REAL NOT NULL,
                    metadata TEXT DEFAULT '{}'
                );
                
                -- Collective patterns
                CREATE TABLE IF NOT EXISTS patterns (
                    id TEXT PRIMARY KEY,
                    pattern_type TEXT NOT NULL,
                    description TEXT NOT NULL,
                    contributing_agents TEXT DEFAULT '[]',
                    evidence_count INTEGER DEFAULT 1,
                    confidence REAL DEFAULT 0.5,
                    domain TEXT DEFAULT 'general',
                    created_at REAL NOT NULL,
                    updated_at REAL NOT NULL
                );
                
                -- Agent registry
                CREATE TABLE IF NOT EXISTS agents (
                    id TEXT PRIMARY KEY,
                    name TEXT,
                    last_seen REAL,
                    proposals_submitted INTEGER DEFAULT 0,
                    patterns_submitted INTEGER DEFAULT 0,
                    metadata TEXT DEFAULT '{}'
                );
                
                -- Sync log
                CREATE TABLE IF NOT EXISTS sync_log (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    agent_id TEXT NOT NULL,
                    action TEXT NOT NULL,
                    details TEXT,
                    timestamp REAL NOT NULL
                );
                
                -- Indexes
                CREATE INDEX IF NOT EXISTS idx_proposals_domain ON proposals(domain);
                CREATE INDEX IF NOT EXISTS idx_proposals_reward ON proposals(reward);
                CREATE INDEX IF NOT EXISTS idx_patterns_type ON patterns(pattern_type);
                CREATE INDEX IF NOT EXISTS idx_patterns_domain ON patterns(domain);
            """)
    
    def _get_connection(self) -> sqlite3.Connection:
        conn = sqlite3.connect(str(self.db_path))
        conn.row_factory = sqlite3.Row
        return conn
    
    def add_proposal(
        self,
        proposal_id: str,
        title: str,
        content: str,
        agent_id: str,
        domain: str,
        reward: float,
        peer_reviews: List[Dict],
        orka_assessment: Dict,
        metadata: Dict
    ) -> bool:
        """Add an approved proposal to shared memory."""
        with self._lock:
            now = time.time()
            
            with self._get_connection() as conn:
                try:
                    conn.execute("""
                        INSERT INTO proposals 
                        (id, title, content, agent_id, domain, reward, peer_reviews, 
                         orka_assessment, created_at, approved_at, metadata)
                        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """, (
                        proposal_id, title, content, agent_id, domain, reward,
                        json.dumps(peer_reviews), json.dumps(orka_assessment),
                        now, now, json.dumps(metadata)
                    ))
                    
                    # Update agent stats
                    conn.execute("""
                        INSERT INTO agents (id, last_seen, proposals_submitted)
                        VALUES (?, ?, 1)
                        ON CONFLICT(id) DO UPDATE SET 
                            last_seen = ?, 
                            proposals_submitted = proposals_submitted + 1
                    """, (agent_id, now, now))
                    
                    # Log sync
                    conn.execute("""
                        INSERT INTO sync_log (agent_id, action, details, timestamp)
                        VALUES (?, 'proposal_added', ?, ?)
                    """, (agent_id, proposal_id, now))
                    
                    return True
                except sqlite3.IntegrityError:
                    return False  # Already exists
    
    def get_proposals(
        self,
        domain: Optional[str] = None,
        limit: int = 50,
        min_reward: float = 0.0,
        since: float = 0.0
    ) -> List[Dict[str, Any]]:
        """Get proposals from shared memory."""
        with self._get_connection() as conn:
            query = """
                SELECT * FROM proposals 
                WHERE reward >= ? AND approved_at >= ?
            """
            params = [min_reward, since]
            
            if domain:
                query += " AND domain = ?"
                params.append(domain)
            
            query += " ORDER BY reward DESC, approved_at DESC LIMIT ?"
            params.append(limit)
            
            rows = conn.execute(query, params).fetchall()
            
            return [
                {
                    'id': row['id'],
                    'title': row['title'],
                    'content': row['content'],
                    'agent_id': row['agent_id'],
                    'domain': row['domain'],
                    'reward': row['reward'],
                    'peer_reviews': json.loads(row['peer_reviews']),
                    'orka_assessment': json.loads(row['orka_assessment']),
                    'deployment_status': row['deployment_status'],
                    'created_at': row['created_at'],
                    'approved_at': row['approved_at'],
                    'metadata': json.loads(row['metadata'])
                }
                for row in rows
            ]
    
    def add_pattern(
        self,
        pattern_type: str,
        description: str,
        domain: str,
        confidence: float,
        agent_id: str
    ) -> str:
        """Add or update a collective pattern."""
        with self._lock:
            pattern_id = hashlib.sha256(
                f"{pattern_type}{description}".encode()
            ).hexdigest()[:16]
            
            now = time.time()
            
            with self._get_connection() as conn:
                # Check if exists
                existing = conn.execute(
                    "SELECT * FROM patterns WHERE id = ?", (pattern_id,)
                ).fetchone()
                
                if existing:
                    # Update existing
                    agents = json.loads(existing['contributing_agents'])
                    if agent_id not in agents:
                        agents.append(agent_id)
                    
                    new_count = existing['evidence_count'] + 1
                    new_confidence = (existing['confidence'] * existing['evidence_count'] + confidence) / new_count
                    
                    conn.execute("""
                        UPDATE patterns 
                        SET contributing_agents = ?, evidence_count = ?, confidence = ?, updated_at = ?
                        WHERE id = ?
                    """, (json.dumps(agents), new_count, new_confidence, now, pattern_id))
                else:
                    # Create new
                    conn.execute("""
                        INSERT INTO patterns 
                        (id, pattern_type, description, contributing_agents, domain, confidence, created_at, updated_at)
                        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                    """, (pattern_id, pattern_type, description, json.dumps([agent_id]), domain, confidence, now, now))
                
                # Update agent stats
                conn.execute("""
                    INSERT INTO agents (id, last_seen, patterns_submitted)
                    VALUES (?, ?, 1)
                    ON CONFLICT(id) DO UPDATE SET 
                        last_seen = ?, 
                        patterns_submitted = patterns_submitted + 1
                """, (agent_id, now, now))
            
            return pattern_id
    
    def get_patterns(
        self,
        pattern_type: Optional[str] = None,
        domain: Optional[str] = None,
        min_confidence: float = 0.5
    ) -> List[Dict[str, Any]]:
        """Get collective patterns."""
        with self._get_connection() as conn:
            query = "SELECT * FROM patterns WHERE confidence >= ?"
            params = [min_confidence]
            
            if pattern_type:
                query += " AND pattern_type = ?"
                params.append(pattern_type)
            if domain:
                query += " AND domain = ?"
                params.append(domain)
            
            query += " ORDER BY confidence DESC, evidence_count DESC"
            
            rows = conn.execute(query, params).fetchall()
            
            return [
                {
                    'id': row['id'],
                    'pattern_type': row['pattern_type'],
                    'description': row['description'],
                    'contributing_agents': json.loads(row['contributing_agents']),
                    'evidence_count': row['evidence_count'],
                    'confidence': row['confidence'],
                    'domain': row['domain'],
                    'created_at': row['created_at'],
                    'updated_at': row['updated_at']
                }
                for row in rows
            ]
    
    def get_sync_data(self, since: float = 0.0) -> Dict[str, Any]:
        """Get all data updated since timestamp (for agent sync)."""
        return {
            'proposals': self.get_proposals(since=since, limit=1000),
            'patterns': self.get_patterns(min_confidence=0.0),
            'timestamp': time.time()
        }
    
    def get_stats(self) -> Dict[str, Any]:
        """Get shared memory statistics."""
        with self._get_connection() as conn:
            proposal_count = conn.execute("SELECT COUNT(*) FROM proposals").fetchone()[0]
            pattern_count = conn.execute("SELECT COUNT(*) FROM patterns").fetchone()[0]
            agent_count = conn.execute("SELECT COUNT(*) FROM agents").fetchone()[0]
            
            # Domain distribution
            domains = conn.execute("""
                SELECT domain, COUNT(*) as count FROM proposals GROUP BY domain
            """).fetchall()
            
            # Top agents
            top_agents = conn.execute("""
                SELECT id, proposals_submitted, patterns_submitted 
                FROM agents ORDER BY proposals_submitted DESC LIMIT 5
            """).fetchall()
            
            return {
                'total_proposals': proposal_count,
                'total_patterns': pattern_count,
                'total_agents': agent_count,
                'domains': {row['domain']: row['count'] for row in domains},
                'top_agents': [
                    {'id': row['id'], 'proposals': row['proposals_submitted'], 'patterns': row['patterns_submitted']}
                    for row in top_agents
                ],
                'status': 'online'
            }

