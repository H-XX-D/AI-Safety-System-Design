"""
Proposal Workspace - Each proposal is a self-contained folder with all research files.

Working memory continuously writes to these files to keep context fresh.
When a proposal is complete, the workspace condenses into persistent memory.

Structure:
proposals/
└── <proposal_id>/
    ├── manifest.json           # Proposal metadata and status
    ├── outline.json            # Current proposal structure
    ├── working_context.json    # Live working memory state
    ├── research/
    │   ├── scratchpad.md       # Human-readable research notes
    │   ├── distilled_papers.json
    │   ├── citations.json
    │   └── evidence_map.json   # Claims -> evidence mapping
    ├── reasoning/
    │   ├── current.json        # Current reasoning chain
    │   ├── history/            # Past reasoning (offloaded)
    │   └── decisions.json      # Key decisions made
    ├── feedback/
    │   ├── peer_reviews.json
    │   ├── orka_challenges.json
    │   └── revisions.json
    ├── checkpoints/
    │   └── checkpoint_*.json
    └── artifacts/
        ├── code/               # Any code written
        └── outputs/            # Generated outputs
"""

import os
import json
import time
import shutil
import hashlib
from typing import Dict, List, Any, Optional, Tuple
from dataclasses import dataclass, field, asdict
from pathlib import Path
import threading
import logging

logger = logging.getLogger(__name__)


@dataclass
class ProposalManifest:
    """Metadata for a proposal workspace."""
    id: str
    title: str
    description: str
    domain: str
    status: str  # 'researching', 'drafting', 'reviewing', 'revising', 'submitted', 'approved', 'rejected', 'archived'
    
    # Timestamps
    created_at: float
    updated_at: float
    submitted_at: Optional[float] = None
    completed_at: Optional[float] = None
    
    # Progress
    confidence: float = 0.5
    research_completeness: float = 0.0  # 0-1, how much research is done
    evidence_strength: float = 0.0      # 0-1, how well claims are supported
    
    # Tracking
    agent_id: str = ""
    session_ids: List[str] = field(default_factory=list)
    revision_count: int = 0
    
    # Outcome (when complete)
    outcome: Optional[str] = None  # 'approved', 'rejected'
    reward: float = 0.0
    
    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'ProposalManifest':
        return cls(**data)


@dataclass
class WorkingContext:
    """Live working memory state for a proposal."""
    # Current focus
    current_task: str = ""
    current_claim_index: int = -1
    
    # Recent context (kept in sync with files)
    recent_findings: List[Dict[str, Any]] = field(default_factory=list)
    recent_reasoning: List[str] = field(default_factory=list)
    pending_questions: List[str] = field(default_factory=list)
    
    # Session state
    session_id: str = ""
    last_activity: float = field(default_factory=time.time)
    context_char_count: int = 0
    
    # Flags
    needs_more_research: bool = True
    has_unsaved_changes: bool = False
    
    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'WorkingContext':
        return cls(**data)


@dataclass
class ProposalOutline:
    """Current structure of the proposal."""
    title: str
    thesis: str
    
    # Claims with evidence tracking
    claims: List[Dict[str, Any]] = field(default_factory=list)
    # Each claim: {
    #   "claim": "...",
    #   "confidence": 0.8,
    #   "evidence": ["citation_id_1", "citation_id_2"],
    #   "status": "supported" | "needs_evidence" | "contradicted"
    # }
    
    methodology: str = ""
    expected_benefits: List[str] = field(default_factory=list)
    identified_risks: List[str] = field(default_factory=list)
    admitted_uncertainties: List[str] = field(default_factory=list)
    rollback_plan: str = ""
    
    # Code if any
    code_description: str = ""
    code_files: List[str] = field(default_factory=list)
    
    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'ProposalOutline':
        return cls(**data)


class ProposalWorkspace:
    """
    Self-contained workspace for a single proposal.
    
    Working memory continuously writes here to keep context fresh.
    All research, reasoning, and feedback lives in this folder.
    
    Features:
    - Continuous file sync (working memory writes here)
    - Structured research storage
    - Evidence mapping (claims -> citations)
    - Reasoning history with offloading
    - Checkpoint/restore
    - Condense to persistent memory when complete
    """
    
    def __init__(
        self,
        proposal_id: str,
        base_dir: str = "./data/proposals",
        agent_id: str = "",
        auto_save_interval: float = 30.0,  # Save every 30 seconds
        max_reasoning_history: int = 50    # Keep last N reasoning items in memory
    ):
        self.proposal_id = proposal_id
        self.base_dir = Path(base_dir)
        self.workspace_dir = self.base_dir / proposal_id
        self.agent_id = agent_id
        self.auto_save_interval = auto_save_interval
        self.max_reasoning_history = max_reasoning_history
        
        self._lock = threading.RLock()
        self._last_save = time.time()
        
        # Create directory structure
        self._init_workspace()
        
        # Load or create state
        self.manifest: ProposalManifest = self._load_or_create_manifest()
        self.outline: ProposalOutline = self._load_or_create_outline()
        self.working_context: WorkingContext = self._load_or_create_context()
        
        # In-memory caches (synced to files)
        self._distilled_papers: Dict[str, Dict] = self._load_json("research/distilled_papers.json", {})
        self._citations: Dict[str, Dict] = self._load_json("research/citations.json", {})
        self._evidence_map: Dict[str, List[str]] = self._load_json("research/evidence_map.json", {})
        self._reasoning_history: List[Dict] = self._load_json("reasoning/history.json", [])
        self._decisions: List[Dict] = self._load_json("reasoning/decisions.json", [])
        self._peer_reviews: List[Dict] = self._load_json("feedback/peer_reviews.json", [])
        self._orka_challenges: List[Dict] = self._load_json("feedback/orka_challenges.json", [])
        self._revisions: List[Dict] = self._load_json("feedback/revisions.json", [])
    
    def _init_workspace(self) -> None:
        """Create workspace directory structure."""
        dirs = [
            self.workspace_dir,
            self.workspace_dir / "research",
            self.workspace_dir / "reasoning",
            self.workspace_dir / "reasoning" / "history",
            self.workspace_dir / "feedback",
            self.workspace_dir / "checkpoints",
            self.workspace_dir / "artifacts",
            self.workspace_dir / "artifacts" / "code",
            self.workspace_dir / "artifacts" / "outputs"
        ]
        for d in dirs:
            d.mkdir(parents=True, exist_ok=True)
    
    def _load_json(self, rel_path: str, default: Any) -> Any:
        """Load JSON file or return default."""
        path = self.workspace_dir / rel_path
        if path.exists():
            try:
                with open(path, 'r') as f:
                    return json.load(f)
            except Exception as e:
                logger.warning(f"Failed to load {rel_path}: {e}")
        return default
    
    def _save_json(self, rel_path: str, data: Any) -> None:
        """Save data to JSON file."""
        path = self.workspace_dir / rel_path
        path.parent.mkdir(parents=True, exist_ok=True)
        with open(path, 'w') as f:
            json.dump(data, f, indent=2, default=str)
    
    def _load_or_create_manifest(self) -> ProposalManifest:
        """Load or create proposal manifest."""
        data = self._load_json("manifest.json", None)
        if data:
            return ProposalManifest.from_dict(data)
        
        return ProposalManifest(
            id=self.proposal_id,
            title="",
            description="",
            domain="general",
            status="researching",
            created_at=time.time(),
            updated_at=time.time(),
            agent_id=self.agent_id
        )
    
    def _load_or_create_outline(self) -> ProposalOutline:
        """Load or create proposal outline."""
        data = self._load_json("outline.json", None)
        if data:
            return ProposalOutline.from_dict(data)
        return ProposalOutline(title="", thesis="")
    
    def _load_or_create_context(self) -> WorkingContext:
        """Load or create working context."""
        data = self._load_json("working_context.json", None)
        if data:
            return WorkingContext.from_dict(data)
        return WorkingContext()
    
    # ========== Continuous Sync (Working Memory Writes Here) ==========
    
    def sync(self) -> None:
        """
        Sync all in-memory state to files.
        Called automatically and can be called manually.
        """
        with self._lock:
            self.manifest.updated_at = time.time()
            self.working_context.last_activity = time.time()
            self.working_context.has_unsaved_changes = False
            
            # Save all state
            self._save_json("manifest.json", self.manifest.to_dict())
            self._save_json("outline.json", self.outline.to_dict())
            self._save_json("working_context.json", self.working_context.to_dict())
            self._save_json("research/distilled_papers.json", self._distilled_papers)
            self._save_json("research/citations.json", self._citations)
            self._save_json("research/evidence_map.json", self._evidence_map)
            self._save_json("reasoning/decisions.json", self._decisions)
            self._save_json("feedback/peer_reviews.json", self._peer_reviews)
            self._save_json("feedback/orka_challenges.json", self._orka_challenges)
            self._save_json("feedback/revisions.json", self._revisions)
            
            # Update scratchpad
            self._update_scratchpad()
            
            self._last_save = time.time()
    
    def _maybe_auto_save(self) -> None:
        """Auto-save if enough time has passed."""
        if time.time() - self._last_save > self.auto_save_interval:
            self.sync()
    
    def _update_scratchpad(self) -> None:
        """Update human-readable scratchpad.md."""
        lines = [
            f"# Research: {self.manifest.title or self.proposal_id}",
            f"*Status: {self.manifest.status}*",
            f"*Confidence: {self.manifest.confidence:.2f}*",
            f"*Last updated: {time.strftime('%Y-%m-%d %H:%M:%S')}*",
            ""
        ]
        
        # Thesis
        if self.outline.thesis:
            lines.extend([
                "## Thesis",
                self.outline.thesis,
                ""
            ])
        
        # Claims with evidence
        if self.outline.claims:
            lines.extend(["## Claims", ""])
            for i, claim in enumerate(self.outline.claims):
                status_icon = {"supported": "✓", "needs_evidence": "?", "contradicted": "✗"}.get(claim.get('status', ''), '•')
                evidence_count = len(claim.get('evidence', []))
                lines.append(f"{i+1}. {status_icon} **{claim.get('claim', '')}**")
                lines.append(f"   - Confidence: {claim.get('confidence', 0):.2f}")
                lines.append(f"   - Evidence: {evidence_count} citations")
                lines.append("")
        
        # Distilled papers
        if self._distilled_papers:
            lines.extend(["## Research Papers", ""])
            for paper in sorted(self._distilled_papers.values(), key=lambda p: -p.get('quality_score', 0)):
                lines.append(f"### {paper.get('title', 'Untitled')}")
                lines.append(f"*{paper.get('source', '')}*")
                lines.append(f"*Relevance: {paper.get('relevance_to_proposal', '')}*")
                lines.append("")
                if paper.get('key_findings'):
                    lines.append("**Key Findings:**")
                    for finding in paper['key_findings'][:5]:
                        lines.append(f"- {finding}")
                lines.append("")
        
        # Current focus
        if self.working_context.current_task:
            lines.extend([
                "## Current Focus",
                self.working_context.current_task,
                ""
            ])
        
        # Pending questions
        if self.working_context.pending_questions:
            lines.extend(["## Pending Questions", ""])
            for q in self.working_context.pending_questions:
                lines.append(f"- [ ] {q}")
            lines.append("")
        
        # Write to file
        scratchpad_path = self.workspace_dir / "research" / "scratchpad.md"
        with open(scratchpad_path, 'w') as f:
            f.write("\n".join(lines))
    
    # ========== Proposal Setup ==========
    
    def set_title(self, title: str, description: str = "") -> None:
        """Set proposal title and description."""
        with self._lock:
            self.manifest.title = title
            self.manifest.description = description
            self.outline.title = title
            self.working_context.has_unsaved_changes = True
            self._maybe_auto_save()
    
    def set_thesis(self, thesis: str) -> None:
        """Set the main thesis."""
        with self._lock:
            self.outline.thesis = thesis
            self.working_context.has_unsaved_changes = True
            self._maybe_auto_save()
    
    def set_domain(self, domain: str) -> None:
        """Set the domain."""
        with self._lock:
            self.manifest.domain = domain
            self.working_context.has_unsaved_changes = True
    
    def set_status(self, status: str) -> None:
        """Update proposal status."""
        with self._lock:
            self.manifest.status = status
            if status == 'submitted':
                self.manifest.submitted_at = time.time()
            elif status in ('approved', 'rejected', 'archived'):
                self.manifest.completed_at = time.time()
                self.manifest.outcome = status
            self._maybe_auto_save()
    
    # ========== Claims & Evidence ==========
    
    def add_claim(
        self,
        claim: str,
        confidence: float = 0.5,
        evidence: List[str] = None
    ) -> int:
        """Add a claim to the proposal. Returns claim index."""
        with self._lock:
            claim_data = {
                'claim': claim,
                'confidence': confidence,
                'evidence': evidence or [],
                'status': 'needs_evidence' if not evidence else 'supported'
            }
            self.outline.claims.append(claim_data)
            self.working_context.has_unsaved_changes = True
            self._maybe_auto_save()
            return len(self.outline.claims) - 1
    
    def update_claim(
        self,
        index: int,
        claim: str = None,
        confidence: float = None,
        evidence: List[str] = None,
        status: str = None
    ) -> None:
        """Update an existing claim."""
        with self._lock:
            if 0 <= index < len(self.outline.claims):
                if claim is not None:
                    self.outline.claims[index]['claim'] = claim
                if confidence is not None:
                    self.outline.claims[index]['confidence'] = confidence
                if evidence is not None:
                    self.outline.claims[index]['evidence'] = evidence
                if status is not None:
                    self.outline.claims[index]['status'] = status
                self.working_context.has_unsaved_changes = True
                self._maybe_auto_save()
    
    def add_evidence_to_claim(self, claim_index: int, citation_id: str) -> None:
        """Add evidence (citation) to a claim."""
        with self._lock:
            if 0 <= claim_index < len(self.outline.claims):
                if citation_id not in self.outline.claims[claim_index]['evidence']:
                    self.outline.claims[claim_index]['evidence'].append(citation_id)
                    
                    # Update evidence map
                    claim_text = self.outline.claims[claim_index]['claim']
                    if claim_text not in self._evidence_map:
                        self._evidence_map[claim_text] = []
                    if citation_id not in self._evidence_map[claim_text]:
                        self._evidence_map[claim_text].append(citation_id)
                    
                    # Update status if now has evidence
                    if self.outline.claims[claim_index]['status'] == 'needs_evidence':
                        self.outline.claims[claim_index]['status'] = 'supported'
                    
                    self.working_context.has_unsaved_changes = True
                    self._maybe_auto_save()
    
    def get_unsupported_claims(self) -> List[Tuple[int, Dict]]:
        """Get claims that need more evidence."""
        return [
            (i, claim) for i, claim in enumerate(self.outline.claims)
            if claim.get('status') == 'needs_evidence' or len(claim.get('evidence', [])) == 0
        ]
    
    # ========== Research (Distilled Papers & Citations) ==========
    
    def add_distilled_paper(
        self,
        citation_id: str,
        title: str,
        source: str,
        key_findings: List[str],
        relevance_to_proposal: str = "",
        relevant_methods: List[str] = None,
        key_quotes: List[Dict[str, str]] = None,
        limitations: List[str] = None,
        supports_claims: List[str] = None,
        contradicts_claims: List[str] = None,
        quality_score: float = 0.5
    ) -> None:
        """Add a distilled paper to research."""
        with self._lock:
            self._distilled_papers[citation_id] = {
                'citation_id': citation_id,
                'title': title,
                'source': source,
                'key_findings': key_findings,
                'relevance_to_proposal': relevance_to_proposal,
                'relevant_methods': relevant_methods or [],
                'key_quotes': key_quotes or [],
                'limitations': limitations or [],
                'supports_claims': supports_claims or [],
                'contradicts_claims': contradicts_claims or [],
                'quality_score': quality_score,
                'distilled_at': time.time()
            }
            
            # Add to recent findings in working context
            self.working_context.recent_findings.append({
                'type': 'paper',
                'citation_id': citation_id,
                'title': title,
                'key_finding': key_findings[0] if key_findings else "",
                'timestamp': time.time()
            })
            
            # Keep recent findings bounded
            if len(self.working_context.recent_findings) > 20:
                self.working_context.recent_findings = self.working_context.recent_findings[-20:]
            
            # Update research completeness estimate
            self._update_research_completeness()
            
            self.working_context.has_unsaved_changes = True
            self._maybe_auto_save()
    
    def add_citation(
        self,
        citation_id: str,
        source_type: str,
        source_id: str,
        title: str,
        authors: List[str],
        relevant_pages: List[int] = None,
        relevant_sections: List[str] = None,
        key_quotes: List[Dict[str, str]] = None
    ) -> None:
        """Add a citation reference."""
        with self._lock:
            self._citations[citation_id] = {
                'citation_id': citation_id,
                'source_type': source_type,
                'source_id': source_id,
                'title': title,
                'authors': authors,
                'relevant_pages': relevant_pages or [],
                'relevant_sections': relevant_sections or [],
                'key_quotes': key_quotes or [],
                'added_at': time.time()
            }
            self.working_context.has_unsaved_changes = True
    
    def get_evidence_for_claim(self, claim_index: int) -> List[Dict]:
        """Get all evidence (papers + citations) for a claim."""
        if claim_index < 0 or claim_index >= len(self.outline.claims):
            return []
        
        evidence = []
        for citation_id in self.outline.claims[claim_index].get('evidence', []):
            if citation_id in self._distilled_papers:
                evidence.append({
                    'type': 'distilled_paper',
                    **self._distilled_papers[citation_id]
                })
            elif citation_id in self._citations:
                evidence.append({
                    'type': 'citation',
                    **self._citations[citation_id]
                })
        return evidence
    
    def _update_research_completeness(self) -> None:
        """Estimate research completeness based on claims and evidence."""
        if not self.outline.claims:
            self.manifest.research_completeness = 0.0
            return
        
        supported = sum(1 for c in self.outline.claims if c.get('status') == 'supported')
        self.manifest.research_completeness = supported / len(self.outline.claims)
        
        # Evidence strength based on number of citations per claim
        total_evidence = sum(len(c.get('evidence', [])) for c in self.outline.claims)
        avg_evidence = total_evidence / len(self.outline.claims) if self.outline.claims else 0
        self.manifest.evidence_strength = min(1.0, avg_evidence / 3)  # 3+ citations = full strength
    
    # ========== Reasoning (Continuous Write) ==========
    
    def add_reasoning(
        self,
        content: str,
        reasoning_type: str = 'analysis',  # 'analysis', 'synthesis', 'evaluation', 'question'
        related_claim: int = -1
    ) -> None:
        """Add reasoning to history (working memory writes here continuously)."""
        with self._lock:
            reasoning_item = {
                'content': content,
                'type': reasoning_type,
                'related_claim': related_claim,
                'timestamp': time.time()
            }
            
            self._reasoning_history.append(reasoning_item)
            
            # Keep in working context
            self.working_context.recent_reasoning.append(content[:200])
            if len(self.working_context.recent_reasoning) > 10:
                self.working_context.recent_reasoning = self.working_context.recent_reasoning[-10:]
            
            # Offload old reasoning to files
            if len(self._reasoning_history) > self.max_reasoning_history:
                self._offload_reasoning()
            
            self.working_context.has_unsaved_changes = True
            self._maybe_auto_save()
    
    def _offload_reasoning(self) -> None:
        """Offload old reasoning to history files."""
        # Keep recent, offload old
        to_offload = self._reasoning_history[:-self.max_reasoning_history]
        self._reasoning_history = self._reasoning_history[-self.max_reasoning_history:]
        
        # Save to timestamped file
        if to_offload:
            timestamp = int(time.time())
            history_file = self.workspace_dir / "reasoning" / "history" / f"reasoning_{timestamp}.json"
            self._save_json(str(history_file.relative_to(self.workspace_dir)), to_offload)
    
    def add_decision(
        self,
        decision: str,
        rationale: str,
        alternatives_considered: List[str] = None,
        confidence: float = 0.5
    ) -> None:
        """Record a key decision made during research/drafting."""
        with self._lock:
            self._decisions.append({
                'decision': decision,
                'rationale': rationale,
                'alternatives_considered': alternatives_considered or [],
                'confidence': confidence,
                'timestamp': time.time()
            })
            self.working_context.has_unsaved_changes = True
            self._maybe_auto_save()
    
    def set_current_task(self, task: str, claim_index: int = -1) -> None:
        """Set current focus (working memory updates this)."""
        with self._lock:
            self.working_context.current_task = task
            self.working_context.current_claim_index = claim_index
            self.working_context.last_activity = time.time()
    
    def add_pending_question(self, question: str) -> None:
        """Add a question to investigate."""
        with self._lock:
            if question not in self.working_context.pending_questions:
                self.working_context.pending_questions.append(question)
                self.working_context.has_unsaved_changes = True
    
    def resolve_question(self, question: str) -> None:
        """Mark a question as resolved."""
        with self._lock:
            if question in self.working_context.pending_questions:
                self.working_context.pending_questions.remove(question)
                self.working_context.has_unsaved_changes = True
    
    # ========== Feedback ==========
    
    def add_peer_review(
        self,
        reviewer_id: str,
        reviewer_type: str,
        vote: str,
        feedback: str,
        concerns: List[str] = None
    ) -> None:
        """Add peer review feedback."""
        with self._lock:
            self._peer_reviews.append({
                'reviewer_id': reviewer_id,
                'reviewer_type': reviewer_type,
                'vote': vote,
                'feedback': feedback,
                'concerns': concerns or [],
                'timestamp': time.time()
            })
            self.working_context.has_unsaved_changes = True
            self._maybe_auto_save()
    
    def add_orka_challenge(
        self,
        challenge: str,
        severity: str,
        affected_claims: List[int] = None,
        response: str = ""
    ) -> None:
        """Add ORKA challenge."""
        with self._lock:
            self._orka_challenges.append({
                'challenge': challenge,
                'severity': severity,
                'affected_claims': affected_claims or [],
                'response': response,
                'timestamp': time.time(),
                'addressed': bool(response)
            })
            self.working_context.has_unsaved_changes = True
            self._maybe_auto_save()
    
    def add_revision(
        self,
        description: str,
        changes: Dict[str, Any],
        triggered_by: str = ""  # 'peer_review', 'orka', 'self'
    ) -> None:
        """Record a revision to the proposal."""
        with self._lock:
            self.manifest.revision_count += 1
            self._revisions.append({
                'revision_number': self.manifest.revision_count,
                'description': description,
                'changes': changes,
                'triggered_by': triggered_by,
                'timestamp': time.time()
            })
            self.working_context.has_unsaved_changes = True
            self._maybe_auto_save()
    
    # ========== Artifacts (Code, Outputs) ==========
    
    def save_code(self, filename: str, content: str) -> str:
        """Save code artifact."""
        with self._lock:
            code_path = self.workspace_dir / "artifacts" / "code" / filename
            with open(code_path, 'w') as f:
                f.write(content)
            
            if filename not in self.outline.code_files:
                self.outline.code_files.append(filename)
            
            self.working_context.has_unsaved_changes = True
            return str(code_path)
    
    def get_code(self, filename: str) -> Optional[str]:
        """Get code artifact content."""
        code_path = self.workspace_dir / "artifacts" / "code" / filename
        if code_path.exists():
            with open(code_path, 'r') as f:
                return f.read()
        return None
    
    def save_output(self, filename: str, content: Any) -> str:
        """Save output artifact (JSON or text)."""
        output_path = self.workspace_dir / "artifacts" / "outputs" / filename
        with open(output_path, 'w') as f:
            if isinstance(content, (dict, list)):
                json.dump(content, f, indent=2)
            else:
                f.write(str(content))
        return str(output_path)
    
    # ========== Context Building ==========
    
    def get_context_summary(self, max_chars: int = 4000) -> str:
        """Get summary for LLM context injection."""
        parts = []
        char_count = 0
        
        # Title and thesis
        if self.outline.title:
            header = f"PROPOSAL: {self.outline.title}\nThesis: {self.outline.thesis}\nConfidence: {self.manifest.confidence:.2f}\n"
            parts.append(header)
            char_count += len(header)
        
        # Current task
        if self.working_context.current_task:
            task = f"\nCURRENT FOCUS: {self.working_context.current_task}\n"
            parts.append(task)
            char_count += len(task)
        
        # Claims status
        if self.outline.claims:
            parts.append("\nCLAIMS:")
            for i, claim in enumerate(self.outline.claims):
                status = claim.get('status', 'unknown')
                evidence_count = len(claim.get('evidence', []))
                claim_str = f"\n{i+1}. [{status}] {claim.get('claim', '')[:100]} ({evidence_count} evidence)"
                if char_count + len(claim_str) < max_chars:
                    parts.append(claim_str)
                    char_count += len(claim_str)
        
        # Recent findings
        if self.working_context.recent_findings:
            parts.append("\n\nRECENT RESEARCH:")
            for finding in self.working_context.recent_findings[-5:]:
                finding_str = f"\n- {finding.get('title', '')}: {finding.get('key_finding', '')[:100]}"
                if char_count + len(finding_str) < max_chars:
                    parts.append(finding_str)
                    char_count += len(finding_str)
        
        # Pending questions
        if self.working_context.pending_questions:
            parts.append("\n\nPENDING QUESTIONS:")
            for q in self.working_context.pending_questions[:3]:
                q_str = f"\n- {q}"
                if char_count + len(q_str) < max_chars:
                    parts.append(q_str)
                    char_count += len(q_str)
        
        return "".join(parts)
    
    def get_full_proposal_content(self) -> str:
        """Get full proposal content for submission."""
        sections = []
        
        sections.append(f"# {self.outline.title}")
        sections.append(f"\n## Thesis\n{self.outline.thesis}")
        
        if self.outline.claims:
            sections.append("\n## Claims")
            for i, claim in enumerate(self.outline.claims):
                sections.append(f"\n### Claim {i+1}: {claim.get('claim', '')}")
                sections.append(f"Confidence: {claim.get('confidence', 0):.2f}")
                
                evidence = self.get_evidence_for_claim(i)
                if evidence:
                    sections.append("\nEvidence:")
                    for e in evidence:
                        sections.append(f"- {e.get('title', '')}: {e.get('key_findings', [''])[0][:100]}")
        
        if self.outline.methodology:
            sections.append(f"\n## Methodology\n{self.outline.methodology}")
        
        if self.outline.expected_benefits:
            sections.append("\n## Expected Benefits")
            for benefit in self.outline.expected_benefits:
                sections.append(f"- {benefit}")
        
        if self.outline.identified_risks:
            sections.append("\n## Identified Risks")
            for risk in self.outline.identified_risks:
                sections.append(f"- {risk}")
        
        if self.outline.admitted_uncertainties:
            sections.append("\n## Admitted Uncertainties")
            for uncertainty in self.outline.admitted_uncertainties:
                sections.append(f"- {uncertainty}")
        
        if self.outline.rollback_plan:
            sections.append(f"\n## Rollback Plan\n{self.outline.rollback_plan}")
        
        return "\n".join(sections)
    
    # ========== Checkpoints ==========
    
    def checkpoint(self, note: str = "") -> str:
        """Create a checkpoint."""
        with self._lock:
            self.sync()  # Save current state first
            
            checkpoint_id = f"checkpoint_{int(time.time())}"
            checkpoint_dir = self.workspace_dir / "checkpoints" / checkpoint_id
            checkpoint_dir.mkdir(parents=True, exist_ok=True)
            
            # Copy key files
            for filename in ["manifest.json", "outline.json", "working_context.json"]:
                src = self.workspace_dir / filename
                if src.exists():
                    shutil.copy(src, checkpoint_dir / filename)
            
            # Copy research
            research_src = self.workspace_dir / "research"
            research_dst = checkpoint_dir / "research"
            if research_src.exists():
                shutil.copytree(research_src, research_dst)
            
            # Save metadata
            self._save_json(f"checkpoints/{checkpoint_id}/metadata.json", {
                'checkpoint_id': checkpoint_id,
                'note': note,
                'created_at': time.time(),
                'manifest_status': self.manifest.status,
                'confidence': self.manifest.confidence
            })
            
            return checkpoint_id
    
    def restore_checkpoint(self, checkpoint_id: str) -> bool:
        """Restore from checkpoint."""
        checkpoint_dir = self.workspace_dir / "checkpoints" / checkpoint_id
        if not checkpoint_dir.exists():
            return False
        
        with self._lock:
            try:
                # Restore files
                for filename in ["manifest.json", "outline.json", "working_context.json"]:
                    src = checkpoint_dir / filename
                    if src.exists():
                        shutil.copy(src, self.workspace_dir / filename)
                
                # Restore research
                research_src = checkpoint_dir / "research"
                research_dst = self.workspace_dir / "research"
                if research_src.exists():
                    shutil.rmtree(research_dst, ignore_errors=True)
                    shutil.copytree(research_src, research_dst)
                
                # Reload state
                self.manifest = self._load_or_create_manifest()
                self.outline = self._load_or_create_outline()
                self.working_context = self._load_or_create_context()
                self._distilled_papers = self._load_json("research/distilled_papers.json", {})
                self._citations = self._load_json("research/citations.json", {})
                self._evidence_map = self._load_json("research/evidence_map.json", {})
                
                return True
            except Exception as e:
                logger.error(f"Failed to restore checkpoint: {e}")
                return False
    
    # ========== Condensation (To Persistent Memory) ==========
    
    def condense_to_persistent(self) -> Dict[str, Any]:
        """
        Condense workspace into persistent memory format.
        Called when proposal is complete (approved/rejected/archived).
        
        Returns distilled data for storage in personal memory.
        """
        with self._lock:
            self.sync()  # Final save
            
            # Extract key insights
            insights = []
            
            # From successful claims
            for claim in self.outline.claims:
                if claim.get('status') == 'supported' and claim.get('confidence', 0) > 0.6:
                    insights.append({
                        'type': 'validated_claim',
                        'content': claim.get('claim', ''),
                        'confidence': claim.get('confidence', 0),
                        'evidence_count': len(claim.get('evidence', []))
                    })
            
            # From decisions
            for decision in self._decisions:
                if decision.get('confidence', 0) > 0.6:
                    insights.append({
                        'type': 'decision',
                        'content': decision.get('decision', ''),
                        'rationale': decision.get('rationale', ''),
                        'confidence': decision.get('confidence', 0)
                    })
            
            # From feedback patterns
            rejection_reasons = []
            for review in self._peer_reviews:
                if review.get('vote') == 'reject':
                    rejection_reasons.extend(review.get('concerns', []))
            
            return {
                'proposal_id': self.proposal_id,
                'title': self.manifest.title,
                'thesis': self.outline.thesis,
                'domain': self.manifest.domain,
                'outcome': self.manifest.outcome,
                'reward': self.manifest.reward,
                'confidence_final': self.manifest.confidence,
                'insights': insights,
                'rejection_reasons': rejection_reasons,
                'revision_count': self.manifest.revision_count,
                'research_completeness': self.manifest.research_completeness,
                'evidence_strength': self.manifest.evidence_strength,
                'papers_used': len(self._distilled_papers),
                'citations_used': len(self._citations),
                'created_at': self.manifest.created_at,
                'completed_at': self.manifest.completed_at
            }
    
    # ========== Cleanup ==========
    
    def archive(self) -> str:
        """Archive the workspace (compress and move)."""
        with self._lock:
            self.sync()
            self.set_status('archived')
            
            # Create archive
            archive_name = f"{self.proposal_id}_archive"
            archive_path = shutil.make_archive(
                str(self.base_dir / "archives" / archive_name),
                'zip',
                str(self.workspace_dir)
            )
            
            return archive_path
    
    def delete(self) -> None:
        """Delete the workspace."""
        if self.workspace_dir.exists():
            shutil.rmtree(self.workspace_dir)
    
    def get_stats(self) -> Dict[str, Any]:
        """Get workspace statistics."""
        return {
            'proposal_id': self.proposal_id,
            'title': self.manifest.title,
            'status': self.manifest.status,
            'confidence': self.manifest.confidence,
            'research_completeness': self.manifest.research_completeness,
            'evidence_strength': self.manifest.evidence_strength,
            'claims_count': len(self.outline.claims),
            'supported_claims': sum(1 for c in self.outline.claims if c.get('status') == 'supported'),
            'papers_distilled': len(self._distilled_papers),
            'citations': len(self._citations),
            'reasoning_items': len(self._reasoning_history),
            'decisions': len(self._decisions),
            'peer_reviews': len(self._peer_reviews),
            'orka_challenges': len(self._orka_challenges),
            'revisions': self.manifest.revision_count,
            'pending_questions': len(self.working_context.pending_questions),
            'created_at': self.manifest.created_at,
            'updated_at': self.manifest.updated_at
        }

