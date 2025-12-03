"""
Research Scratchpad - Per-proposal research file for context offloading.

When an agent researches for a proposal:
1. Distills papers/citations into key points
2. Builds structured research notes in a temp file
3. Offloads to file when working memory fills
4. Reloads relevant sections on demand
5. Preserves research progress across context overflows

Structure:
research_<proposal_name>/
├── scratchpad.md          # Main research notes (human-readable)
├── distilled.json         # Structured distilled content
├── citations.json         # Citation references
├── outline.json           # Current proposal outline
├── checkpoints/           # Progress checkpoints
│   ├── checkpoint_001.json
│   └── ...
└── context_overflow/      # Offloaded context chunks
    ├── chunk_001.json
    └── ...
"""

import os
import json
import time
import hashlib
import shutil
from typing import Dict, List, Any, Optional, Tuple
from dataclasses import dataclass, field, asdict
from pathlib import Path
import threading
import logging

logger = logging.getLogger(__name__)


@dataclass
class DistilledPaper:
    """Distilled content from a research paper."""
    citation_id: str
    title: str
    source: str  # "arxiv:2301.00001"
    
    # Distilled content (not full paper)
    key_findings: List[str]
    relevant_methods: List[str]
    key_quotes: List[Dict[str, str]]  # {"quote": "...", "page": "5", "relevance": "high"}
    limitations: List[str]
    
    # How it relates to the proposal
    relevance_to_proposal: str
    supports_claims: List[str]  # Which proposal claims this supports
    contradicts_claims: List[str]  # Which claims it might contradict
    
    # Metadata
    distilled_at: float = field(default_factory=time.time)
    quality_score: float = 0.0  # How useful was this paper
    
    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'DistilledPaper':
        return cls(**data)
    
    def to_markdown(self) -> str:
        """Convert to markdown for scratchpad."""
        lines = [
            f"## {self.title}",
            f"*Source: {self.source}*",
            f"*Relevance: {self.relevance_to_proposal}*",
            "",
            "### Key Findings"
        ]
        for finding in self.key_findings:
            lines.append(f"- {finding}")
        
        if self.relevant_methods:
            lines.append("\n### Relevant Methods")
            for method in self.relevant_methods:
                lines.append(f"- {method}")
        
        if self.key_quotes:
            lines.append("\n### Key Quotes")
            for quote in self.key_quotes:
                lines.append(f"> \"{quote.get('quote', '')}\" (p.{quote.get('page', '?')})")
        
        if self.limitations:
            lines.append("\n### Limitations/Caveats")
            for lim in self.limitations:
                lines.append(f"- {lim}")
        
        if self.supports_claims:
            lines.append("\n### Supports Claims")
            for claim in self.supports_claims:
                lines.append(f"- ✓ {claim}")
        
        if self.contradicts_claims:
            lines.append("\n### Contradicts/Challenges")
            for claim in self.contradicts_claims:
                lines.append(f"- ✗ {claim}")
        
        return "\n".join(lines)


@dataclass
class ResearchSection:
    """A section of research notes."""
    id: str
    title: str
    content: str
    section_type: str  # 'background', 'methods', 'evidence', 'gaps', 'synthesis'
    papers: List[str]  # Citation IDs used in this section
    created_at: float
    updated_at: float
    importance: float = 1.0  # For prioritizing what to keep in context
    
    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'ResearchSection':
        return cls(**data)


@dataclass
class ProposalOutline:
    """Current outline/structure of the proposal being built."""
    title: str
    thesis: str
    claims: List[Dict[str, Any]]  # {"claim": "...", "evidence": [...], "confidence": 0.8}
    methodology: str
    expected_benefits: List[str]
    risks: List[str]
    uncertainties: List[str]
    current_confidence: float
    
    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'ProposalOutline':
        return cls(**data)


@dataclass
class ContextChunk:
    """A chunk of context that was offloaded to disk."""
    id: str
    content: str
    chunk_type: str  # 'reasoning', 'search_results', 'paper_analysis', etc.
    keywords: List[str]  # For retrieval
    created_at: float
    importance: float
    
    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'ContextChunk':
        return cls(**data)


class ResearchScratchpad:
    """
    Per-proposal research scratchpad with context offloading.
    
    Features:
    - Distills papers into key points
    - Maintains structured research notes
    - Offloads context when memory fills
    - Reloads relevant sections on demand
    - Checkpoints progress for recovery
    - Generates readable markdown summary
    """
    
    def __init__(
        self,
        proposal_name: str,
        base_dir: str = "./data/research",
        max_context_chars: int = 8000,
        auto_checkpoint_interval: int = 300  # seconds
    ):
        self.proposal_name = self._sanitize_name(proposal_name)
        self.base_dir = Path(base_dir)
        self.research_dir = self.base_dir / f"research_{self.proposal_name}"
        self.research_dir.mkdir(parents=True, exist_ok=True)
        
        self.max_context_chars = max_context_chars
        self.auto_checkpoint_interval = auto_checkpoint_interval
        
        # Create subdirectories
        (self.research_dir / "checkpoints").mkdir(exist_ok=True)
        (self.research_dir / "context_overflow").mkdir(exist_ok=True)
        
        # File paths
        self.scratchpad_file = self.research_dir / "scratchpad.md"
        self.distilled_file = self.research_dir / "distilled.json"
        self.citations_file = self.research_dir / "citations.json"
        self.outline_file = self.research_dir / "outline.json"
        self.sections_file = self.research_dir / "sections.json"
        self.state_file = self.research_dir / "state.json"
        
        self._lock = threading.RLock()
        
        # In-memory state
        self._distilled_papers: Dict[str, DistilledPaper] = {}
        self._sections: Dict[str, ResearchSection] = {}
        self._outline: Optional[ProposalOutline] = None
        self._overflow_chunks: Dict[str, ContextChunk] = {}
        self._current_context_chars = 0
        self._last_checkpoint = time.time()
        self._created_at = time.time()
        
        # Load existing state if resuming
        self._load_state()
    
    def _sanitize_name(self, name: str) -> str:
        """Sanitize proposal name for filesystem."""
        # Replace spaces and special chars
        safe = "".join(c if c.isalnum() or c in "-_" else "_" for c in name)
        return safe[:50]  # Limit length
    
    def _load_state(self) -> None:
        """Load existing state from disk."""
        try:
            # Load distilled papers
            if self.distilled_file.exists():
                with open(self.distilled_file, 'r') as f:
                    data = json.load(f)
                    self._distilled_papers = {
                        k: DistilledPaper.from_dict(v) for k, v in data.items()
                    }
            
            # Load sections
            if self.sections_file.exists():
                with open(self.sections_file, 'r') as f:
                    data = json.load(f)
                    self._sections = {
                        k: ResearchSection.from_dict(v) for k, v in data.items()
                    }
            
            # Load outline
            if self.outline_file.exists():
                with open(self.outline_file, 'r') as f:
                    self._outline = ProposalOutline.from_dict(json.load(f))
            
            # Load overflow chunks
            overflow_dir = self.research_dir / "context_overflow"
            for chunk_file in overflow_dir.glob("chunk_*.json"):
                with open(chunk_file, 'r') as f:
                    chunk = ContextChunk.from_dict(json.load(f))
                    self._overflow_chunks[chunk.id] = chunk
            
            # Load state
            if self.state_file.exists():
                with open(self.state_file, 'r') as f:
                    state = json.load(f)
                    self._created_at = state.get('created_at', time.time())
                    self._last_checkpoint = state.get('last_checkpoint', time.time())
            
            logger.info(f"Loaded research scratchpad: {len(self._distilled_papers)} papers, {len(self._sections)} sections")
        except Exception as e:
            logger.warning(f"Failed to load scratchpad state: {e}")
    
    def _save_state(self) -> None:
        """Save current state to disk."""
        try:
            # Save distilled papers
            with open(self.distilled_file, 'w') as f:
                json.dump({k: v.to_dict() for k, v in self._distilled_papers.items()}, f, indent=2)
            
            # Save sections
            with open(self.sections_file, 'w') as f:
                json.dump({k: v.to_dict() for k, v in self._sections.items()}, f, indent=2)
            
            # Save outline
            if self._outline:
                with open(self.outline_file, 'w') as f:
                    json.dump(self._outline.to_dict(), f, indent=2)
            
            # Save state
            with open(self.state_file, 'w') as f:
                json.dump({
                    'created_at': self._created_at,
                    'last_checkpoint': self._last_checkpoint,
                    'proposal_name': self.proposal_name
                }, f, indent=2)
            
            # Update markdown scratchpad
            self._update_markdown_scratchpad()
            
        except Exception as e:
            logger.error(f"Failed to save scratchpad state: {e}")
    
    def _update_markdown_scratchpad(self) -> None:
        """Update the human-readable markdown scratchpad."""
        lines = [
            f"# Research: {self.proposal_name}",
            f"*Last updated: {time.strftime('%Y-%m-%d %H:%M:%S')}*",
            ""
        ]
        
        # Outline
        if self._outline:
            lines.extend([
                "## Proposal Outline",
                f"**Thesis:** {self._outline.thesis}",
                f"**Current Confidence:** {self._outline.current_confidence:.2f}",
                "",
                "### Claims"
            ])
            for claim in self._outline.claims:
                evidence_count = len(claim.get('evidence', []))
                lines.append(f"- {claim.get('claim', '')} ({evidence_count} evidence, conf: {claim.get('confidence', 0):.2f})")
            lines.append("")
        
        # Distilled papers
        if self._distilled_papers:
            lines.extend([
                "## Distilled Research",
                ""
            ])
            for paper in sorted(self._distilled_papers.values(), key=lambda p: -p.quality_score):
                lines.append(paper.to_markdown())
                lines.append("\n---\n")
        
        # Sections
        if self._sections:
            lines.extend([
                "## Research Sections",
                ""
            ])
            for section in sorted(self._sections.values(), key=lambda s: -s.importance):
                lines.extend([
                    f"### {section.title}",
                    section.content,
                    ""
                ])
        
        # Write to file
        with open(self.scratchpad_file, 'w') as f:
            f.write("\n".join(lines))
    
    # ========== Paper Distillation ==========
    
    def distill_paper(
        self,
        citation_id: str,
        title: str,
        source: str,
        key_findings: List[str],
        relevant_methods: List[str] = None,
        key_quotes: List[Dict[str, str]] = None,
        limitations: List[str] = None,
        relevance_to_proposal: str = "",
        supports_claims: List[str] = None,
        contradicts_claims: List[str] = None,
        quality_score: float = 0.5
    ) -> str:
        """
        Add a distilled paper to the scratchpad.
        
        This is the COMPRESSED version - full paper stays in PaperQA.
        """
        with self._lock:
            paper = DistilledPaper(
                citation_id=citation_id,
                title=title,
                source=source,
                key_findings=key_findings,
                relevant_methods=relevant_methods or [],
                key_quotes=key_quotes or [],
                limitations=limitations or [],
                relevance_to_proposal=relevance_to_proposal,
                supports_claims=supports_claims or [],
                contradicts_claims=contradicts_claims or [],
                quality_score=quality_score
            )
            
            self._distilled_papers[citation_id] = paper
            self._save_state()
            self._maybe_checkpoint()
            
            return citation_id
    
    def get_distilled_paper(self, citation_id: str) -> Optional[DistilledPaper]:
        """Get a distilled paper."""
        return self._distilled_papers.get(citation_id)
    
    def get_all_distilled(self) -> List[DistilledPaper]:
        """Get all distilled papers, sorted by quality."""
        return sorted(self._distilled_papers.values(), key=lambda p: -p.quality_score)
    
    # ========== Research Sections ==========
    
    def add_section(
        self,
        title: str,
        content: str,
        section_type: str = 'evidence',
        papers: List[str] = None,
        importance: float = 1.0
    ) -> str:
        """Add a research section."""
        with self._lock:
            section_id = hashlib.sha256(f"{title}{time.time()}".encode()).hexdigest()[:12]
            now = time.time()
            
            section = ResearchSection(
                id=section_id,
                title=title,
                content=content,
                section_type=section_type,
                papers=papers or [],
                created_at=now,
                updated_at=now,
                importance=importance
            )
            
            self._sections[section_id] = section
            self._save_state()
            
            return section_id
    
    def update_section(self, section_id: str, content: str) -> bool:
        """Update a section's content."""
        with self._lock:
            if section_id in self._sections:
                self._sections[section_id].content = content
                self._sections[section_id].updated_at = time.time()
                self._save_state()
                return True
            return False
    
    def get_sections_by_type(self, section_type: str) -> List[ResearchSection]:
        """Get sections of a specific type."""
        return [s for s in self._sections.values() if s.section_type == section_type]
    
    # ========== Proposal Outline ==========
    
    def set_outline(
        self,
        title: str,
        thesis: str,
        claims: List[Dict[str, Any]] = None,
        methodology: str = "",
        expected_benefits: List[str] = None,
        risks: List[str] = None,
        uncertainties: List[str] = None,
        confidence: float = 0.5
    ) -> None:
        """Set or update the proposal outline."""
        with self._lock:
            self._outline = ProposalOutline(
                title=title,
                thesis=thesis,
                claims=claims or [],
                methodology=methodology,
                expected_benefits=expected_benefits or [],
                risks=risks or [],
                uncertainties=uncertainties or [],
                current_confidence=confidence
            )
            self._save_state()
    
    def update_claim_evidence(self, claim_index: int, evidence: List[str]) -> None:
        """Update evidence for a specific claim."""
        with self._lock:
            if self._outline and 0 <= claim_index < len(self._outline.claims):
                self._outline.claims[claim_index]['evidence'] = evidence
                self._save_state()
    
    def get_outline(self) -> Optional[ProposalOutline]:
        """Get current outline."""
        return self._outline
    
    # ========== Context Offloading ==========
    
    def offload_context(
        self,
        content: str,
        chunk_type: str = 'reasoning',
        keywords: List[str] = None,
        importance: float = 0.5
    ) -> str:
        """
        Offload context to disk when working memory fills.
        
        Returns chunk ID for later retrieval.
        """
        with self._lock:
            chunk_id = f"chunk_{int(time.time())}_{hashlib.sha256(content.encode()).hexdigest()[:8]}"
            
            chunk = ContextChunk(
                id=chunk_id,
                content=content,
                chunk_type=chunk_type,
                keywords=keywords or self._extract_keywords(content),
                created_at=time.time(),
                importance=importance
            )
            
            # Save to disk
            chunk_file = self.research_dir / "context_overflow" / f"{chunk_id}.json"
            with open(chunk_file, 'w') as f:
                json.dump(chunk.to_dict(), f)
            
            self._overflow_chunks[chunk_id] = chunk
            
            logger.debug(f"Offloaded context chunk {chunk_id} ({len(content)} chars)")
            
            return chunk_id
    
    def retrieve_context(self, chunk_id: str) -> Optional[str]:
        """Retrieve an offloaded context chunk."""
        if chunk_id in self._overflow_chunks:
            return self._overflow_chunks[chunk_id].content
        
        # Try loading from disk
        chunk_file = self.research_dir / "context_overflow" / f"{chunk_id}.json"
        if chunk_file.exists():
            with open(chunk_file, 'r') as f:
                chunk = ContextChunk.from_dict(json.load(f))
                self._overflow_chunks[chunk_id] = chunk
                return chunk.content
        
        return None
    
    def search_offloaded(self, query: str, limit: int = 3) -> List[Tuple[str, str]]:
        """
        Search offloaded chunks by keywords.
        
        Returns list of (chunk_id, content) tuples.
        """
        query_words = set(query.lower().split())
        
        scored = []
        for chunk in self._overflow_chunks.values():
            keyword_overlap = len(query_words & set(chunk.keywords))
            if keyword_overlap > 0:
                score = keyword_overlap * chunk.importance
                scored.append((score, chunk.id, chunk.content))
        
        scored.sort(key=lambda x: -x[0])
        return [(cid, content) for _, cid, content in scored[:limit]]
    
    def _extract_keywords(self, content: str, n: int = 10) -> List[str]:
        """Extract keywords from content."""
        words = content.lower().split()
        stopwords = {'the', 'a', 'an', 'is', 'are', 'was', 'were', 'be', 'been',
                     'to', 'of', 'in', 'for', 'on', 'with', 'at', 'by', 'from',
                     'this', 'that', 'and', 'or', 'but', 'if', 'it', 'its', 'as'}
        
        word_counts = {}
        for word in words:
            if len(word) > 3 and word not in stopwords:
                word_counts[word] = word_counts.get(word, 0) + 1
        
        sorted_words = sorted(word_counts.items(), key=lambda x: -x[1])
        return [w for w, _ in sorted_words[:n]]
    
    # ========== Checkpointing ==========
    
    def checkpoint(self, note: str = "") -> str:
        """
        Create a checkpoint of current research state.
        
        Useful for recovery if something goes wrong.
        """
        with self._lock:
            checkpoint_id = f"checkpoint_{int(time.time())}"
            checkpoint_dir = self.research_dir / "checkpoints" / checkpoint_id
            checkpoint_dir.mkdir(parents=True, exist_ok=True)
            
            # Copy current state files
            for src_file in [self.distilled_file, self.sections_file, self.outline_file, self.state_file]:
                if src_file.exists():
                    shutil.copy(src_file, checkpoint_dir / src_file.name)
            
            # Save checkpoint metadata
            with open(checkpoint_dir / "metadata.json", 'w') as f:
                json.dump({
                    'checkpoint_id': checkpoint_id,
                    'created_at': time.time(),
                    'note': note,
                    'papers_count': len(self._distilled_papers),
                    'sections_count': len(self._sections),
                    'has_outline': self._outline is not None
                }, f, indent=2)
            
            self._last_checkpoint = time.time()
            
            logger.info(f"Created checkpoint {checkpoint_id}")
            return checkpoint_id
    
    def restore_checkpoint(self, checkpoint_id: str) -> bool:
        """Restore from a checkpoint."""
        with self._lock:
            checkpoint_dir = self.research_dir / "checkpoints" / checkpoint_id
            
            if not checkpoint_dir.exists():
                logger.error(f"Checkpoint {checkpoint_id} not found")
                return False
            
            try:
                # Restore files
                for filename in ["distilled.json", "sections.json", "outline.json", "state.json"]:
                    src = checkpoint_dir / filename
                    if src.exists():
                        shutil.copy(src, self.research_dir / filename)
                
                # Reload state
                self._load_state()
                
                logger.info(f"Restored checkpoint {checkpoint_id}")
                return True
            except Exception as e:
                logger.error(f"Failed to restore checkpoint: {e}")
                return False
    
    def list_checkpoints(self) -> List[Dict[str, Any]]:
        """List available checkpoints."""
        checkpoints = []
        checkpoint_base = self.research_dir / "checkpoints"
        
        for checkpoint_dir in checkpoint_base.iterdir():
            if checkpoint_dir.is_dir():
                metadata_file = checkpoint_dir / "metadata.json"
                if metadata_file.exists():
                    with open(metadata_file, 'r') as f:
                        checkpoints.append(json.load(f))
        
        return sorted(checkpoints, key=lambda c: -c.get('created_at', 0))
    
    def _maybe_checkpoint(self) -> None:
        """Create checkpoint if enough time has passed."""
        if time.time() - self._last_checkpoint > self.auto_checkpoint_interval:
            self.checkpoint(note="auto")
    
    # ========== Context Building ==========
    
    def get_context_summary(self, max_chars: int = 4000) -> str:
        """
        Get a summary of research for context injection.
        
        Prioritizes:
        1. Proposal outline
        2. High-quality distilled papers
        3. Important sections
        """
        parts = []
        char_count = 0
        
        # Outline first
        if self._outline:
            outline_str = f"PROPOSAL: {self._outline.title}\nThesis: {self._outline.thesis}\nConfidence: {self._outline.current_confidence:.2f}\n"
            if char_count + len(outline_str) < max_chars:
                parts.append(outline_str)
                char_count += len(outline_str)
        
        # Top papers
        papers = self.get_all_distilled()[:5]
        if papers:
            parts.append("\nKEY RESEARCH:")
            for paper in papers:
                paper_str = f"- {paper.title}: {', '.join(paper.key_findings[:2])}"
                if char_count + len(paper_str) < max_chars:
                    parts.append(paper_str)
                    char_count += len(paper_str)
        
        # Important sections
        important_sections = sorted(self._sections.values(), key=lambda s: -s.importance)[:3]
        if important_sections:
            parts.append("\nRESEARCH NOTES:")
            for section in important_sections:
                section_str = f"[{section.section_type}] {section.title}: {section.content[:200]}..."
                if char_count + len(section_str) < max_chars:
                    parts.append(section_str)
                    char_count += len(section_str)
        
        return "\n".join(parts)
    
    def get_evidence_for_claim(self, claim: str) -> List[Dict[str, Any]]:
        """Get all evidence supporting a specific claim."""
        evidence = []
        
        for paper in self._distilled_papers.values():
            if claim in paper.supports_claims:
                evidence.append({
                    'source': paper.source,
                    'title': paper.title,
                    'findings': paper.key_findings,
                    'quotes': paper.key_quotes,
                    'type': 'supporting'
                })
            elif claim in paper.contradicts_claims:
                evidence.append({
                    'source': paper.source,
                    'title': paper.title,
                    'findings': paper.key_findings,
                    'quotes': paper.key_quotes,
                    'type': 'contradicting'
                })
        
        return evidence
    
    # ========== Cleanup ==========
    
    def cleanup(self, keep_checkpoints: int = 3) -> None:
        """Clean up old data, keeping recent checkpoints."""
        with self._lock:
            # Clean old checkpoints
            checkpoints = self.list_checkpoints()
            for checkpoint in checkpoints[keep_checkpoints:]:
                checkpoint_dir = self.research_dir / "checkpoints" / checkpoint['checkpoint_id']
                if checkpoint_dir.exists():
                    shutil.rmtree(checkpoint_dir)
            
            # Clean old overflow chunks (keep last 50)
            chunks = sorted(self._overflow_chunks.values(), key=lambda c: -c.created_at)
            for chunk in chunks[50:]:
                chunk_file = self.research_dir / "context_overflow" / f"{chunk.id}.json"
                chunk_file.unlink(missing_ok=True)
                del self._overflow_chunks[chunk.id]
    
    def delete(self) -> None:
        """Delete the entire scratchpad."""
        if self.research_dir.exists():
            shutil.rmtree(self.research_dir)
            logger.info(f"Deleted research scratchpad: {self.proposal_name}")
    
    def get_stats(self) -> Dict[str, Any]:
        """Get scratchpad statistics."""
        return {
            'proposal_name': self.proposal_name,
            'created_at': self._created_at,
            'distilled_papers': len(self._distilled_papers),
            'sections': len(self._sections),
            'has_outline': self._outline is not None,
            'overflow_chunks': len(self._overflow_chunks),
            'checkpoints': len(self.list_checkpoints()),
            'last_checkpoint': self._last_checkpoint
        }

