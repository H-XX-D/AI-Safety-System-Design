"""
Memory Manager - Unified interface for the 3-tier memory system.

Coordinates:
- Working Memory (RAM + disk spillover)
- Personal Memory (on-device, persistent)
- Shared Memory (orchestra-level, cross-agent)
- Citation Store (lightweight references, PaperQA retrieves full content)
- Dedup LUT Tree (prevents redundant storage)
- Session Distiller (compresses history)
- RAG Retriever (unified search)

Handles:
- Automatic tier promotion (working -> personal -> shared)
- Session lifecycle (start, checkpoint, end)
- Memory synchronization
- Context building for LLM prompts
"""

import time
import threading
from typing import Dict, List, Any, Optional, Tuple
from pathlib import Path
import logging

from .working_memory import WorkingMemory
from .personal_memory import PersonalMemory
from .shared_memory import SharedMemoryClient
from .citation_store import CitationStore
from .dedup_lut_tree import DedupLUTTree
from .session_distiller import SessionDistiller
from .rag_retriever import RAGRetriever, EmbeddingProvider

logger = logging.getLogger(__name__)


class MemoryManager:
    """
    Unified memory management across all tiers.
    
    Architecture:
    ┌─────────────────────────────────────────────────────────────────────┐
    │                        MEMORY MANAGER                               │
    ├─────────────────────────────────────────────────────────────────────┤
    │                                                                     │
    │  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐                 │
    │  │   WORKING   │  │  PERSONAL   │  │   SHARED    │                 │
    │  │   MEMORY    │  │   MEMORY    │  │   MEMORY    │                 │
    │  │  (RAM+Disk) │  │ (On-Device) │  │ (Orchestra) │                 │
    │  └──────┬──────┘  └──────┬──────┘  └──────┬──────┘                 │
    │         │                │                │                         │
    │         └────────────────┼────────────────┘                         │
    │                          │                                          │
    │                   ┌──────┴──────┐                                   │
    │                   │ RAG RETRIEVER│                                   │
    │                   └──────┬──────┘                                   │
    │                          │                                          │
    │  ┌─────────────┐  ┌──────┴──────┐  ┌─────────────┐                 │
    │  │  CITATION   │  │   DEDUP     │  │  SESSION    │                 │
    │  │   STORE     │  │  LUT TREE   │  │  DISTILLER  │                 │
    │  │ (Refs only) │  │ (No dupes)  │  │ (Compress)  │                 │
    │  └─────────────┘  └─────────────┘  └─────────────┘                 │
    │                                                                     │
    └─────────────────────────────────────────────────────────────────────┘
    """
    
    def __init__(
        self,
        agent_id: str,
        data_dir: str = "./data/memory",
        orchestra_url: str = "http://localhost:5000",
        paperqa_client=None,
        embedding_model: str = "all-MiniLM-L6-v2",
        auto_sync: bool = True,
        sync_interval: float = 60.0
    ):
        self.agent_id = agent_id
        self.data_dir = Path(data_dir)
        self.data_dir.mkdir(parents=True, exist_ok=True)
        
        # Initialize embedding provider
        self.embedder = EmbeddingProvider(model_name=embedding_model)
        
        # Initialize memory tiers
        self.working = WorkingMemory(
            session_id=f"{agent_id}_{int(time.time())}",
            spill_dir=str(self.data_dir / "working_spill")
        )
        
        self.personal = PersonalMemory(
            agent_id=agent_id,
            data_dir=str(self.data_dir / "personal"),
            embedding_dim=self.embedder.dimension
        )
        
        self.shared = SharedMemoryClient(
            agent_id=agent_id,
            orchestra_url=orchestra_url,
            local_cache_dir=str(self.data_dir / "shared_cache"),
            sync_interval_seconds=sync_interval
        )
        
        # Initialize supporting systems
        self.citations = CitationStore(
            data_dir=str(self.data_dir / "citations"),
            paperqa_client=paperqa_client
        )
        
        self.dedup = DedupLUTTree(
            data_dir=str(self.data_dir / "dedup")
        )
        
        self.distiller = SessionDistiller()
        
        # Initialize RAG retriever
        self.rag = RAGRetriever(
            working_memory=self.working,
            personal_memory=self.personal,
            shared_memory=self.shared,
            embedding_provider=self.embedder
        )
        
        # State
        self._session_start = time.time()
        self._lock = threading.RLock()
        
        # Auto-sync thread
        self._auto_sync = auto_sync
        self._sync_interval = sync_interval
        self._sync_thread = None
        self._stop_sync = threading.Event()
        
        if auto_sync:
            self._start_sync_thread()
    
    def _start_sync_thread(self) -> None:
        """Start background sync thread."""
        def sync_loop():
            while not self._stop_sync.wait(self._sync_interval):
                try:
                    self.shared.sync()
                except Exception as e:
                    logger.warning(f"Sync failed: {e}")
        
        self._sync_thread = threading.Thread(target=sync_loop, daemon=True)
        self._sync_thread.start()
    
    # ========== Session Lifecycle ==========
    
    def start_session(self, task_description: Optional[str] = None) -> str:
        """Start a new session."""
        session_id = self.working.session_id
        
        if task_description:
            self.working.set_current_task({
                'description': task_description,
                'session_id': session_id
            })
        
        logger.info(f"Started session {session_id}")
        return session_id
    
    def checkpoint(self) -> None:
        """Save current state (periodic checkpoint)."""
        with self._lock:
            # Save personal memory embeddings
            self.personal.close()
            
            # Save dedup tree
            self.dedup._save()
            
            # Sync shared memory
            self.shared.sync()
            
            logger.debug("Checkpoint saved")
    
    def end_session(self, promote_notes: bool = True) -> Dict[str, Any]:
        """
        End the current session.
        
        - Distills session into compressed knowledge
        - Optionally promotes important notes to personal memory
        - Cleans up working memory
        
        Returns session summary.
        """
        with self._lock:
            # Get session data
            session_data = self.working.end_session(cleanup_disk=False)
            
            # Get proposals from this session
            proposals = self.personal.get_recent_proposals(limit=100)
            session_proposals = [
                p.to_dict() for p in proposals
                if p.created_at >= self._session_start
            ]
            
            # Get feedback
            feedback = []
            for p in session_proposals:
                feedback.extend(self.personal.get_feedback_for_proposal(p['id']))
            
            # Distill session
            distilled = self.distiller.distill_session(
                session_id=self.working.session_id,
                agent_id=self.agent_id,
                notes=[n for n in session_data.get('notes_for_promotion', [])],
                proposals=session_proposals,
                feedback=feedback,
                started_at=self._session_start,
                ended_at=time.time()
            )
            
            # Store distilled insights in dedup tree
            for insight in distilled.insights:
                self.dedup.add(
                    content=f"{insight.title}: {insight.summary}",
                    domain=insight.domain,
                    source_session=self.working.session_id,
                    confidence=insight.confidence
                )
            
            # Promote high-priority notes to personal memory patterns
            if promote_notes:
                for note in session_data.get('notes_for_promotion', []):
                    self.personal.record_pattern(
                        pattern_type=note.get('note_type', 'finding'),
                        description=note.get('content', ''),
                        example_id=note.get('id', ''),
                        confidence=note.get('priority', 3) / 5.0
                    )
            
            # Cleanup working memory
            self.working.clear(keep_notes=False)
            self.working._spillover.cleanup()
            
            # Reset session start
            self._session_start = time.time()
            
            logger.info(f"Ended session: {len(distilled.insights)} insights distilled")
            
            return distilled.to_dict()
    
    # ========== Knowledge Operations ==========
    
    def add_to_working(
        self,
        content: str,
        item_type: str = 'context',
        importance: float = 1.0
    ) -> str:
        """Add item to working memory."""
        return self.working.add(content, item_type, importance)
    
    def add_note(
        self,
        title: str,
        content: str,
        note_type: str = 'finding',
        priority: int = 3,
        tags: Optional[List[str]] = None
    ) -> str:
        """Add a session note (persists to disk)."""
        return self.working.add_note(title, content, note_type, priority, tags)
    
    def store_proposal(
        self,
        title: str,
        content: str,
        confidence: float = 0.5,
        domain: str = "general"
    ) -> str:
        """
        Store a proposal in personal memory.
        
        - Generates embedding for semantic search
        - Checks for duplicates via dedup tree
        - Stores in personal memory
        """
        with self._lock:
            # Generate embedding
            embedding = self.embedder.embed(content)
            
            # Check for duplicates
            dedup_result = self.dedup.check_duplicate(content, domain)
            
            if dedup_result.recommended_action == 'skip':
                logger.info(f"Skipping duplicate proposal: {title}")
                return dedup_result.exact_match_id
            
            # Store in personal memory
            proposal_id = self.personal.store_proposal(
                title=title,
                content=content,
                confidence=confidence,
                metadata={'domain': domain, 'dedup_action': dedup_result.recommended_action},
                embedding=embedding
            )
            
            # Add to dedup tree
            self.dedup.add(
                content=content,
                domain=domain,
                source_session=self.working.session_id,
                confidence=confidence,
                parent_id=dedup_result.merge_target_id if dedup_result.recommended_action == 'link' else None
            )
            
            # Add to working memory for immediate context
            self.working.add(
                f"Stored proposal: {title}",
                item_type='proposal',
                importance=0.8
            )
            
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
        self.personal.update_proposal_outcome(
            proposal_id, outcome, confidence_final, reward, reviews
        )
        
        # Record patterns based on outcome
        if outcome == 'approved' and reward > 0.5:
            self.personal.record_pattern(
                pattern_type='success_factor',
                description=f"High-reward proposal approach",
                example_id=proposal_id,
                confidence=reward
            )
        elif outcome == 'rejected':
            # Extract rejection reason from reviews
            for review in reviews:
                if review.get('vote') == 'reject':
                    self.personal.record_pattern(
                        pattern_type='failure_mode',
                        description=review.get('reason', 'Unknown rejection reason'),
                        example_id=proposal_id,
                        confidence=0.7
                    )
    
    def submit_to_shared(
        self,
        proposal_id: str,
        peer_reviews: List[Dict[str, Any]],
        orka_assessment: Dict[str, Any]
    ) -> bool:
        """Submit an approved proposal to shared memory."""
        proposal = self.personal.get_proposal(proposal_id)
        if not proposal or proposal.outcome != 'approved':
            return False
        
        return self.shared.submit_approved_proposal(
            proposal_id=proposal_id,
            title=proposal.title,
            content=proposal.content,
            domain=proposal.metadata.get('domain', 'general'),
            reward=proposal.reward,
            peer_reviews=peer_reviews,
            orka_assessment=orka_assessment,
            metadata=proposal.metadata
        )
    
    # ========== Citation Operations ==========
    
    def add_citation(
        self,
        source_type: str,
        source_id: str,
        title: str,
        authors: List[str],
        relevant_pages: Optional[List[int]] = None,
        relevant_sections: Optional[List[str]] = None,
        key_quotes: Optional[List[Dict[str, Any]]] = None,
        query: str = "",
        relevance: float = 0.0,
        domain: str = "general"
    ) -> str:
        """Add a citation reference (PaperQA retrieves full content)."""
        citation_id, is_new = self.citations.add_citation(
            source_type=source_type,
            source_id=source_id,
            title=title,
            authors=authors,
            relevant_pages=relevant_pages,
            relevant_sections=relevant_sections,
            key_quotes=key_quotes,
            original_query=query,
            relevance_score=relevance,
            domain=domain
        )
        
        if is_new:
            self.working.add(
                f"Added citation: {title}",
                item_type='context',
                importance=0.5
            )
        
        return citation_id
    
    def get_citations_for_proposal(self, proposal_id: str) -> List[Any]:
        """Get all citations used in a proposal."""
        bundles = self.citations.get_bundles_for_proposal(proposal_id)
        citations = []
        for bundle in bundles:
            for cid in bundle.citations:
                citation = self.citations.get_citation(cid)
                if citation:
                    citations.append(citation)
        return citations
    
    # ========== RAG & Context ==========
    
    def retrieve(
        self,
        query: str,
        k: int = 10,
        include_shared: bool = True
    ) -> Any:
        """Retrieve relevant context from all memory tiers."""
        from .rag_retriever import MemoryTier
        
        tiers = [MemoryTier.WORKING, MemoryTier.PERSONAL]
        if include_shared:
            tiers.append(MemoryTier.SHARED)
        
        return self.rag.retrieve(query, k=k, tiers=tiers)
    
    def get_context_for_prompt(
        self,
        query: str,
        max_chars: int = 4000
    ) -> str:
        """
        Get complete context for LLM prompt augmentation.
        
        Includes:
        - Working memory context
        - Session notes
        - Retrieved similar proposals
        - Relevant patterns
        """
        # Get RAG context
        rag_context = self.retrieve(query, k=5)
        
        # Get relevant patterns
        patterns = self.personal.get_patterns(min_confidence=0.6, limit=3)
        
        # Build context string
        parts = []
        char_count = 0
        
        # RAG context
        rag_section = rag_context.to_prompt_section(max_chars=max_chars // 2)
        if rag_section:
            parts.append(rag_section)
            char_count += len(rag_section)
        
        # Patterns
        if patterns and char_count < max_chars:
            parts.append("\n=== LEARNED PATTERNS ===")
            for pattern in patterns:
                pattern_str = f"[{pattern.pattern_type}] {pattern.description} (confidence: {pattern.confidence:.2f})"
                if char_count + len(pattern_str) < max_chars:
                    parts.append(pattern_str)
                    char_count += len(pattern_str)
        
        return "\n".join(parts)
    
    def get_contrastive_examples(
        self,
        topic: str,
        n_positive: int = 3,
        n_negative: int = 3
    ) -> Tuple[List[Any], List[Any]]:
        """Get successful and failed examples for steering/learning."""
        return self.rag.get_contrastive_examples(topic, n_positive, n_negative)
    
    # ========== Stats & Debug ==========
    
    def get_stats(self) -> Dict[str, Any]:
        """Get comprehensive memory statistics."""
        return {
            'agent_id': self.agent_id,
            'session_id': self.working.session_id,
            'session_duration_seconds': time.time() - self._session_start,
            'working_memory': self.working.get_stats(),
            'personal_memory': self.personal.get_stats(),
            'shared_memory': self.shared.get_stats(),
            'citations': self.citations.get_stats(),
            'dedup_tree': self.dedup.get_stats(),
            'rag_retriever': self.rag.get_stats()
        }
    
    def close(self) -> None:
        """Clean shutdown."""
        # Stop sync thread
        if self._sync_thread:
            self._stop_sync.set()
            self._sync_thread.join(timeout=5.0)
        
        # Save everything
        self.checkpoint()
        
        # Close personal memory
        self.personal.close()
        
        logger.info(f"Memory manager closed for agent {self.agent_id}")

