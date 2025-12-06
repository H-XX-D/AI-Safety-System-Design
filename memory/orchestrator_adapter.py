"""
Orchestrator Memory Adapter
===========================

Bridges the 3-tier memory system (memory/) with the Orchestrator.

This adapter:
1. Wraps MemoryManager for orchestrator use
2. Integrates with existing MemoryStorage (Merkle) for compatibility
3. Provides RAG-augmented context for proposals
4. Enables cross-agent shared memory on the nano cluster
5. Connects to SharedMemoryServer on ORKA

Usage:
    from memory.orchestrator_adapter import OrchestratorMemoryAdapter
    
    adapter = OrchestratorMemoryAdapter(
        agent_id="GIN",
        orchestra_url="http://192.168.0.242:5000"  # ORKA
    )
    
    # Get context for proposal evaluation
    context = adapter.get_proposal_context(proposal_content)
    
    # Store proposal outcome
    adapter.record_proposal_outcome(proposal_id, outcome, reward, reviews)
"""

import time
import logging
from typing import Dict, List, Any, Optional
from dataclasses import dataclass, asdict

from .memory_manager import MemoryManager
from .shared_memory import SharedMemoryServer

logger = logging.getLogger(__name__)


@dataclass
class ProposalContext:
    """Context retrieved for proposal evaluation."""
    similar_proposals: List[Dict[str, Any]]
    relevant_patterns: List[Dict[str, Any]]
    citations: List[Dict[str, Any]]
    working_context: List[str]
    shared_knowledge: List[Dict[str, Any]]
    prompt_section: str
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            'similar_proposals': self.similar_proposals,
            'relevant_patterns': self.relevant_patterns,
            'citations': self.citations,
            'working_context': self.working_context,
            'shared_knowledge': self.shared_knowledge,
            'prompt_section': self.prompt_section
        }


class OrchestratorMemoryAdapter:
    """
    Adapts the 3-tier memory system for use by the Orchestrator.
    
    Integrates:
    - MemoryManager for full memory capabilities
    - RAG for semantic search across all tiers
    - SharedMemory for cross-agent knowledge on nano cluster
    - Citation tracking for evidence-based proposals
    """
    
    def __init__(
        self,
        agent_id: str = "ORKA",
        data_dir: str = "./data/memory",
        orchestra_url: str = "http://localhost:5000",
        paperqa_client=None,
        embedding_model: str = "all-MiniLM-L6-v2",
        auto_sync: bool = True,
        sync_interval: float = 30.0,
        merkle_storage=None  # Optional: existing MemoryStorage for compatibility
    ):
        """
        Initialize the adapter.
        
        Args:
            agent_id: Identifier for this agent (e.g., "ORKA", "GIN")
            data_dir: Directory for memory storage
            orchestra_url: URL of SharedMemoryServer (typically ORKA)
            paperqa_client: Optional PaperQA client for full-text retrieval
            embedding_model: Model for semantic embeddings
            auto_sync: Whether to auto-sync with shared memory
            sync_interval: Sync interval in seconds
            merkle_storage: Optional existing MemoryStorage for backward compat
        """
        self.agent_id = agent_id
        self.merkle_storage = merkle_storage
        
        # Initialize the full memory manager
        self.memory = MemoryManager(
            agent_id=agent_id,
            data_dir=data_dir,
            orchestra_url=orchestra_url,
            paperqa_client=paperqa_client,
            embedding_model=embedding_model,
            auto_sync=auto_sync,
            sync_interval=sync_interval
        )
        
        # Start a session
        self.memory.start_session(f"Orchestrator session for {agent_id}")
        
        logger.info(f"OrchestratorMemoryAdapter initialized for {agent_id}")
    
    # ========== Proposal Context ==========
    
    def get_proposal_context(
        self,
        proposal_content: str,
        proposal_type: str = "improvement",
        max_similar: int = 5,
        max_patterns: int = 3,
        max_chars: int = 4000
    ) -> ProposalContext:
        """
        Retrieve relevant context for evaluating a proposal.
        
        Uses RAG to find:
        - Similar past proposals (approved/rejected)
        - Learned patterns (success/failure modes)
        - Relevant citations
        - Current working context
        - Shared knowledge from other agents
        
        Returns ProposalContext with all relevant information.
        """
        # Get RAG retrieval
        rag_result = self.memory.retrieve(
            query=proposal_content,
            k=max_similar,
            include_shared=True
        )
        
        # Get patterns
        patterns = self.memory.personal.get_patterns(
            min_confidence=0.5,
            limit=max_patterns
        )
        
        # Get contrastive examples
        positive, negative = self.memory.get_contrastive_examples(
            topic=proposal_content[:200],  # First 200 chars as topic
            n_positive=2,
            n_negative=2
        )
        
        # Build working context from recent items
        working_items = self.memory.working.get_recent(limit=10)
        working_context = [item.content for item in working_items]
        
        # Get shared knowledge
        shared_knowledge = []
        try:
            shared_proposals = self.memory.shared.get_shared_proposals(limit=5)
            shared_knowledge = [asdict(p) for p in shared_proposals]
        except Exception as e:
            logger.warning(f"Failed to get shared knowledge: {e}")
        
        # Build prompt section
        prompt_section = self.memory.get_context_for_prompt(
            query=proposal_content,
            max_chars=max_chars
        )
        
        # Add contrastive examples to prompt
        if positive or negative:
            prompt_section += "\n\n=== EXAMPLES FOR REFERENCE ==="
            if positive:
                prompt_section += "\n[SUCCESSFUL APPROACHES]"
                for ex in positive[:2]:
                    prompt_section += f"\n- {ex.get('title', 'Untitled')}: {ex.get('summary', '')[:100]}..."
            if negative:
                prompt_section += "\n[APPROACHES TO AVOID]"
                for ex in negative[:2]:
                    prompt_section += f"\n- {ex.get('title', 'Untitled')}: {ex.get('reason', '')}..."
        
        return ProposalContext(
            similar_proposals=[r.to_dict() for r in rag_result.results] if hasattr(rag_result, 'results') else [],
            relevant_patterns=[{
                'type': p.pattern_type,
                'description': p.description,
                'confidence': p.confidence
            } for p in patterns],
            citations=[],  # TODO: Link to proposal citations
            working_context=working_context,
            shared_knowledge=shared_knowledge,
            prompt_section=prompt_section
        )
    
    # ========== Proposal Lifecycle ==========
    
    def store_proposal(
        self,
        title: str,
        content: str,
        proposer_id: str,
        confidence: float = 0.5,
        domain: str = "improvement",
        metadata: Optional[Dict[str, Any]] = None
    ) -> str:
        """
        Store a new proposal in memory.
        
        Returns proposal_id.
        """
        # Add to working memory for immediate context
        self.memory.add_to_working(
            f"New proposal from {proposer_id}: {title}",
            item_type='proposal',
            importance=0.9
        )
        
        # Store in personal memory with embedding
        proposal_id = self.memory.store_proposal(
            title=title,
            content=content,
            confidence=confidence,
            domain=domain
        )
        
        # Also store in Merkle storage if available (backward compat)
        if self.merkle_storage:
            try:
                from infrastructure.memory_merkle import MemoryType
                self.merkle_storage.store_memory(
                    content={'title': title, 'content': content, 'proposer': proposer_id},
                    memory_type=MemoryType.PROPOSAL,
                    system_id=hash(proposer_id) % 1000,
                    metadata=metadata or {}
                )
            except Exception as e:
                logger.warning(f"Failed to store in Merkle: {e}")
        
        return proposal_id
    
    def record_proposal_outcome(
        self,
        proposal_id: str,
        outcome: str,  # 'approved', 'rejected', 'deferred'
        confidence_final: float,
        reward: float,
        reviews: List[Dict[str, Any]],
        orka_assessment: Optional[Dict[str, Any]] = None
    ) -> None:
        """
        Record the outcome of a proposal evaluation.
        
        Updates personal memory with outcome and learns patterns.
        If approved with high reward, submits to shared memory.
        """
        # Update proposal in personal memory
        self.memory.update_proposal_outcome(
            proposal_id=proposal_id,
            outcome=outcome,
            confidence_final=confidence_final,
            reward=reward,
            reviews=reviews
        )
        
        # Add to working memory
        self.memory.add_to_working(
            f"Proposal {proposal_id[:8]} {outcome} (reward: {reward:.2f})",
            item_type='outcome',
            importance=0.7
        )
        
        # Submit to shared memory if approved with good reward
        if outcome == 'approved' and reward >= 0.5:
            try:
                self.memory.submit_to_shared(
                    proposal_id=proposal_id,
                    peer_reviews=reviews,
                    orka_assessment=orka_assessment or {}
                )
                logger.info(f"Submitted {proposal_id} to shared memory")
            except Exception as e:
                logger.warning(f"Failed to submit to shared: {e}")
        
        # Also record in Merkle if available
        if self.merkle_storage:
            try:
                from infrastructure.memory_merkle import MemoryType
                self.merkle_storage.store_memory(
                    content={
                        'proposal_id': proposal_id,
                        'outcome': outcome,
                        'reward': reward,
                        'reviews_count': len(reviews)
                    },
                    memory_type=MemoryType.CONSENSUS,
                    system_id=0,  # Orchestrator
                    metadata={'confidence': confidence_final}
                )
            except Exception as e:
                logger.warning(f"Failed to record in Merkle: {e}")
    
    # ========== Deception Detection Support ==========
    
    def get_agent_history(
        self,
        agent_id: str,
        limit: int = 50
    ) -> List[Dict[str, Any]]:
        """
        Get proposal history for an agent (for deception pattern analysis).
        """
        # This would need PersonalMemory per-agent, or query shared
        # For now, return from shared knowledge
        try:
            all_approved = self.memory.shared.get_shared_proposals(limit=200)
            agent_proposals = [
                asdict(p) for p in all_approved
                if p.metadata.get('proposer') == agent_id
            ]
            return agent_proposals[:limit]
        except Exception:
            return []
    
    def record_deception_incident(
        self,
        agent_id: str,
        incident_type: str,
        severity: str,
        details: Dict[str, Any]
    ) -> None:
        """Record a deception detection incident."""
        self.memory.add_note(
            title=f"Deception: {incident_type}",
            content=f"Agent {agent_id} - {severity}: {details}",
            note_type='security_incident',
            priority=5 if severity == 'critical' else 4,
            tags=['deception', agent_id, severity]
        )
        
        # Record pattern for future detection
        self.memory.personal.record_pattern(
            pattern_type='deception_indicator',
            description=f"{incident_type} from {agent_id}",
            example_id=f"incident_{int(time.time())}",
            confidence=0.8
        )
    
    # ========== Session & Stats ==========
    
    def checkpoint(self) -> None:
        """Save current memory state."""
        self.memory.checkpoint()
    
    def get_stats(self) -> Dict[str, Any]:
        """Get memory statistics."""
        stats = self.memory.get_stats()
        stats['adapter'] = {
            'agent_id': self.agent_id,
            'merkle_connected': self.merkle_storage is not None
        }
        return stats
    
    def close(self) -> None:
        """Clean shutdown."""
        self.memory.end_session(promote_notes=True)
        self.memory.close()
        logger.info(f"Adapter closed for {self.agent_id}")


class SharedMemoryOrchestra:
    """
    Wraps the SharedMemoryServer for use on ORKA.
    
    This is the central knowledge hub that all agents sync with.
    The server stores data locally; HTTP API is handled by the Flask UI.
    """
    
    def __init__(
        self,
        data_dir: str = "./data/shared_memory"
    ):
        self.data_dir = data_dir
        self.server = SharedMemoryServer(data_dir=data_dir)
        self._running = False
    
    def start(self) -> None:
        """Mark server as running (actual serving via Flask)."""
        self._running = True
        logger.info(f"SharedMemoryOrchestra initialized with data_dir={self.data_dir}")
    
    def stop(self) -> None:
        """Mark server as stopped."""
        self._running = False
    
    def is_running(self) -> bool:
        """Check if server is running."""
        return self._running
    
    def get_stats(self) -> Dict[str, Any]:
        """Get server statistics."""
        return self.server.get_stats()


def create_adapter_for_nano(
    nano_name: str,
    nano_ip: str,
    orchestra_ip: str = "localhost",  # ORKA runs on localhost (Z6)
    data_dir: Optional[str] = None
) -> OrchestratorMemoryAdapter:
    """
    Factory function to create an adapter for a specific nano.
    
    Args:
        nano_name: Name of the nano (e.g., "GIN", "TORI")
        nano_ip: IP address of the nano
        orchestra_ip: IP of ORKA (SharedMemoryServer host)
        data_dir: Optional custom data directory
    
    Returns:
        Configured OrchestratorMemoryAdapter
    """
    if data_dir is None:
        data_dir = f"./data/memory/{nano_name.lower()}"
    
    return OrchestratorMemoryAdapter(
        agent_id=nano_name,
        data_dir=data_dir,
        orchestra_url=f"http://{orchestra_ip}:5001",  # Flask UI port
        auto_sync=True,
        sync_interval=30.0
    )


# Nano cluster configuration (from config/default.yaml)
NANO_CLUSTER = {
    'ORKA': {'ip': 'localhost', 'model': 'qwen2.5:14b'},
    'GIN': {'ip': '192.168.0.242', 'model': 'deepseek-r1:1.5b'},
    'ORIN': {'ip': '192.168.0.160', 'model': 'deepseek-r1:1.5b'},
    'TIF': {'ip': '192.168.0.213', 'model': 'deepseek-r1:1.5b'},
    'TORI': {'ip': '192.168.0.235', 'model': 'gemma3:4b'},
    'PAGEQA': {'ip': '192.168.0.168', 'model': 'qwen2.5:3b'},
    'ARCHI': {'ip': '192.168.0.232', 'model': 'qwen2.5:3b'},
    'GUARD': {'ip': '192.168.0.146', 'model': 'llama-guard3:1b'},
}
