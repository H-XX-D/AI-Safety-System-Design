"""
TIER 1: Working Memory (RAM-based with Disk Spillover)

Fast, session-scoped memory for immediate context.
- Current conversation/task state
- Recent proposals being worked on
- Temporary scratchpad for reasoning
- DISK SPILLOVER when RAM gets full
- Persistent session notes for long research sessions
- Cleared on agent restart (but notes can be promoted to personal memory)
"""

import os
import json
import time
import tempfile
import shutil
from typing import Dict, List, Any, Optional, Tuple
from dataclasses import dataclass, field, asdict
from collections import deque
from pathlib import Path
import threading
import logging

logger = logging.getLogger(__name__)


@dataclass
class MemoryItem:
    """Single item in working memory."""
    id: str
    content: str
    item_type: str  # 'context', 'proposal', 'feedback', 'reasoning', 'tool_result', 'note'
    timestamp: float = field(default_factory=time.time)
    metadata: Dict[str, Any] = field(default_factory=dict)
    importance: float = 1.0  # For priority-based eviction
    in_ram: bool = True  # False if spilled to disk
    
    def age_seconds(self) -> float:
        return time.time() - self.timestamp
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            'id': self.id,
            'content': self.content,
            'item_type': self.item_type,
            'timestamp': self.timestamp,
            'metadata': self.metadata,
            'importance': self.importance
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'MemoryItem':
        return cls(
            id=data['id'],
            content=data['content'],
            item_type=data['item_type'],
            timestamp=data.get('timestamp', time.time()),
            metadata=data.get('metadata', {}),
            importance=data.get('importance', 1.0),
            in_ram=True
        )


@dataclass
class SessionNote:
    """
    Persistent note for long research sessions.
    These survive context overflow and can be promoted to personal memory.
    """
    id: str
    title: str
    content: str
    note_type: str  # 'finding', 'question', 'todo', 'reference', 'insight'
    priority: int  # 1-5, higher = more important
    tags: List[str]
    created_at: float
    updated_at: float
    related_items: List[str]  # IDs of related memory items
    
    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'SessionNote':
        return cls(**data)


class DiskSpillover:
    """
    Manages disk-based storage for overflowed memory items.
    Uses a temp directory that persists for the session.
    """
    
    def __init__(self, session_id: str, base_dir: Optional[str] = None):
        self.session_id = session_id
        
        if base_dir:
            self.spill_dir = Path(base_dir) / f"session_{session_id}"
        else:
            # Use system temp with a persistent subdirectory
            self.spill_dir = Path(tempfile.gettempdir()) / "ai_safety_memory" / f"session_{session_id}"
        
        self.spill_dir.mkdir(parents=True, exist_ok=True)
        self.items_dir = self.spill_dir / "items"
        self.items_dir.mkdir(exist_ok=True)
        self.notes_file = self.spill_dir / "session_notes.json"
        
        self._lock = threading.RLock()
        self._spilled_ids: set = set()
        
        # Load any existing spilled items from previous crash/restart
        self._scan_existing()
    
    def _scan_existing(self) -> None:
        """Scan for existing spilled items (recovery after crash)."""
        for item_file in self.items_dir.glob("*.json"):
            self._spilled_ids.add(item_file.stem)
    
    def spill(self, item: MemoryItem) -> bool:
        """Spill a memory item to disk."""
        with self._lock:
            try:
                item_path = self.items_dir / f"{item.id}.json"
                with open(item_path, 'w') as f:
                    json.dump(item.to_dict(), f)
                self._spilled_ids.add(item.id)
                logger.debug(f"Spilled item {item.id} to disk")
                return True
            except Exception as e:
                logger.error(f"Failed to spill item {item.id}: {e}")
                return False
    
    def retrieve(self, item_id: str) -> Optional[MemoryItem]:
        """Retrieve a spilled item from disk."""
        with self._lock:
            if item_id not in self._spilled_ids:
                return None
            
            try:
                item_path = self.items_dir / f"{item_id}.json"
                with open(item_path, 'r') as f:
                    data = json.load(f)
                return MemoryItem.from_dict(data)
            except Exception as e:
                logger.error(f"Failed to retrieve item {item_id}: {e}")
                return None
    
    def remove(self, item_id: str) -> bool:
        """Remove a spilled item from disk."""
        with self._lock:
            if item_id not in self._spilled_ids:
                return False
            
            try:
                item_path = self.items_dir / f"{item_id}.json"
                item_path.unlink(missing_ok=True)
                self._spilled_ids.discard(item_id)
                return True
            except Exception as e:
                logger.error(f"Failed to remove item {item_id}: {e}")
                return False
    
    def get_spilled_ids(self) -> List[str]:
        """Get list of all spilled item IDs."""
        return list(self._spilled_ids)
    
    def get_spilled_count(self) -> int:
        """Get count of spilled items."""
        return len(self._spilled_ids)
    
    # ========== Session Notes (always on disk) ==========
    
    def save_notes(self, notes: List[SessionNote]) -> None:
        """Save session notes to disk."""
        with self._lock:
            try:
                with open(self.notes_file, 'w') as f:
                    json.dump([n.to_dict() for n in notes], f, indent=2)
            except Exception as e:
                logger.error(f"Failed to save session notes: {e}")
    
    def load_notes(self) -> List[SessionNote]:
        """Load session notes from disk."""
        with self._lock:
            if not self.notes_file.exists():
                return []
            
            try:
                with open(self.notes_file, 'r') as f:
                    data = json.load(f)
                return [SessionNote.from_dict(n) for n in data]
            except Exception as e:
                logger.error(f"Failed to load session notes: {e}")
                return []
    
    def cleanup(self) -> None:
        """Clean up all spilled data (end of session)."""
        with self._lock:
            try:
                shutil.rmtree(self.spill_dir)
                self._spilled_ids.clear()
            except Exception as e:
                logger.error(f"Failed to cleanup spill dir: {e}")
    
    def get_disk_usage(self) -> int:
        """Get total disk usage in bytes."""
        total = 0
        for item_file in self.items_dir.glob("*.json"):
            total += item_file.stat().st_size
        if self.notes_file.exists():
            total += self.notes_file.stat().st_size
        return total


class WorkingMemory:
    """
    RAM-based working memory with disk spillover for immediate context.
    
    Features:
    - Fixed RAM capacity with automatic disk spillover
    - Type-based retrieval (get all feedback, all proposals, etc.)
    - Thread-safe operations
    - Automatic decay of old items
    - Session notes that persist across context overflow
    - Disk spillover for long research sessions
    """
    
    def __init__(
        self,
        session_id: Optional[str] = None,
        max_ram_items: int = 100,
        max_ram_chars: int = 50000,  # ~12k tokens
        max_total_items: int = 1000,  # Including spilled
        decay_half_life_seconds: float = 300.0,  # 5 minutes
        spill_dir: Optional[str] = None
    ):
        self.session_id = session_id or f"{int(time.time())}_{os.getpid()}"
        self.max_ram_items = max_ram_items
        self.max_ram_chars = max_ram_chars
        self.max_total_items = max_total_items
        self.decay_half_life = decay_half_life_seconds
        
        # RAM storage
        self._ram_items: Dict[str, MemoryItem] = {}
        self._ram_char_count = 0
        self._item_counter = 0
        
        # Disk spillover
        self._spillover = DiskSpillover(self.session_id, spill_dir)
        
        # Session notes (always persisted)
        self._notes: Dict[str, SessionNote] = {}
        self._load_notes()
        
        # Current task context
        self._current_task: Optional[Dict[str, Any]] = None
        self._conversation_history: List[Dict[str, str]] = []
        
        self._lock = threading.RLock()
    
    def _generate_id(self) -> str:
        """Generate unique item ID."""
        self._item_counter += 1
        return f"wm_{self.session_id}_{self._item_counter}"
    
    def _load_notes(self) -> None:
        """Load session notes from disk."""
        notes = self._spillover.load_notes()
        self._notes = {n.id: n for n in notes}
    
    def _save_notes(self) -> None:
        """Save session notes to disk."""
        self._spillover.save_notes(list(self._notes.values()))
    
    # ========== Core Memory Operations ==========
    
    def add(
        self,
        content: str,
        item_type: str = 'context',
        importance: float = 1.0,
        metadata: Optional[Dict[str, Any]] = None
    ) -> str:
        """Add item to working memory. Returns item ID."""
        with self._lock:
            item_id = self._generate_id()
            item = MemoryItem(
                id=item_id,
                content=content,
                item_type=item_type,
                importance=importance,
                metadata=metadata or {},
                in_ram=True
            )
            
            # Check if we need to spill before adding
            self._maybe_spill()
            
            # Add to RAM
            self._ram_items[item_id] = item
            self._ram_char_count += len(content)
            
            # Check total capacity
            self._enforce_total_limit()
            
            return item_id
    
    def get(self, item_id: str) -> Optional[MemoryItem]:
        """Get item by ID (checks RAM first, then disk)."""
        with self._lock:
            # Check RAM
            if item_id in self._ram_items:
                return self._ram_items[item_id]
            
            # Check disk spillover
            item = self._spillover.retrieve(item_id)
            if item:
                # Optionally bring back to RAM if there's space
                if self._has_ram_space(len(item.content)):
                    self._ram_items[item_id] = item
                    self._ram_char_count += len(item.content)
                    item.in_ram = True
                    self._spillover.remove(item_id)
            
            return item
    
    def remove(self, item_id: str) -> bool:
        """Remove item from memory."""
        with self._lock:
            if item_id in self._ram_items:
                item = self._ram_items.pop(item_id)
                self._ram_char_count -= len(item.content)
                return True
            
            return self._spillover.remove(item_id)
    
    def _has_ram_space(self, content_len: int) -> bool:
        """Check if there's RAM space for content."""
        return (
            len(self._ram_items) < self.max_ram_items and
            self._ram_char_count + content_len < self.max_ram_chars
        )
    
    def _maybe_spill(self) -> None:
        """Spill lowest-priority items to disk if RAM is full."""
        while not self._has_ram_space(0) and self._ram_items:
            # Find lowest priority item to spill
            items = list(self._ram_items.values())
            items.sort(key=lambda x: self._eviction_score(x))
            
            # Spill the lowest scoring item
            to_spill = items[0]
            if self._spillover.spill(to_spill):
                del self._ram_items[to_spill.id]
                self._ram_char_count -= len(to_spill.content)
                to_spill.in_ram = False
                logger.debug(f"Spilled item {to_spill.id} to disk (type={to_spill.item_type})")
            else:
                break
    
    def _eviction_score(self, item: MemoryItem) -> float:
        """Score for eviction priority (lower = evict first)."""
        age = item.age_seconds()
        decay = 0.5 ** (age / self.decay_half_life)
        
        # Type-based priority boost
        type_boost = {
            'note': 2.0,      # Notes are important
            'proposal': 1.5,  # Current work
            'feedback': 1.3,  # Recent feedback
            'reasoning': 1.0,
            'context': 0.8,
            'tool_result': 0.5  # Tool results can be regenerated
        }.get(item.item_type, 1.0)
        
        return item.importance * decay * type_boost
    
    def _enforce_total_limit(self) -> None:
        """Enforce total item limit (RAM + disk)."""
        total = len(self._ram_items) + self._spillover.get_spilled_count()
        
        while total > self.max_total_items:
            # First try to remove from disk (older items)
            spilled_ids = self._spillover.get_spilled_ids()
            if spilled_ids:
                # Remove oldest spilled item
                oldest_id = spilled_ids[0]
                self._spillover.remove(oldest_id)
                total -= 1
            else:
                # Remove from RAM
                items = list(self._ram_items.values())
                items.sort(key=lambda x: self._eviction_score(x))
                if items:
                    to_remove = items[0]
                    del self._ram_items[to_remove.id]
                    self._ram_char_count -= len(to_remove.content)
                    total -= 1
                else:
                    break
    
    # ========== Session Notes ==========
    
    def add_note(
        self,
        title: str,
        content: str,
        note_type: str = 'finding',
        priority: int = 3,
        tags: Optional[List[str]] = None,
        related_items: Optional[List[str]] = None
    ) -> str:
        """
        Add a session note. Notes persist to disk immediately.
        Use for important findings during long research sessions.
        """
        with self._lock:
            note_id = f"note_{self.session_id}_{len(self._notes)}"
            now = time.time()
            
            note = SessionNote(
                id=note_id,
                title=title,
                content=content,
                note_type=note_type,
                priority=priority,
                tags=tags or [],
                created_at=now,
                updated_at=now,
                related_items=related_items or []
            )
            
            self._notes[note_id] = note
            self._save_notes()
            
            return note_id
    
    def update_note(
        self,
        note_id: str,
        content: Optional[str] = None,
        priority: Optional[int] = None,
        tags: Optional[List[str]] = None
    ) -> bool:
        """Update an existing note."""
        with self._lock:
            if note_id not in self._notes:
                return False
            
            note = self._notes[note_id]
            if content is not None:
                note.content = content
            if priority is not None:
                note.priority = priority
            if tags is not None:
                note.tags = tags
            note.updated_at = time.time()
            
            self._save_notes()
            return True
    
    def get_note(self, note_id: str) -> Optional[SessionNote]:
        """Get a note by ID."""
        return self._notes.get(note_id)
    
    def get_notes(
        self,
        note_type: Optional[str] = None,
        min_priority: int = 1,
        tags: Optional[List[str]] = None
    ) -> List[SessionNote]:
        """Get notes with optional filtering."""
        notes = list(self._notes.values())
        
        if note_type:
            notes = [n for n in notes if n.note_type == note_type]
        
        notes = [n for n in notes if n.priority >= min_priority]
        
        if tags:
            tag_set = set(tags)
            notes = [n for n in notes if tag_set & set(n.tags)]
        
        # Sort by priority (high to low), then by created_at (recent first)
        notes.sort(key=lambda n: (-n.priority, -n.created_at))
        
        return notes
    
    def delete_note(self, note_id: str) -> bool:
        """Delete a note."""
        with self._lock:
            if note_id in self._notes:
                del self._notes[note_id]
                self._save_notes()
                return True
            return False
    
    def get_notes_summary(self) -> str:
        """Get a summary of all notes for context injection."""
        notes = self.get_notes(min_priority=2)  # Only priority 2+
        
        if not notes:
            return ""
        
        lines = ["SESSION NOTES:"]
        for note in notes[:10]:  # Top 10 notes
            lines.append(f"  [{note.note_type.upper()}] {note.title}: {note.content[:100]}...")
        
        return "\n".join(lines)
    
    # ========== Conversation & Task Context ==========
    
    def add_conversation_turn(self, role: str, content: str) -> None:
        """Add a conversation turn (user/assistant message)."""
        with self._lock:
            self._conversation_history.append({
                'role': role,
                'content': content,
                'timestamp': time.time()
            })
            # Keep last N turns
            if len(self._conversation_history) > 20:
                self._conversation_history = self._conversation_history[-20:]
    
    def set_current_task(self, task: Dict[str, Any]) -> None:
        """Set the current task being worked on."""
        with self._lock:
            self._current_task = {
                **task,
                'started_at': time.time()
            }
    
    def get_current_task(self) -> Optional[Dict[str, Any]]:
        """Get current task context."""
        return self._current_task
    
    def clear_current_task(self) -> None:
        """Clear current task (task completed or abandoned)."""
        with self._lock:
            self._current_task = None
    
    # ========== Retrieval ==========
    
    def get_by_type(self, item_type: str, limit: int = 10, include_spilled: bool = False) -> List[MemoryItem]:
        """Get items of a specific type, most recent first."""
        with self._lock:
            # Get from RAM
            items = [i for i in self._ram_items.values() if i.item_type == item_type]
            
            # Optionally include spilled items
            if include_spilled:
                for spilled_id in self._spillover.get_spilled_ids():
                    item = self._spillover.retrieve(spilled_id)
                    if item and item.item_type == item_type:
                        items.append(item)
            
            items.sort(key=lambda x: x.timestamp, reverse=True)
            return items[:limit]
    
    def get_recent(self, limit: int = 10, min_importance: float = 0.0) -> List[MemoryItem]:
        """Get most recent items above importance threshold (RAM only for speed)."""
        with self._lock:
            items = [i for i in self._ram_items.values() if i.importance >= min_importance]
            items.sort(key=lambda x: x.timestamp, reverse=True)
            return items[:limit]
    
    def search(self, query: str, limit: int = 5, include_spilled: bool = False) -> List[MemoryItem]:
        """
        Simple keyword search in working memory.
        For semantic search, use RAGRetriever with personal/shared memory.
        """
        with self._lock:
            query_lower = query.lower()
            query_words = set(query_lower.split())
            
            # Search RAM
            items_to_search = list(self._ram_items.values())
            
            # Optionally include spilled
            if include_spilled:
                for spilled_id in self._spillover.get_spilled_ids():
                    item = self._spillover.retrieve(spilled_id)
                    if item:
                        items_to_search.append(item)
            
            scored = []
            for item in items_to_search:
                content_lower = item.content.lower()
                content_words = set(content_lower.split())
                overlap = len(query_words & content_words)
                if overlap > 0:
                    recency_boost = 1.0 / (1.0 + item.age_seconds() / 60.0)
                    score = overlap * item.importance * recency_boost
                    scored.append((score, item))
            
            scored.sort(key=lambda x: x[0], reverse=True)
            return [item for _, item in scored[:limit]]
    
    # ========== Context Building ==========
    
    def get_context_window(self, max_chars: int = 4000) -> str:
        """
        Build a context string for LLM prompt injection.
        Prioritizes: current task > notes > recent high-importance > conversation
        """
        with self._lock:
            parts = []
            char_count = 0
            
            # 1. Current task (highest priority)
            if self._current_task:
                task_str = f"CURRENT TASK: {self._current_task.get('description', 'Unknown')}\n"
                if len(task_str) + char_count < max_chars:
                    parts.append(task_str)
                    char_count += len(task_str)
            
            # 2. Session notes summary
            notes_summary = self.get_notes_summary()
            if notes_summary and len(notes_summary) + char_count < max_chars:
                parts.append(notes_summary + "\n")
                char_count += len(notes_summary) + 1
            
            # 3. Recent high-importance items from RAM
            important = self.get_recent(limit=5, min_importance=0.7)
            for item in important:
                item_str = f"[{item.item_type.upper()}] {item.content}\n"
                if len(item_str) + char_count < max_chars:
                    parts.append(item_str)
                    char_count += len(item_str)
            
            # 4. Recent conversation
            for turn in self._conversation_history[-5:]:
                turn_str = f"{turn['role'].upper()}: {turn['content'][:200]}...\n"
                if len(turn_str) + char_count < max_chars:
                    parts.append(turn_str)
                    char_count += len(turn_str)
            
            return "\n".join(parts)
    
    # ========== Lifecycle ==========
    
    def clear(self, keep_notes: bool = True) -> None:
        """Clear working memory."""
        with self._lock:
            self._ram_items.clear()
            self._ram_char_count = 0
            self._current_task = None
            self._conversation_history.clear()
            
            if not keep_notes:
                self._notes.clear()
                self._save_notes()
            
            # Clear spilled items
            for item_id in self._spillover.get_spilled_ids():
                self._spillover.remove(item_id)
    
    def end_session(self, cleanup_disk: bool = True) -> Dict[str, Any]:
        """
        End the session. Returns notes for potential promotion to personal memory.
        """
        with self._lock:
            # Collect notes for promotion
            notes_for_promotion = [n.to_dict() for n in self._notes.values() if n.priority >= 3]
            
            if cleanup_disk:
                self._spillover.cleanup()
            
            return {
                'session_id': self.session_id,
                'notes_for_promotion': notes_for_promotion,
                'total_items_processed': self._item_counter,
                'final_ram_items': len(self._ram_items),
                'final_spilled_items': self._spillover.get_spilled_count()
            }
    
    def get_stats(self) -> Dict[str, Any]:
        """Get memory statistics."""
        with self._lock:
            type_counts = {}
            for item in self._ram_items.values():
                type_counts[item.item_type] = type_counts.get(item.item_type, 0) + 1
            
            return {
                'session_id': self.session_id,
                'ram_items': len(self._ram_items),
                'ram_chars': self._ram_char_count,
                'ram_capacity_pct': (self._ram_char_count / self.max_ram_chars) * 100,
                'spilled_items': self._spillover.get_spilled_count(),
                'total_items': len(self._ram_items) + self._spillover.get_spilled_count(),
                'notes_count': len(self._notes),
                'items_by_type': type_counts,
                'has_current_task': self._current_task is not None,
                'conversation_turns': len(self._conversation_history),
                'disk_usage_bytes': self._spillover.get_disk_usage()
            }
    
    def to_dict(self) -> Dict[str, Any]:
        """Export working memory state (for debugging/logging)."""
        with self._lock:
            return {
                'session_id': self.session_id,
                'ram_items': [
                    {
                        'id': item.id,
                        'content': item.content[:100] + '...' if len(item.content) > 100 else item.content,
                        'type': item.item_type,
                        'importance': item.importance,
                        'age_seconds': item.age_seconds()
                    }
                    for item in self._ram_items.values()
                ],
                'spilled_count': self._spillover.get_spilled_count(),
                'notes': [n.to_dict() for n in self._notes.values()],
                'current_task': self._current_task,
                'conversation_history': self._conversation_history[-5:]
            }
