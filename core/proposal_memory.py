"""
Proposal Building Memory - Progressive Compression System
==========================================================

Keeps agent context small as proposals develop through stages.
Memory is compressed/summarized at each stage transition to prevent OOM.

Memory Tiers:
- TIER 1 (Drafting): Full working memory (~5K tokens)
- TIER 2 (First Review): Condensed summary (~2.5K tokens)  
- TIER 3 (Second Review): Minimal proposal (~1.5K tokens)
- TIER 4 (Sandbox): Execution only (~800 tokens)
- TIER 5 (Distilled): One-liner outcome (~100 tokens)
"""

import json
import time
from dataclasses import dataclass, field, asdict
from typing import List, Dict, Any, Optional
from enum import Enum, auto
from pathlib import Path
import threading
import logging

logger = logging.getLogger(__name__)


class ProposalStage(Enum):
    """Proposal lifecycle stages with progressive compression."""
    # TIER 1: Full working memory
    DRAFTING = 1
    DOMAIN_RESEARCH = 2
    INITIAL_DRAFT = 3
    
    # TIER 2: Condensed (after first peer review)
    PEER_REVIEW_1 = 4
    REVISION_1 = 5
    PAGEQA_RESEARCH = 6
    REVISION_2 = 7
    
    # TIER 3: Minimal (after second peer review)
    PEER_REVIEW_2 = 8
    REVISION_3 = 9
    ORKA_COUNTERPOINT = 10
    REVISION_4 = 11
    VOTING = 12
    
    # TIER 4: Execution only
    SANDBOX_INITIAL = 13
    SANDBOX_DEBUG_1 = 14
    SANDBOX_DEBUG_2 = 15
    SANDBOX_DEBUG_3 = 16
    SANDBOX_METRICS = 17
    
    # TIER 5: Distilled
    REWARD_COMPUTE = 18
    RL_UPDATE = 19
    MEMORY_DISTILL = 20
    COMPLETE = 21
    REJECTED = 22


@dataclass
class PeerFeedback:
    """Compressed peer feedback."""
    reviewer_id: str
    approved: bool
    key_points: List[str]  # Max 3 bullet points
    concerns: List[str]    # Max 2 concerns
    timestamp: float = field(default_factory=time.time)


@dataclass
class ORKACounterpoint:
    """ORKA's adversarial challenge."""
    challenge_id: str
    challenge_text: str
    severity: str  # 'minor', 'moderate', 'critical'
    addressed: bool = False
    response_summary: Optional[str] = None


@dataclass
class SandboxAttempt:
    """Record of a sandbox execution attempt."""
    attempt_number: int
    success: bool
    error_type: Optional[str] = None  # 'syntax', 'runtime', 'timeout', 'import'
    error_snippet: Optional[str] = None  # First 200 chars of error
    orka_tips: List[str] = field(default_factory=list)  # Max 3 tips
    execution_time_ms: int = 0


@dataclass
class ProposalMemory:
    """
    Progressive compression proposal memory.
    
    Memory is automatically compressed when transitioning between tiers
    to keep context under ~5K tokens at any time.
    """
    
    # Core identifiers
    proposal_id: str
    agent_id: str
    stage: ProposalStage = ProposalStage.DRAFTING
    created_at: float = field(default_factory=time.time)
    updated_at: float = field(default_factory=time.time)
    
    # === TIER 1: Full Working Memory (stages 1-3) ===
    # Evicted after first peer review
    raw_pageqa_results: Optional[str] = None      # Full PAGEQA response
    draft_iterations: List[str] = field(default_factory=list)  # All draft versions
    scratch_notes: Optional[str] = None           # Agent's thinking/reasoning
    domain_research: Optional[str] = None         # Domain-specific findings
    
    # === TIER 2: Condensed (stages 4-7) ===
    # Summarized from Tier 1, evicted after second peer review
    research_summary: Optional[str] = None        # Key findings only (~500 tokens)
    current_draft: Optional[str] = None           # Latest version only
    feedback_round_1: List[PeerFeedback] = field(default_factory=list)
    revision_notes_1: Optional[str] = None        # What was changed
    
    # === TIER 3: Minimal (stages 8-12) ===
    # Summarized from Tier 2, evicted after vote
    final_proposal: Optional[str] = None          # The proposal text
    key_claims: List[str] = field(default_factory=list)  # Max 5 claims
    feedback_round_2: List[PeerFeedback] = field(default_factory=list)
    orka_counterpoints: List[ORKACounterpoint] = field(default_factory=list)
    vote_results: Dict[str, bool] = field(default_factory=dict)  # agent_id -> vote
    
    # === TIER 4: Execution (stages 13-17) ===
    # Minimal info needed for sandbox
    code_diff: Optional[str] = None               # The actual code changes
    expected_metrics: Dict[str, float] = field(default_factory=dict)
    pass_criteria: Optional[str] = None
    sandbox_attempts: List[SandboxAttempt] = field(default_factory=list)
    final_metrics: Dict[str, float] = field(default_factory=dict)
    
    # === TIER 5: Distilled (permanent) ===
    outcome: Optional[str] = None                 # 'approved', 'rejected', 'failed'
    outcome_summary: Optional[str] = None         # "Improved X by Y% using Z"
    lessons_learned: Optional[str] = None         # "Z doesn't work because..."
    reward: float = 0.0
    
    def advance_stage(self, new_stage: ProposalStage) -> None:
        """Advance to new stage with automatic compression."""
        old_tier = self._get_tier(self.stage)
        new_tier = self._get_tier(new_stage)
        
        if new_tier > old_tier:
            self._compress_to_tier(new_tier)
        
        self.stage = new_stage
        self.updated_at = time.time()
        logger.info(f"Proposal {self.proposal_id} advanced to {new_stage.name}")
    
    def _get_tier(self, stage: ProposalStage) -> int:
        """Get tier number for a stage."""
        if stage.value <= 3:
            return 1
        elif stage.value <= 7:
            return 2
        elif stage.value <= 12:
            return 3
        elif stage.value <= 17:
            return 4
        else:
            return 5
    
    def _compress_to_tier(self, target_tier: int) -> None:
        """Compress memory to target tier, evicting lower tier data."""
        
        if target_tier >= 2 and self._get_tier(self.stage) < 2:
            # TIER 1 → TIER 2: Summarize research, keep only latest draft
            logger.info(f"Compressing {self.proposal_id} to Tier 2")
            
            # Summarize research (in production, use LLM)
            if self.raw_pageqa_results:
                self.research_summary = self._extract_key_findings(self.raw_pageqa_results)
            
            # Keep only latest draft
            if self.draft_iterations:
                self.current_draft = self.draft_iterations[-1]
            
            # Evict Tier 1
            self.raw_pageqa_results = None
            self.draft_iterations = []
            self.scratch_notes = None
            self.domain_research = None
        
        if target_tier >= 3 and self._get_tier(self.stage) < 3:
            # TIER 2 → TIER 3: Extract final proposal and key claims
            logger.info(f"Compressing {self.proposal_id} to Tier 3")
            
            self.final_proposal = self.current_draft
            self.key_claims = self._extract_claims(self.current_draft or "")
            
            # Evict Tier 2
            self.research_summary = None
            self.current_draft = None
            self.revision_notes_1 = None
        
        if target_tier >= 4 and self._get_tier(self.stage) < 4:
            # TIER 3 → TIER 4: Keep only code and metrics
            logger.info(f"Compressing {self.proposal_id} to Tier 4")
            
            self.code_diff = self._extract_code(self.final_proposal or "")
            
            # Evict Tier 3
            self.final_proposal = None
            self.key_claims = []
            self.feedback_round_2 = []
            self.orka_counterpoints = []
            self.vote_results = {}
        
        if target_tier >= 5 and self._get_tier(self.stage) < 5:
            # TIER 4 → TIER 5: Distill to one-liner
            logger.info(f"Compressing {self.proposal_id} to Tier 5 (distilled)")
            
            self._distill_outcome()
            
            # Evict Tier 4
            self.code_diff = None
            self.expected_metrics = {}
            self.pass_criteria = None
            self.sandbox_attempts = []
    
    def _extract_key_findings(self, raw_results: str) -> str:
        """Extract key findings from raw PAGEQA results."""
        # Simple truncation for now; use LLM summarization in production
        if len(raw_results) > 1500:
            return raw_results[:1500] + "..."
        return raw_results
    
    def _extract_claims(self, draft: str, max_claims: int = 5) -> List[str]:
        """Extract key claims from proposal draft."""
        # Simple extraction; use LLM in production
        lines = draft.split('\n')
        claims = []
        for line in lines:
            line = line.strip()
            if line.startswith('- ') or line.startswith('* '):
                claims.append(line[2:])
            if len(claims) >= max_claims:
                break
        return claims
    
    def _extract_code(self, proposal: str) -> Optional[str]:
        """Extract code block from proposal."""
        # Look for code blocks
        import re
        code_blocks = re.findall(r'```(?:python)?\n(.*?)```', proposal, re.DOTALL)
        if code_blocks:
            return code_blocks[0][:2000]  # Max 2000 chars
        return None
    
    def _distill_outcome(self) -> None:
        """Create one-liner outcome summary."""
        if self.final_metrics:
            improvements = []
            for metric, value in self.final_metrics.items():
                if value > 0:
                    improvements.append(f"{metric}: +{value:.1%}")
            if improvements:
                self.outcome_summary = f"Improved {', '.join(improvements)}"
            else:
                self.outcome_summary = "No measurable improvement"
        else:
            self.outcome_summary = self.outcome or "Unknown outcome"
    
    def get_context_tokens(self) -> int:
        """Estimate current context size in tokens."""
        total_chars = 0
        
        # Count all string fields
        for field_value in [
            self.raw_pageqa_results, self.scratch_notes, self.domain_research,
            self.research_summary, self.current_draft, self.revision_notes_1,
            self.final_proposal, self.code_diff, self.pass_criteria,
            self.outcome_summary, self.lessons_learned
        ]:
            if field_value:
                total_chars += len(field_value)
        
        # Count list fields
        total_chars += sum(len(d) for d in self.draft_iterations)
        total_chars += sum(len(c) for c in self.key_claims)
        total_chars += sum(len(str(f)) for f in self.feedback_round_1)
        total_chars += sum(len(str(f)) for f in self.feedback_round_2)
        total_chars += sum(len(str(a)) for a in self.sandbox_attempts)
        
        # Rough: 4 chars per token
        return total_chars // 4
    
    def get_active_context(self) -> Dict[str, Any]:
        """Get only the active tier's context for LLM."""
        tier = self._get_tier(self.stage)
        
        context = {
            "proposal_id": self.proposal_id,
            "stage": self.stage.name,
            "tier": tier
        }
        
        if tier == 1:
            context.update({
                "raw_research": self.raw_pageqa_results,
                "drafts": self.draft_iterations,
                "notes": self.scratch_notes,
                "domain": self.domain_research
            })
        elif tier == 2:
            context.update({
                "research_summary": self.research_summary,
                "current_draft": self.current_draft,
                "feedback": [asdict(f) for f in self.feedback_round_1],
                "revision_notes": self.revision_notes_1
            })
        elif tier == 3:
            context.update({
                "final_proposal": self.final_proposal,
                "key_claims": self.key_claims,
                "feedback": [asdict(f) for f in self.feedback_round_2],
                "counterpoints": [asdict(c) for c in self.orka_counterpoints],
                "votes": self.vote_results
            })
        elif tier == 4:
            context.update({
                "code_diff": self.code_diff,
                "expected_metrics": self.expected_metrics,
                "pass_criteria": self.pass_criteria,
                "attempts": [asdict(a) for a in self.sandbox_attempts]
            })
        else:  # tier == 5
            context.update({
                "outcome": self.outcome,
                "summary": self.outcome_summary,
                "lessons": self.lessons_learned,
                "reward": self.reward
            })
        
        return context
    
    def to_dict(self) -> Dict[str, Any]:
        """Serialize to dictionary."""
        return {
            "proposal_id": self.proposal_id,
            "agent_id": self.agent_id,
            "stage": self.stage.name,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
            "tier": self._get_tier(self.stage),
            "context_tokens": self.get_context_tokens(),
            "active_context": self.get_active_context()
        }
    
    def save(self, base_dir: str = "./data/proposal_memory") -> None:
        """Save to disk."""
        path = Path(base_dir) / f"{self.proposal_id}.json"
        path.parent.mkdir(parents=True, exist_ok=True)
        with open(path, 'w') as f:
            json.dump(asdict(self), f, indent=2, default=str)
    
    @classmethod
    def load(cls, proposal_id: str, base_dir: str = "./data/proposal_memory") -> Optional['ProposalMemory']:
        """Load from disk."""
        path = Path(base_dir) / f"{proposal_id}.json"
        if not path.exists():
            return None
        
        with open(path, 'r') as f:
            data = json.load(f)
        
        # Reconstruct enums and dataclasses
        data['stage'] = ProposalStage[data['stage']]
        data['feedback_round_1'] = [PeerFeedback(**f) for f in data.get('feedback_round_1', [])]
        data['feedback_round_2'] = [PeerFeedback(**f) for f in data.get('feedback_round_2', [])]
        data['orka_counterpoints'] = [ORKACounterpoint(**c) for c in data.get('orka_counterpoints', [])]
        data['sandbox_attempts'] = [SandboxAttempt(**a) for a in data.get('sandbox_attempts', [])]
        
        return cls(**data)


@dataclass
class PeerReviewContext:
    """Minimal context for reviewing another agent's proposal."""
    proposal_id: str
    proposer_id: str
    proposal_summary: str      # ~500 tokens max
    key_claims: List[str]      # ~200 tokens max
    code_snippet: Optional[str] = None  # ~300 tokens max
    review_round: int = 1
    
    # Reviewer's output
    feedback: Optional[str] = None
    vote: Optional[bool] = None
    concerns: List[str] = field(default_factory=list)
    
    def get_context_tokens(self) -> int:
        """Estimate context size."""
        total = len(self.proposal_summary)
        total += sum(len(c) for c in self.key_claims)
        total += len(self.code_snippet or "")
        return total // 4  # ~1000 tokens max


@dataclass
class SandboxFixContext:
    """Minimal context for agent to fix sandbox failure."""
    proposal_id: str
    attempt_number: int
    max_attempts: int = 3
    error_type: str = ""
    error_snippet: str = ""          # First 500 chars
    orka_analysis: str = ""          # ~200 tokens
    orka_suggestions: List[str] = field(default_factory=list)  # 2-3 bullets
    code_hint: Optional[str] = None  # Optional fix snippet
    original_code: str = ""
    
    def get_context_tokens(self) -> int:
        """Estimate context size."""
        total = len(self.error_snippet) + len(self.orka_analysis)
        total += sum(len(s) for s in self.orka_suggestions)
        total += len(self.code_hint or "")
        total += len(self.original_code)
        return total // 4  # ~1500 tokens max


class ProposalMemoryManager:
    """
    Manages proposal memory across all agents.
    Handles context swapping between own proposal and peer review.
    """
    
    def __init__(self, base_dir: str = "./data/proposal_memory"):
        self.base_dir = Path(base_dir)
        self.base_dir.mkdir(parents=True, exist_ok=True)
        self._memories: Dict[str, ProposalMemory] = {}
        self._parked: Dict[str, ProposalMemory] = {}  # Parked while doing peer review
        self._lock = threading.RLock()
    
    def create_proposal(self, proposal_id: str, agent_id: str) -> ProposalMemory:
        """Create new proposal memory."""
        with self._lock:
            memory = ProposalMemory(proposal_id=proposal_id, agent_id=agent_id)
            self._memories[proposal_id] = memory
            memory.save(str(self.base_dir))
            return memory
    
    def get_proposal(self, proposal_id: str) -> Optional[ProposalMemory]:
        """Get proposal memory, loading from disk if needed."""
        with self._lock:
            if proposal_id in self._memories:
                return self._memories[proposal_id]
            
            memory = ProposalMemory.load(proposal_id, str(self.base_dir))
            if memory:
                self._memories[proposal_id] = memory
            return memory
    
    def park_proposal(self, proposal_id: str) -> bool:
        """Park a proposal (save to slot B) while agent does peer review."""
        with self._lock:
            if proposal_id in self._memories:
                memory = self._memories[proposal_id]
                memory.save(str(self.base_dir))
                self._parked[proposal_id] = memory
                del self._memories[proposal_id]
                logger.info(f"Parked proposal {proposal_id}")
                return True
            return False
    
    def restore_proposal(self, proposal_id: str) -> Optional[ProposalMemory]:
        """Restore a parked proposal after peer review."""
        with self._lock:
            if proposal_id in self._parked:
                memory = self._parked[proposal_id]
                self._memories[proposal_id] = memory
                del self._parked[proposal_id]
                logger.info(f"Restored proposal {proposal_id}")
                return memory
            return None
    
    def get_all_active(self) -> List[ProposalMemory]:
        """Get all active (non-parked) proposals."""
        with self._lock:
            return list(self._memories.values())
    
    def get_proposals_by_agent(self, agent_id: str) -> List[ProposalMemory]:
        """Get all proposals for an agent."""
        with self._lock:
            return [m for m in self._memories.values() if m.agent_id == agent_id]
    
    def get_proposals_at_stage(self, stage: ProposalStage) -> List[ProposalMemory]:
        """Get all proposals at a specific stage."""
        with self._lock:
            return [m for m in self._memories.values() if m.stage == stage]
    
    def advance_proposal(self, proposal_id: str, new_stage: ProposalStage) -> bool:
        """Advance a proposal to a new stage with compression."""
        with self._lock:
            memory = self.get_proposal(proposal_id)
            if memory:
                memory.advance_stage(new_stage)
                memory.save(str(self.base_dir))
                return True
            return False
    
    def get_memory_stats(self) -> Dict[str, Any]:
        """Get memory usage statistics."""
        with self._lock:
            stats = {
                "active_proposals": len(self._memories),
                "parked_proposals": len(self._parked),
                "by_tier": {1: 0, 2: 0, 3: 0, 4: 0, 5: 0},
                "total_tokens": 0
            }
            
            for memory in self._memories.values():
                tier = memory._get_tier(memory.stage)
                stats["by_tier"][tier] += 1
                stats["total_tokens"] += memory.get_context_tokens()
            
            return stats
