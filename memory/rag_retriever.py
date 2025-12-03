"""
RAG Retriever - Unified retrieval across all memory tiers.

Searches across:
- Working Memory (fast, keyword-based)
- Personal Memory (semantic search with embeddings)
- Shared Memory (collective knowledge)

Returns ranked, deduplicated results for context injection.
"""

import time
import hashlib
import numpy as np
from typing import Dict, List, Any, Optional, Tuple, Union
from dataclasses import dataclass
from enum import Enum
import threading
import logging

logger = logging.getLogger(__name__)


class MemoryTier(Enum):
    WORKING = "working"
    PERSONAL = "personal"
    SHARED = "shared"


@dataclass
class RetrievalResult:
    """A single retrieval result with source information."""
    content: str
    source_tier: MemoryTier
    source_id: str
    relevance_score: float
    metadata: Dict[str, Any]
    
    # For proposals
    title: Optional[str] = None
    outcome: Optional[str] = None
    reward: Optional[float] = None
    
    def to_context_string(self) -> str:
        """Format for LLM context injection."""
        prefix = f"[{self.source_tier.value.upper()}]"
        if self.title:
            prefix += f" {self.title}"
        if self.outcome:
            prefix += f" ({self.outcome})"
        
        return f"{prefix}\n{self.content[:500]}..."


@dataclass 
class RAGContext:
    """Complete RAG context for prompt augmentation."""
    query: str
    results: List[RetrievalResult]
    working_context: str  # From working memory
    notes_summary: str    # Session notes
    total_chars: int
    retrieval_time_ms: float
    
    def to_prompt_section(self, max_chars: int = 4000) -> str:
        """Format as prompt section for LLM."""
        sections = []
        char_count = 0
        
        # Working memory context first (most relevant to current task)
        if self.working_context:
            sections.append("=== CURRENT CONTEXT ===")
            sections.append(self.working_context)
            char_count += len(self.working_context) + 30
        
        # Session notes
        if self.notes_summary and char_count + len(self.notes_summary) < max_chars:
            sections.append("\n=== SESSION NOTES ===")
            sections.append(self.notes_summary)
            char_count += len(self.notes_summary) + 25
        
        # Retrieved results
        if self.results:
            sections.append("\n=== RELEVANT PAST KNOWLEDGE ===")
            for result in self.results:
                result_str = result.to_context_string()
                if char_count + len(result_str) < max_chars:
                    sections.append(result_str)
                    char_count += len(result_str)
                else:
                    break
        
        return "\n".join(sections)


class EmbeddingProvider:
    """
    Provides text embeddings for semantic search.
    Uses sentence-transformers if available, falls back to simple TF-IDF.
    """
    
    def __init__(self, model_name: str = "all-MiniLM-L6-v2"):
        self.model_name = model_name
        self._model = None
        self._fallback_mode = False
        self._dimension = 384  # Default for MiniLM
        
        self._init_model()
    
    def _init_model(self) -> None:
        """Initialize embedding model."""
        try:
            from sentence_transformers import SentenceTransformer
            self._model = SentenceTransformer(self.model_name)
            self._dimension = self._model.get_sentence_embedding_dimension()
            logger.info(f"Loaded embedding model: {self.model_name}")
        except ImportError:
            logger.warning("sentence-transformers not available, using fallback TF-IDF embeddings")
            self._fallback_mode = True
            self._dimension = 384
    
    def embed(self, text: str) -> np.ndarray:
        """Generate embedding for text."""
        if self._fallback_mode:
            return self._fallback_embed(text)
        
        return self._model.encode(text, convert_to_numpy=True)
    
    def embed_batch(self, texts: List[str]) -> np.ndarray:
        """Generate embeddings for multiple texts."""
        if self._fallback_mode:
            return np.array([self._fallback_embed(t) for t in texts])
        
        return self._model.encode(texts, convert_to_numpy=True)
    
    def _fallback_embed(self, text: str) -> np.ndarray:
        """
        Simple fallback embedding using hash-based projection.
        Not as good as real embeddings, but works without dependencies.
        """
        # Tokenize
        words = text.lower().split()
        
        # Hash each word to a dimension
        embedding = np.zeros(self._dimension)
        for word in words:
            # Use hash to get consistent dimension indices
            h = int(hashlib.md5(word.encode()).hexdigest(), 16)
            idx = h % self._dimension
            embedding[idx] += 1.0
        
        # Normalize
        norm = np.linalg.norm(embedding)
        if norm > 0:
            embedding = embedding / norm
        
        return embedding
    
    @property
    def dimension(self) -> int:
        return self._dimension


class RAGRetriever:
    """
    Unified retriever across all memory tiers.
    
    Features:
    - Multi-tier search (working, personal, shared)
    - Semantic + keyword hybrid search
    - Result ranking and deduplication
    - Configurable tier weights
    - Caching for performance
    """
    
    def __init__(
        self,
        working_memory=None,  # WorkingMemory instance
        personal_memory=None,  # PersonalMemory instance
        shared_memory=None,    # SharedMemoryClient instance
        embedding_provider: Optional[EmbeddingProvider] = None,
        tier_weights: Optional[Dict[str, float]] = None
    ):
        self.working = working_memory
        self.personal = personal_memory
        self.shared = shared_memory
        
        self.embedder = embedding_provider or EmbeddingProvider()
        
        # Default tier weights (how much to trust each source)
        self.tier_weights = tier_weights or {
            'working': 1.5,   # Current context is most relevant
            'personal': 1.2,  # Personal history is valuable
            'shared': 1.0     # Collective knowledge baseline
        }
        
        self._lock = threading.RLock()
        self._cache: Dict[str, Tuple[float, List[RetrievalResult]]] = {}
        self._cache_ttl = 60.0  # Cache results for 60 seconds
    
    def retrieve(
        self,
        query: str,
        k: int = 10,
        tiers: Optional[List[MemoryTier]] = None,
        outcome_filter: Optional[str] = None,  # 'approved', 'rejected', etc.
        min_relevance: float = 0.1,
        use_cache: bool = True
    ) -> RAGContext:
        """
        Retrieve relevant context from all memory tiers.
        
        Args:
            query: Search query
            k: Number of results to return
            tiers: Which tiers to search (default: all)
            outcome_filter: Filter by proposal outcome
            min_relevance: Minimum relevance score
            use_cache: Whether to use cached results
        
        Returns:
            RAGContext with ranked results
        """
        start_time = time.time()
        
        # Check cache
        cache_key = f"{query}_{k}_{tiers}_{outcome_filter}"
        if use_cache and cache_key in self._cache:
            cached_time, cached_results = self._cache[cache_key]
            if time.time() - cached_time < self._cache_ttl:
                return self._build_context(query, cached_results, start_time)
        
        tiers = tiers or [MemoryTier.WORKING, MemoryTier.PERSONAL, MemoryTier.SHARED]
        
        all_results: List[RetrievalResult] = []
        
        # Generate query embedding for semantic search
        query_embedding = self.embedder.embed(query)
        
        # Search each tier
        if MemoryTier.WORKING in tiers and self.working:
            all_results.extend(self._search_working(query, k))
        
        if MemoryTier.PERSONAL in tiers and self.personal:
            all_results.extend(self._search_personal(query, query_embedding, k, outcome_filter))
        
        if MemoryTier.SHARED in tiers and self.shared:
            all_results.extend(self._search_shared(query, k))
        
        # Rank and deduplicate
        ranked = self._rank_results(all_results, min_relevance)
        final_results = ranked[:k]
        
        # Cache results
        self._cache[cache_key] = (time.time(), final_results)
        
        return self._build_context(query, final_results, start_time)
    
    def _search_working(self, query: str, k: int) -> List[RetrievalResult]:
        """Search working memory (keyword-based)."""
        results = []
        
        try:
            items = self.working.search(query, limit=k, include_spilled=True)
            
            for item in items:
                results.append(RetrievalResult(
                    content=item.content,
                    source_tier=MemoryTier.WORKING,
                    source_id=item.id,
                    relevance_score=item.importance * 0.8,  # Keyword match baseline
                    metadata={'item_type': item.item_type, 'age_seconds': item.age_seconds()}
                ))
        except Exception as e:
            logger.warning(f"Working memory search failed: {e}")
        
        return results
    
    def _search_personal(
        self,
        query: str,
        query_embedding: np.ndarray,
        k: int,
        outcome_filter: Optional[str]
    ) -> List[RetrievalResult]:
        """Search personal memory (semantic)."""
        results = []
        
        try:
            similar = self.personal.search_proposals_semantic(
                query_embedding,
                k=k,
                outcome_filter=outcome_filter
            )
            
            for proposal, similarity in similar:
                results.append(RetrievalResult(
                    content=proposal.content,
                    source_tier=MemoryTier.PERSONAL,
                    source_id=proposal.id,
                    relevance_score=similarity,
                    metadata=proposal.metadata or {},
                    title=proposal.title,
                    outcome=proposal.outcome,
                    reward=proposal.reward
                ))
        except Exception as e:
            logger.warning(f"Personal memory search failed: {e}")
        
        return results
    
    def _search_shared(self, query: str, k: int) -> List[RetrievalResult]:
        """Search shared memory."""
        results = []
        
        try:
            similar = self.shared.search_shared_proposals(query, limit=k)
            
            for proposal, score in similar:
                results.append(RetrievalResult(
                    content=proposal.content,
                    source_tier=MemoryTier.SHARED,
                    source_id=proposal.id,
                    relevance_score=score,
                    metadata=proposal.metadata,
                    title=proposal.title,
                    outcome=proposal.deployment_status,
                    reward=proposal.reward
                ))
        except Exception as e:
            logger.warning(f"Shared memory search failed: {e}")
        
        return results
    
    def _rank_results(
        self,
        results: List[RetrievalResult],
        min_relevance: float
    ) -> List[RetrievalResult]:
        """Rank and deduplicate results."""
        # Apply tier weights
        for result in results:
            tier_weight = self.tier_weights.get(result.source_tier.value, 1.0)
            result.relevance_score *= tier_weight
            
            # Boost approved proposals
            if result.outcome == 'approved':
                result.relevance_score *= 1.2
            
            # Boost high-reward proposals
            if result.reward and result.reward > 0.5:
                result.relevance_score *= (1.0 + result.reward * 0.3)
        
        # Filter by minimum relevance
        results = [r for r in results if r.relevance_score >= min_relevance]
        
        # Sort by relevance
        results.sort(key=lambda r: r.relevance_score, reverse=True)
        
        # Deduplicate by content similarity (simple hash-based)
        seen_hashes = set()
        unique_results = []
        
        for result in results:
            content_hash = hashlib.md5(result.content[:200].encode()).hexdigest()
            if content_hash not in seen_hashes:
                seen_hashes.add(content_hash)
                unique_results.append(result)
        
        return unique_results
    
    def _build_context(
        self,
        query: str,
        results: List[RetrievalResult],
        start_time: float
    ) -> RAGContext:
        """Build RAGContext from results."""
        # Get working memory context
        working_context = ""
        notes_summary = ""
        
        if self.working:
            working_context = self.working.get_context_window(max_chars=2000)
            notes_summary = self.working.get_notes_summary()
        
        total_chars = sum(len(r.content) for r in results)
        total_chars += len(working_context) + len(notes_summary)
        
        return RAGContext(
            query=query,
            results=results,
            working_context=working_context,
            notes_summary=notes_summary,
            total_chars=total_chars,
            retrieval_time_ms=(time.time() - start_time) * 1000
        )
    
    # ========== Specialized Retrievers ==========
    
    def get_similar_proposals(
        self,
        proposal_content: str,
        k: int = 5,
        outcome: Optional[str] = None
    ) -> List[RetrievalResult]:
        """Get proposals similar to given content."""
        context = self.retrieve(
            query=proposal_content[:500],  # Use first 500 chars as query
            k=k,
            tiers=[MemoryTier.PERSONAL, MemoryTier.SHARED],
            outcome_filter=outcome
        )
        return context.results
    
    def get_successful_examples(self, topic: str, k: int = 5) -> List[RetrievalResult]:
        """Get successful (approved) proposals on a topic."""
        return self.get_similar_proposals(topic, k=k, outcome='approved')
    
    def get_failed_examples(self, topic: str, k: int = 5) -> List[RetrievalResult]:
        """Get failed (rejected) proposals on a topic - to learn what NOT to do."""
        return self.get_similar_proposals(topic, k=k, outcome='rejected')
    
    def get_contrastive_examples(
        self,
        topic: str,
        n_positive: int = 3,
        n_negative: int = 3
    ) -> Tuple[List[RetrievalResult], List[RetrievalResult]]:
        """Get both successful and failed examples for contrast."""
        positive = self.get_successful_examples(topic, k=n_positive)
        negative = self.get_failed_examples(topic, k=n_negative)
        return positive, negative
    
    # ========== Context Augmentation ==========
    
    def augment_prompt(
        self,
        base_prompt: str,
        query: str,
        max_context_chars: int = 4000
    ) -> str:
        """
        Augment a prompt with retrieved context.
        
        Args:
            base_prompt: The original prompt
            query: What to search for
            max_context_chars: Maximum chars for context
        
        Returns:
            Augmented prompt with RAG context
        """
        context = self.retrieve(query, k=5)
        context_section = context.to_prompt_section(max_chars=max_context_chars)
        
        if context_section:
            return f"{context_section}\n\n---\n\n{base_prompt}"
        
        return base_prompt
    
    def clear_cache(self) -> None:
        """Clear the retrieval cache."""
        with self._lock:
            self._cache.clear()
    
    def get_stats(self) -> Dict[str, Any]:
        """Get retriever statistics."""
        return {
            'cache_size': len(self._cache),
            'embedding_dimension': self.embedder.dimension,
            'embedding_fallback_mode': self.embedder._fallback_mode,
            'tier_weights': self.tier_weights,
            'working_connected': self.working is not None,
            'personal_connected': self.personal is not None,
            'shared_connected': self.shared is not None
        }

