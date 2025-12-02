"""
AI Memory System
================

Three-tier memory architecture for each AI:
1. Short-term temporary memory - on-board disk (local to each AI)
2. Long-term memory - on disk (persistent storage)
3. Shared memory - on orchestrator (shared across all AIs)

Each AI has its own local disk storage, and the orchestrator maintains
shared memory accessible to all AIs.
"""

import json
import os
import time
from pathlib import Path
from typing import Dict, List, Optional, Any
from dataclasses import dataclass, field, asdict
from datetime import datetime
from threading import Lock
import logging

logger = logging.getLogger(__name__)


@dataclass
class MemoryEntry:
    """Single memory entry."""
    key: str
    value: Any
    timestamp: str
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            'key': self.key,
            'value': self.value,
            'timestamp': self.timestamp,
            'metadata': self.metadata
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'MemoryEntry':
        return cls(
            key=data['key'],
            value=data['value'],
            timestamp=data['timestamp'],
            metadata=data.get('metadata', {})
        )


class ShortTermMemory:
    """
    Short-term temporary memory stored on each AI's on-board disk.
    
    This is fast, local storage for recent information that may be
    discarded after a period of time.
    """
    
    def __init__(self, agent_id: str, base_path: Optional[Path] = None):
        """
        Initialize short-term memory.
        
        Args:
            agent_id: Unique identifier for this AI agent
            base_path: Base path for storage (defaults to agent-specific dir)
        """
        self.agent_id = agent_id
        if base_path is None:
            base_path = Path(f"data/agents/{agent_id}/short_term")
        self.base_path = Path(base_path)
        self.base_path.mkdir(parents=True, exist_ok=True)
        
        self.memory_file = self.base_path / "memory.json"
        self._lock = Lock()
        self._cache: Dict[str, MemoryEntry] = {}
        self._load()
    
    def _load(self) -> None:
        """Load memory from disk."""
        if not self.memory_file.exists():
            return
        
        try:
            with self._lock:
                with open(self.memory_file, 'r') as f:
                    data = json.load(f)
                    self._cache = {
                        k: MemoryEntry.from_dict(v)
                        for k, v in data.items()
                    }
        except Exception as e:
            logger.warning(f"Failed to load short-term memory: {e}")
            self._cache = {}
    
    def _save(self) -> None:
        """Save memory to disk."""
        try:
            with self._lock:
                data = {
                    k: entry.to_dict()
                    for k, entry in self._cache.items()
                }
                with open(self.memory_file, 'w') as f:
                    json.dump(data, f, indent=2)
        except Exception as e:
            logger.error(f"Failed to save short-term memory: {e}")
    
    def write(self, key: str, value: Any, metadata: Optional[Dict[str, Any]] = None) -> None:
        """
        Write to short-term memory.
        
        Args:
            key: Memory key
            value: Value to store
            metadata: Optional metadata
        """
        entry = MemoryEntry(
            key=key,
            value=value,
            timestamp=datetime.now().isoformat(),
            metadata=metadata or {}
        )
        
        with self._lock:
            self._cache[key] = entry
        
        self._save()
        logger.debug(f"Short-term memory write: {key}")
    
    def read(self, key: str) -> Optional[Any]:
        """
        Read from short-term memory.
        
        Args:
            key: Memory key
            
        Returns:
            Value if found, None otherwise
        """
        with self._lock:
            entry = self._cache.get(key)
            if entry:
                return entry.value
            return None
    
    def read_with_metadata(self, key: str) -> Optional[MemoryEntry]:
        """Read entry with metadata."""
        with self._lock:
            return self._cache.get(key)
    
    def delete(self, key: str) -> None:
        """Delete from short-term memory."""
        with self._lock:
            if key in self._cache:
                del self._cache[key]
                self._save()
    
    def list_keys(self) -> List[str]:
        """List all keys in short-term memory."""
        with self._lock:
            return list(self._cache.keys())
    
    def clear(self) -> None:
        """Clear all short-term memory."""
        with self._lock:
            self._cache.clear()
            self._save()


class LongTermMemory:
    """
    Long-term memory stored on disk (persistent storage).
    
    This is for important information that should persist across
    sessions and be available long-term.
    """
    
    def __init__(self, agent_id: str, base_path: Optional[Path] = None):
        """
        Initialize long-term memory.
        
        Args:
            agent_id: Unique identifier for this AI agent
            base_path: Base path for storage (defaults to agent-specific dir)
        """
        self.agent_id = agent_id
        if base_path is None:
            base_path = Path(f"data/agents/{agent_id}/long_term")
        self.base_path = Path(base_path)
        self.base_path.mkdir(parents=True, exist_ok=True)
        
        self.memory_file = self.base_path / "memory.json"
        self._lock = Lock()
        self._cache: Dict[str, MemoryEntry] = {}
        self._load()
    
    def _load(self) -> None:
        """Load memory from disk."""
        if not self.memory_file.exists():
            return
        
        try:
            with self._lock:
                with open(self.memory_file, 'r') as f:
                    data = json.load(f)
                    self._cache = {
                        k: MemoryEntry.from_dict(v)
                        for k, v in data.items()
                    }
        except Exception as e:
            logger.warning(f"Failed to load long-term memory: {e}")
            self._cache = {}
    
    def _save(self) -> None:
        """Save memory to disk."""
        try:
            with self._lock:
                data = {
                    k: entry.to_dict()
                    for k, entry in self._cache.items()
                }
                with open(self.memory_file, 'w') as f:
                    json.dump(data, f, indent=2)
        except Exception as e:
            logger.error(f"Failed to save long-term memory: {e}")
    
    def write(self, key: str, value: Any, metadata: Optional[Dict[str, Any]] = None) -> None:
        """
        Write to long-term memory.
        
        Args:
            key: Memory key
            value: Value to store
            metadata: Optional metadata
        """
        entry = MemoryEntry(
            key=key,
            value=value,
            timestamp=datetime.now().isoformat(),
            metadata=metadata or {}
        )
        
        with self._lock:
            self._cache[key] = entry
        
        self._save()
        logger.debug(f"Long-term memory write: {key}")
    
    def read(self, key: str) -> Optional[Any]:
        """
        Read from long-term memory.
        
        Args:
            key: Memory key
            
        Returns:
            Value if found, None otherwise
        """
        with self._lock:
            entry = self._cache.get(key)
            if entry:
                return entry.value
            return None
    
    def read_with_metadata(self, key: str) -> Optional[MemoryEntry]:
        """Read entry with metadata."""
        with self._lock:
            return self._cache.get(key)
    
    def delete(self, key: str) -> None:
        """Delete from long-term memory."""
        with self._lock:
            if key in self._cache:
                del self._cache[key]
                self._save()
    
    def list_keys(self) -> List[str]:
        """List all keys in long-term memory."""
        with self._lock:
            return list(self._cache.keys())
    
    def search(self, query: str) -> List[MemoryEntry]:
        """
        Search long-term memory by key (simple substring match).
        
        Args:
            query: Search query
            
        Returns:
            List of matching entries
        """
        with self._lock:
            results = []
            query_lower = query.lower()
            for entry in self._cache.values():
                if query_lower in entry.key.lower():
                    results.append(entry)
            return results


class SharedMemoryClient:
    """
    Client for accessing shared memory on the orchestrator.
    
    This allows each AI to read/write to shared memory that is
    accessible to all AIs.
    """
    
    def __init__(self, orchestrator_endpoint: str, agent_id: str):
        """
        Initialize shared memory client.
        
        Args:
            orchestrator_endpoint: URL of orchestrator
            agent_id: This agent's ID
        """
        self.orchestrator_endpoint = orchestrator_endpoint.rstrip('/')
        self.agent_id = agent_id
        self.shared_memory_endpoint = f"{self.orchestrator_endpoint}/api/shared_memory"
    
    def write(self, key: str, value: Any, metadata: Optional[Dict[str, Any]] = None) -> bool:
        """
        Write to shared memory.
        
        Args:
            key: Memory key
            value: Value to store
            metadata: Optional metadata
            
        Returns:
            True if successful, False otherwise
        """
        try:
            import requests
            payload = {
                'key': key,
                'value': value,
                'metadata': metadata or {},
                'agent_id': self.agent_id
            }
            response = requests.post(
                f"{self.shared_memory_endpoint}/write",
                json=payload,
                timeout=5
            )
            return response.status_code == 200
        except Exception as e:
            logger.error(f"Failed to write to shared memory: {e}")
            return False
    
    def read(self, key: str) -> Optional[Any]:
        """
        Read from shared memory.
        
        Args:
            key: Memory key
            
        Returns:
            Value if found, None otherwise
        """
        try:
            import requests
            response = requests.get(
                f"{self.shared_memory_endpoint}/read",
                params={'key': key},
                timeout=5
            )
            if response.status_code == 200:
                data = response.json()
                return data.get('value')
            return None
        except Exception as e:
            logger.error(f"Failed to read from shared memory: {e}")
            return None
    
    def list_keys(self) -> List[str]:
        """
        List all keys in shared memory.
        
        Returns:
            List of keys
        """
        try:
            import requests
            response = requests.get(
                f"{self.shared_memory_endpoint}/list",
                timeout=5
            )
            if response.status_code == 200:
                data = response.json()
                return data.get('keys', [])
            return []
        except Exception as e:
            logger.error(f"Failed to list shared memory keys: {e}")
            return []


class AIMemorySystem:
    """
    Complete memory system for an AI agent.
    
    Combines short-term, long-term, and shared memory into a single interface.
    """
    
    def __init__(
        self,
        agent_id: str,
        orchestrator_endpoint: str,
        short_term_path: Optional[Path] = None,
        long_term_path: Optional[Path] = None
    ):
        """
        Initialize AI memory system.
        
        Args:
            agent_id: Unique identifier for this AI agent
            orchestrator_endpoint: URL of orchestrator for shared memory
            short_term_path: Optional path for short-term memory
            long_term_path: Optional path for long-term memory
        """
        self.agent_id = agent_id
        
        # Initialize memory tiers
        self.short_term = ShortTermMemory(agent_id, short_term_path)
        self.long_term = LongTermMemory(agent_id, long_term_path)
        self.shared = SharedMemoryClient(orchestrator_endpoint, agent_id)
        
        logger.info(f"Initialized memory system for agent {agent_id}")
    
    def note_hypothesis_contradiction(
        self,
        hypothesis_id: str,
        hypothesis: str,
        evidence: str
    ) -> None:
        """
        Note that a hypothesis contradicts evidence (as requested by user).
        
        Stores in long-term memory so the AI remembers what doesn't work.
        
        Args:
            hypothesis_id: Unique ID for the hypothesis
            hypothesis: The hypothesis text
            evidence: Evidence that contradicts it
        """
        self.long_term.write(
            key=f"hypothesis_contradiction:{hypothesis_id}",
            value={
                'hypothesis': hypothesis,
                'evidence': evidence,
                'noted_at': datetime.now().isoformat()
            },
            metadata={'type': 'hypothesis_contradiction'}
        )
        logger.info(f"Noted hypothesis contradiction: {hypothesis_id}")
    
    def get_hypothesis_note(self, hypothesis_id: str) -> Optional[Dict[str, Any]]:
        """Get note about a hypothesis contradiction."""
        return self.long_term.read(f"hypothesis_contradiction:{hypothesis_id}")


