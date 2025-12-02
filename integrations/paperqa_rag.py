"""
PaperQA RAG Integration
=======================

Provides evidence-grounded research capabilities for AI agents.

The agents don't access the network directly - they ask PaperQA to find
information, and PaperQA returns summarized, cited answers.

Architecture:
    Agent -> RAG Query -> PaperQA -> Research APIs -> Cited Answer -> Agent
    
The agent never sees URLs or makes HTTP requests. All research is mediated
through PaperQA which handles the network access.
"""

import os
import sys
import json
import asyncio
import hashlib
from pathlib import Path
from typing import Dict, List, Optional, Any, Callable
from dataclasses import dataclass, field
from datetime import datetime
from threading import Lock

# Project root
PROJECT_ROOT = Path(__file__).parent.parent

# Llama server configuration (local, self-contained)
LLAMA_SERVER_URL = os.environ.get("LLAMA_SERVER_URL", "http://localhost:8080/v1")
LLAMA_MODEL_NAME = os.environ.get("LLAMA_MODEL_NAME", "phi-3.5-mini")


@dataclass
class RAGResult:
    """Result from a RAG query."""
    query: str
    answer: str
    sources: List[Dict[str, str]]  # [{name, text, score}]
    confidence: float
    timestamp: str
    cached: bool = False
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            'query': self.query,
            'answer': self.answer,
            'sources': self.sources,
            'confidence': self.confidence,
            'timestamp': self.timestamp,
            'cached': self.cached
        }


@dataclass
class RAGConfig:
    """Configuration for RAG system."""
    # LLM settings
    llm_model: str = LLAMA_MODEL_NAME
    llm_api_base: str = LLAMA_SERVER_URL
    temperature: float = 0.1
    max_tokens: int = 1024
    
    # Retrieval settings
    evidence_k: int = 10
    max_sources: int = 5
    
    # Embedding settings  
    embedding: str = "sparse"  # Use sparse for local, no external API
    
    # Document directories to index
    doc_directories: List[str] = field(default_factory=lambda: [
        str(PROJECT_ROOT / "docs"),
        str(PROJECT_ROOT / "assessments"),
        str(PROJECT_ROOT / "README.md"),
    ])
    
    # Cache settings
    cache_enabled: bool = True
    cache_ttl_seconds: int = 3600


class LocalRAG:
    """
    Local RAG system that doesn't require external API keys.
    Uses local llama.cpp server for inference and sparse embeddings.
    """
    
    def __init__(self, config: Optional[RAGConfig] = None):
        self.config = config or RAGConfig()
        self._cache: Dict[str, RAGResult] = {}
        self._cache_lock = Lock()
        self._docs = None
        self._settings = None
        self._initialized = False
        
    def _get_cache_key(self, query: str) -> str:
        """Generate cache key for query."""
        return hashlib.sha256(query.lower().strip().encode()).hexdigest()[:16]
    
    def _check_cache(self, query: str) -> Optional[RAGResult]:
        """Check if query result is cached."""
        if not self.config.cache_enabled:
            return None
            
        key = self._get_cache_key(query)
        with self._cache_lock:
            if key in self._cache:
                result = self._cache[key]
                # Check TTL
                cached_time = datetime.fromisoformat(result.timestamp)
                if (datetime.now() - cached_time).seconds < self.config.cache_ttl_seconds:
                    result.cached = True
                    return result
                else:
                    del self._cache[key]
        return None
    
    def _store_cache(self, query: str, result: RAGResult) -> None:
        """Store query result in cache."""
        if not self.config.cache_enabled:
            return
            
        key = self._get_cache_key(query)
        with self._cache_lock:
            self._cache[key] = result
    
    async def initialize(self) -> bool:
        """Initialize the RAG system with local documents."""
        if self._initialized:
            return True
            
        try:
            from paperqa import Docs, Settings
            
            # Configure for local llama.cpp server
            local_llm_config = {
                "model_list": [{
                    "model_name": self.config.llm_model,
                    "litellm_params": {
                        "model": f"openai/{self.config.llm_model}",
                        "api_base": self.config.llm_api_base,
                        "api_key": "sk-no-key-required",
                        "temperature": self.config.temperature,
                        "max_tokens": self.config.max_tokens,
                    },
                }]
            }
            
            self._settings = Settings(
                llm=self.config.llm_model,
                llm_config=local_llm_config,
                summary_llm=self.config.llm_model,
                summary_llm_config=local_llm_config,
                embedding=self.config.embedding,
            )
            self._settings.answer.evidence_k = self.config.evidence_k
            self._settings.answer.answer_max_sources = self.config.max_sources
            
            self._docs = Docs()
            
            # Index local documents
            await self._index_documents()
            
            self._initialized = True
            return True
            
        except ImportError:
            print("PaperQA not installed. Run: pip install paper-qa")
            return False
        except Exception as e:
            print(f"RAG initialization error: {e}")
            return False
    
    async def _index_documents(self) -> None:
        """Index local documentation."""
        if not self._docs:
            return
            
        indexed = 0
        for doc_path in self.config.doc_directories:
            path = Path(doc_path)
            if path.is_file():
                try:
                    await self._docs.aadd(str(path), settings=self._settings)
                    indexed += 1
                except Exception:
                    pass
            elif path.is_dir():
                for ext in ['.md', '.txt', '.py']:
                    for file in path.glob(f'**/*{ext}'):
                        try:
                            await self._docs.aadd(str(file), settings=self._settings)
                            indexed += 1
                        except Exception:
                            pass
        
        print(f"RAG: Indexed {indexed} documents")
    
    async def query(self, question: str) -> RAGResult:
        """
        Query the RAG system.
        
        This is the main interface for agents. The agent asks a question
        in natural language and receives a cited answer.
        
        Args:
            question: Natural language question
            
        Returns:
            RAGResult with answer and sources
        """
        # Check cache first
        cached = self._check_cache(question)
        if cached:
            return cached
        
        # Ensure initialized
        if not self._initialized:
            await self.initialize()
        
        if not self._docs or not self._settings:
            return RAGResult(
                query=question,
                answer="RAG system not initialized",
                sources=[],
                confidence=0.0,
                timestamp=datetime.now().isoformat()
            )
        
        try:
            # Query PaperQA
            session = await self._docs.aquery(question, settings=self._settings)
            
            # Extract sources
            sources = []
            if hasattr(session, 'contexts') and session.contexts:
                for ctx in session.contexts[:self.config.max_sources]:
                    sources.append({
                        'name': getattr(ctx.text.doc, 'docname', 'unknown'),
                        'text': ctx.text.text[:500] if hasattr(ctx.text, 'text') else '',
                        'score': getattr(ctx, 'score', 0.0)
                    })
            
            result = RAGResult(
                query=question,
                answer=session.answer if hasattr(session, 'answer') else str(session),
                sources=sources,
                confidence=0.8 if sources else 0.3,  # Higher confidence with sources
                timestamp=datetime.now().isoformat()
            )
            
            # Cache result
            self._store_cache(question, result)
            
            return result
            
        except Exception as e:
            return RAGResult(
                query=question,
                answer=f"Query error: {str(e)}",
                sources=[],
                confidence=0.0,
                timestamp=datetime.now().isoformat()
            )
    
    def query_sync(self, question: str) -> RAGResult:
        """Synchronous wrapper for query."""
        return asyncio.run(self.query(question))


class PaperQAIntegration:
    """
    High-level integration of PaperQA into the AI Safety System.
    
    Provides:
    - Evidence search for proposals
    - Claim verification
    - Research synthesis
    - Prior art search
    """
    
    def __init__(self, config: Optional[RAGConfig] = None):
        self.rag = LocalRAG(config)
        self._initialized = False
    
    async def initialize(self) -> bool:
        """Initialize the integration."""
        self._initialized = await self.rag.initialize()
        return self._initialized
    
    async def search_evidence(self, claim: str, context: Optional[str] = None) -> Dict[str, Any]:
        """
        Search for evidence supporting or refuting a claim.
        
        Args:
            claim: The claim to verify
            context: Optional context about the claim
            
        Returns:
            Dict with evidence, sources, and assessment
        """
        query = f"Is there evidence for or against this claim: {claim}"
        if context:
            query += f"\n\nContext: {context}"
        
        result = await self.rag.query(query)
        
        return {
            'claim': claim,
            'evidence': result.answer,
            'sources': result.sources,
            'confidence': result.confidence,
            'timestamp': result.timestamp,
            'supports_claim': self._assess_support(result.answer)
        }
    
    def _assess_support(self, answer: str) -> Optional[bool]:
        """Assess if the answer supports or refutes the claim."""
        lower = answer.lower()
        if any(word in lower for word in ['supports', 'confirms', 'evidence for', 'consistent with']):
            return True
        elif any(word in lower for word in ['refutes', 'contradicts', 'no evidence', 'inconsistent']):
            return False
        return None  # Unclear
    
    async def verify_proposal_claims(self, proposal: Dict[str, Any]) -> Dict[str, Any]:
        """
        Verify claims made in a proposal.
        
        Args:
            proposal: Proposal dict with title, motivation, expected_benefits, etc.
            
        Returns:
            Dict with verification results for each claim
        """
        claims_to_verify = []
        
        # Extract claims from proposal
        if 'expected_benefits' in proposal:
            claims_to_verify.append(('expected_benefits', proposal['expected_benefits']))
        if 'motivation' in proposal:
            claims_to_verify.append(('motivation', proposal['motivation']))
        if 'testable_predictions' in proposal:
            for pred in proposal.get('testable_predictions', []):
                claims_to_verify.append(('prediction', pred))
        
        results = {}
        for claim_type, claim_text in claims_to_verify:
            evidence = await self.search_evidence(claim_text)
            results[claim_type] = evidence
        
        # Overall assessment
        supported_count = sum(1 for r in results.values() if r.get('supports_claim') is True)
        refuted_count = sum(1 for r in results.values() if r.get('supports_claim') is False)
        
        return {
            'proposal_title': proposal.get('title', 'Unknown'),
            'claims_verified': len(results),
            'claims_supported': supported_count,
            'claims_refuted': refuted_count,
            'claim_results': results,
            'overall_confidence': sum(r['confidence'] for r in results.values()) / len(results) if results else 0
        }
    
    async def research_topic(self, topic: str, depth: str = 'standard') -> Dict[str, Any]:
        """
        Research a topic and synthesize findings.
        
        Args:
            topic: Topic to research
            depth: 'quick', 'standard', or 'deep'
            
        Returns:
            Research synthesis with citations
        """
        queries = [f"What is {topic}?"]
        
        if depth in ['standard', 'deep']:
            queries.extend([
                f"What are the best practices for {topic}?",
                f"What are common problems with {topic}?",
            ])
        
        if depth == 'deep':
            queries.extend([
                f"What is the current state of the art for {topic}?",
                f"What are open research questions about {topic}?",
            ])
        
        results = []
        all_sources = []
        
        for query in queries:
            result = await self.rag.query(query)
            results.append({
                'query': query,
                'answer': result.answer,
                'confidence': result.confidence
            })
            all_sources.extend(result.sources)
        
        # Deduplicate sources
        seen = set()
        unique_sources = []
        for s in all_sources:
            key = s.get('name', '')
            if key not in seen:
                seen.add(key)
                unique_sources.append(s)
        
        return {
            'topic': topic,
            'depth': depth,
            'findings': results,
            'sources': unique_sources[:10],  # Top 10 sources
            'timestamp': datetime.now().isoformat()
        }
    
    async def find_prior_art(self, concept: str) -> Dict[str, Any]:
        """
        Search for prior art related to a concept.
        
        Args:
            concept: Concept to search for
            
        Returns:
            Prior art findings
        """
        queries = [
            f"Are there existing implementations of {concept}?",
            f"What is the history of {concept}?",
            f"Who has worked on {concept} before?",
        ]
        
        results = []
        for query in queries:
            result = await self.rag.query(query)
            results.append({
                'query': query,
                'answer': result.answer,
                'sources': result.sources
            })
        
        return {
            'concept': concept,
            'prior_art_findings': results,
            'timestamp': datetime.now().isoformat()
        }
    
    async def evaluate_proposal_usefulness(
        self,
        proposal: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        PaperQA AI evaluates if a proposal is useful or should be filtered out.
        
        Checks:
        - Is this redundant with existing knowledge?
        - Is this proposal well-evidenced?
        - Does this add value or is it useless?
        - Has this been tried before?
        
        Returns:
            Dict with:
            - useful: bool - Whether proposal is useful
            - confidence: float - Confidence in evaluation
            - reasoning: str - Why it's useful/not useful
            - redundancy_score: float - How redundant (0-1, higher = more redundant)
            - evidence_quality: float - Quality of supporting evidence (0-1)
        """
        title = proposal.get('title', '')
        description = proposal.get('changes', {}).get('description', '')
        motivation = proposal.get('motivation', '')
        
        # Build evaluation query
        eval_query = f"""
Evaluate this improvement proposal:
Title: {title}
Description: {description}
Motivation: {motivation}

Questions to answer:
1. Is this proposal redundant with existing solutions or knowledge?
2. Is this proposal well-evidenced and supported by research?
3. Does this proposal add meaningful value?
4. Has something similar been tried before?

Provide a clear evaluation with reasoning.
"""
        
        try:
            result = await self.rag.query(eval_query)
            answer_text = result.answer.lower()
            
            # Extract evaluation signals
            is_redundant = any(word in answer_text for word in [
                'redundant', 'already exists', 'been done', 'similar', 'duplicate'
            ])
            
            is_well_evidenced = any(word in answer_text for word in [
                'supported', 'evidence', 'research', 'proven', 'validated'
            ])
            
            adds_value = any(word in answer_text for word in [
                'useful', 'valuable', 'improves', 'beneficial', 'adds value'
            ]) and not any(word in answer_text for word in [
                'not useful', 'no value', 'useless', 'unnecessary'
            ])
            
            # Compute scores
            redundancy_score = 0.8 if is_redundant else 0.2
            evidence_quality = 0.8 if is_well_evidenced else 0.4
            
            # Overall usefulness
            useful = adds_value and not is_redundant and is_well_evidenced
            
            # Confidence based on answer quality
            confidence = result.confidence
            
            return {
                'useful': useful,
                'confidence': confidence,
                'reasoning': result.answer,
                'redundancy_score': redundancy_score,
                'evidence_quality': evidence_quality,
                'sources': result.sources
            }
            
        except Exception as e:
            logger.error(f"Error evaluating proposal: {e}")
            # Default to allowing proposal if evaluation fails (fail-open)
            return {
                'useful': True,
                'confidence': 0.3,
                'reasoning': f"Evaluation failed: {str(e)}",
                'redundancy_score': 0.5,
                'evidence_quality': 0.5,
                'sources': []
            }
    
    async def check_proposal_redundancy(
        self,
        proposal: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Check if a proposal is redundant with existing knowledge.
        
        Returns:
            Dict with:
            - is_redundant: bool
            - similarity_score: float (0-1, higher = more similar)
            - similar_proposals: List of similar proposals found
        """
        title = proposal.get('title', '')
        description = proposal.get('changes', {}).get('description', '')
        
        query = f"""
Find similar or redundant proposals to:
Title: {title}
Description: {description}

Has this been proposed or implemented before?
"""
        
        try:
            result = await self.rag.query(query)
            answer_text = result.answer.lower()
            is_redundant = any(word in answer_text for word in [
                'similar', 'already', 'exists', 'redundant', 'duplicate', 'been done'
            ])
            
            # Estimate similarity score
            similarity_score = 0.7 if is_redundant else 0.2
            
            return {
                'is_redundant': is_redundant,
                'similarity_score': similarity_score,
                'similar_proposals': [s.get('name', '') for s in result.sources],
                'reasoning': result.answer
            }
            
        except Exception as e:
            logger.error(f"Error checking redundancy: {e}")
            return {
                'is_redundant': False,
                'similarity_score': 0.0,
                'similar_proposals': [],
                'reasoning': f"Error: {str(e)}"
            }


# Convenience function for agents to use
_global_rag: Optional[PaperQAIntegration] = None

async def get_rag() -> PaperQAIntegration:
    """Get or create the global RAG instance."""
    global _global_rag
    if _global_rag is None:
        _global_rag = PaperQAIntegration()
        await _global_rag.initialize()
    return _global_rag


async def ask_research(question: str) -> str:
    """
    Simple interface for agents to ask research questions.
    
    This is what agents call - they never see URLs or network details.
    
    Args:
        question: Natural language question
        
    Returns:
        Cited answer as string
    """
    rag = await get_rag()
    result = await rag.rag.query(question)
    
    # Format answer with citations
    answer = result.answer
    if result.sources:
        answer += "\n\nSources:\n"
        for i, source in enumerate(result.sources, 1):
            answer += f"  [{i}] {source.get('name', 'Unknown')}\n"
    
    return answer


def ask_research_sync(question: str) -> str:
    """Synchronous wrapper for ask_research."""
    return asyncio.run(ask_research(question))

