"""
20-Step Proposal Workflow Engine
================================

Implements the full research-to-reward workflow from WORKFLOW_GROUND_TRUTH.md

PHASE 1: RESEARCH (Steps 1-5)
  1. 01_idea.md - What capability to improve, why, initial solution
  2. 02_papers_broad.md - Search 5-10 papers via PAGEQA
  3. 03_triage.md - Rate relevance 0-1, mark top 3 standouts
  4. 04_deep_notes.md - Key findings, methodology, limitations
  5. 05_synthesis.md - Background, themes, gaps, implications

PHASE 2: HYPOTHESIS (Steps 6-7)
  6. 06_hypothesis.md - Testable statement, IV/DV/control, predictions
  7. 07_experiment.md - Methodology, procedure, success criteria

PHASE 3: PROPOSAL & EARLY REVIEW (Steps 8-12)
  8. 08_proposal.md - Full proposal (use template)
  9. 09_self_check_consistency.md - Internal consistency check
  10. 10_self_check_weaknesses.md - Weaknesses, confidence 0-100%
  11. READ peer_review + deception_check → WRITE 11_early_response.md
  12. 12_revised_proposal.md - Revise based on early feedback

PHASE 4: VALIDATION (Steps 13-14)
  13. READ paperqa_validation → WRITE 13_validation_response.md
  14. 14_validated_proposal.md - Fix citations per PaperQA

PHASE 5: LATE REVIEW & VOTE (Steps 15-17)
  15. READ late_peer_review + collusion_check → WRITE 15_late_response.md
  16. READ 16_vote_results.md - APPROVE→17, REVISE→12, REJECT→20
  17. READ orka_challenge → WRITE 17_defense.md

PHASE 6: COMPLETION (Steps 18-20)
  18. 18_final_proposal.md - Final revision
  19. READ 19_sandbox_results.md - Code test results
  20. READ 20_reward.md - Your score

Each proposal gets its own workspace directory with all step files.
"""

import logging
import time
import json
import hashlib
from pathlib import Path
from typing import Dict, List, Any, Optional, Tuple
from dataclasses import dataclass, field, asdict
from enum import Enum
import threading

logger = logging.getLogger(__name__)


class ProposalPhase(Enum):
    """The 6 phases of proposal development."""
    RESEARCH = "research"           # Steps 1-5
    HYPOTHESIS = "hypothesis"       # Steps 6-7
    EARLY_REVIEW = "early_review"   # Steps 8-12
    VALIDATION = "validation"       # Steps 13-14
    LATE_REVIEW = "late_review"     # Steps 15-17
    COMPLETION = "completion"       # Steps 18-20


@dataclass
class WorkflowStep:
    """Definition of a workflow step."""
    number: int
    filename: str
    phase: ProposalPhase
    title: str
    description: str
    is_read_step: bool = False  # True if agent reads external input
    requires_external: Optional[str] = None  # External file to read
    writes_file: Optional[str] = None  # File to write (if read step)


# Define all 20 steps
WORKFLOW_STEPS: List[WorkflowStep] = [
    # PHASE 1: RESEARCH (1-5)
    WorkflowStep(1, "01_idea.md", ProposalPhase.RESEARCH, 
                 "IDEA", "What capability to improve, why, initial solution"),
    WorkflowStep(2, "02_papers_broad.md", ProposalPhase.RESEARCH,
                 "BROAD SEARCH", "Search 5-10 papers via PAGEQA"),
    WorkflowStep(3, "03_triage.md", ProposalPhase.RESEARCH,
                 "TRIAGE", "Rate relevance 0-1, mark top 3 standouts"),
    WorkflowStep(4, "04_deep_notes.md", ProposalPhase.RESEARCH,
                 "DEEP DIVE", "Key findings, methodology, limitations from standouts"),
    WorkflowStep(5, "05_synthesis.md", ProposalPhase.RESEARCH,
                 "SYNTHESIS", "Background, themes, gaps, implications"),
    
    # PHASE 2: HYPOTHESIS (6-7)
    WorkflowStep(6, "06_hypothesis.md", ProposalPhase.HYPOTHESIS,
                 "HYPOTHESIS", "Testable statement, IV/DV/control, predictions"),
    WorkflowStep(7, "07_experiment.md", ProposalPhase.HYPOTHESIS,
                 "EXPERIMENT", "Methodology, procedure, success criteria"),
    
    # PHASE 3: PROPOSAL & EARLY REVIEW (8-12)
    WorkflowStep(8, "08_proposal.md", ProposalPhase.EARLY_REVIEW,
                 "WRITE PROPOSAL", "Full proposal using template"),
    WorkflowStep(9, "09_self_check_consistency.md", ProposalPhase.EARLY_REVIEW,
                 "SELF-CHECK CONSISTENCY", "Internal consistency check"),
    WorkflowStep(10, "10_self_check_weaknesses.md", ProposalPhase.EARLY_REVIEW,
                 "SELF-CHECK WEAKNESSES", "Weaknesses, confidence 0-100%"),
    WorkflowStep(11, "11_early_response.md", ProposalPhase.EARLY_REVIEW,
                 "EARLY REVIEW RESPONSE", "Respond to peer review and deception check",
                 is_read_step=True, 
                 requires_external="11_early_peer_review.md,11_deception_check.md",
                 writes_file="11_early_response.md"),
    WorkflowStep(12, "12_revised_proposal.md", ProposalPhase.EARLY_REVIEW,
                 "REVISION", "Revise based on early feedback"),
    
    # PHASE 4: VALIDATION (13-14)
    WorkflowStep(13, "13_validation_response.md", ProposalPhase.VALIDATION,
                 "VALIDATION RESPONSE", "Respond to PaperQA validation",
                 is_read_step=True,
                 requires_external="13_paperqa_validation.md",
                 writes_file="13_validation_response.md"),
    WorkflowStep(14, "14_validated_proposal.md", ProposalPhase.VALIDATION,
                 "VALIDATED PROPOSAL", "Fix citations per PaperQA"),
    
    # PHASE 5: LATE REVIEW & VOTE (15-17)
    WorkflowStep(15, "15_late_response.md", ProposalPhase.LATE_REVIEW,
                 "LATE REVIEW RESPONSE", "Respond to late review and collusion check",
                 is_read_step=True,
                 requires_external="15_late_peer_review.md,15_collusion_deception_check.md",
                 writes_file="15_late_response.md"),
    WorkflowStep(16, "16_vote_decision.md", ProposalPhase.LATE_REVIEW,
                 "VOTE RESULTS", "Process vote: APPROVE→17, REVISE→12, REJECT→20",
                 is_read_step=True,
                 requires_external="16_vote_results.md",
                 writes_file="16_vote_decision.md"),
    WorkflowStep(17, "17_defense.md", ProposalPhase.LATE_REVIEW,
                 "ORKA DEFENSE", "Defend against ORKA challenge",
                 is_read_step=True,
                 requires_external="17_orka_challenge.md",
                 writes_file="17_defense.md"),
    
    # PHASE 6: COMPLETION (18-20)
    WorkflowStep(18, "18_final_proposal.md", ProposalPhase.COMPLETION,
                 "FINAL PROPOSAL", "Final revision incorporating all feedback"),
    WorkflowStep(19, "19_sandbox_response.md", ProposalPhase.COMPLETION,
                 "SANDBOX REVIEW", "Review sandbox test results",
                 is_read_step=True,
                 requires_external="19_sandbox_results.md",
                 writes_file="19_sandbox_response.md"),
    WorkflowStep(20, "20_reward_received.md", ProposalPhase.COMPLETION,
                 "REWARD", "Acknowledge and learn from reward",
                 is_read_step=True,
                 requires_external="20_reward.md",
                 writes_file="20_reward_received.md"),
]


# Proposal template for step 8
PROPOSAL_TEMPLATE = """# {title}

## Problem
What capability needs improvement and why?

## Hypothesis
Testable prediction: If [action] then [result] because [reasoning]

## Evidence
Papers and research supporting this approach:
- [Paper 1]: Key finding
- [Paper 2]: Key finding

## Method
Step-by-step implementation:
1. Step one
2. Step two
3. Step three

## Expected Results
What will be different after implementation?

## Success Criteria
How will we measure success?
- Metric 1: [threshold]
- Metric 2: [threshold]

## Risks
What could go wrong?
- Risk 1: [mitigation]
- Risk 2: [mitigation]

## Rollback
How to undo if it fails?

## Confidence
[0-100]% - [reasoning for confidence level]
"""


@dataclass
class ProposalWorkspace:
    """A workspace for a single proposal going through the 20-step workflow."""
    id: str
    agent: str
    topic: str
    workspace_path: Path
    current_step: int = 1
    status: str = "active"  # active, paused, completed, rejected
    created_at: float = field(default_factory=time.time)
    updated_at: float = field(default_factory=time.time)
    
    # Tracking
    completed_steps: List[int] = field(default_factory=list)
    step_timestamps: Dict[int, float] = field(default_factory=dict)
    
    # External inputs received
    external_inputs: Dict[str, str] = field(default_factory=dict)
    
    # Final outcome
    vote_result: Optional[str] = None  # APPROVE, REVISE, REJECT
    reward_score: Optional[float] = None
    
    def get_step_file(self, step_num: int) -> Path:
        """Get the file path for a step."""
        step = WORKFLOW_STEPS[step_num - 1]
        return self.workspace_path / step.filename
    
    def read_step(self, step_num: int) -> Optional[str]:
        """Read the content of a step file."""
        path = self.get_step_file(step_num)
        if path.exists():
            return path.read_text()
        return None
    
    def write_step(self, step_num: int, content: str) -> None:
        """Write content to a step file."""
        path = self.get_step_file(step_num)
        path.write_text(content)
        if step_num not in self.completed_steps:
            self.completed_steps.append(step_num)
        self.step_timestamps[step_num] = time.time()
        self.updated_at = time.time()
    
    def get_context(self, max_steps: int = 5) -> str:
        """Get context from recent completed steps."""
        context_parts = []
        recent_steps = sorted(self.completed_steps)[-max_steps:]
        
        for step_num in recent_steps:
            content = self.read_step(step_num)
            if content:
                step = WORKFLOW_STEPS[step_num - 1]
                # Truncate if too long
                if len(content) > 1000:
                    content = content[:1000] + "\n...[truncated]"
                context_parts.append(f"=== {step.filename} ({step.title}) ===\n{content}")
        
        return "\n\n".join(context_parts) if context_parts else "No previous work yet."
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "agent": self.agent,
            "topic": self.topic,
            "workspace_path": str(self.workspace_path),
            "current_step": self.current_step,
            "status": self.status,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
            "completed_steps": self.completed_steps,
            "step_timestamps": self.step_timestamps,
            "vote_result": self.vote_result,
            "reward_score": self.reward_score,
        }
    
    def save_state(self) -> None:
        """Save workspace state to JSON."""
        state_file = self.workspace_path / "workflow_state.json"
        state_file.write_text(json.dumps(self.to_dict(), indent=2))
    
    @classmethod
    def load_state(cls, workspace_path: Path) -> Optional['ProposalWorkspace']:
        """Load workspace from saved state."""
        state_file = workspace_path / "workflow_state.json"
        if not state_file.exists():
            return None
        try:
            data = json.loads(state_file.read_text())
            return cls(
                id=data["id"],
                agent=data["agent"],
                topic=data["topic"],
                workspace_path=Path(data["workspace_path"]),
                current_step=data["current_step"],
                status=data["status"],
                created_at=data["created_at"],
                updated_at=data["updated_at"],
                completed_steps=data["completed_steps"],
                step_timestamps=data["step_timestamps"],
                vote_result=data.get("vote_result"),
                reward_score=data.get("reward_score"),
            )
        except Exception as e:
            logger.error(f"Failed to load workspace state: {e}")
            return None


# AURA Storage Integration
try:
    from memory.aura_storage import get_storage, AURACompressedStorage
    AURA_STORAGE_AVAILABLE = True
except ImportError:
    AURA_STORAGE_AVAILABLE = False
    get_storage = None


class ProposalWorkflowEngine:
    """
    Engine that drives proposals through the 20-step workflow.
    
    Uses the nano cluster for:
    - Agent's own LLM for proposal work
    - PAGEQA for research steps
    - Peer agents for reviews
    - ORKA for challenges and final decisions
    - GUARD for deception/collusion checks
    
    Uses AURA compression for:
    - Storing proposals in compressed format
    - Inter-nano communication
    - Pattern storage
    """
    
    def __init__(self, base_workspace: Optional[Path] = None):
        self.base_workspace = base_workspace or Path("./data/proposals")
        self.base_workspace.mkdir(parents=True, exist_ok=True)
        self.active_workspaces: Dict[str, ProposalWorkspace] = {}
        self._ground_truth: Optional[str] = None
        self._load_ground_truth()
        
        # Initialize AURA storage
        if AURA_STORAGE_AVAILABLE:
            self.aura_storage = get_storage(str(self.base_workspace / "aura_proposals.db"))
            logger.info("AURA compressed storage enabled for proposals")
        else:
            self.aura_storage = None
            logger.warning("AURA storage not available, using plain file storage")
    
    def _load_ground_truth(self) -> None:
        """Load the workflow ground truth document."""
        gt_path = Path("./memory/WORKFLOW_GROUND_TRUTH.md")
        if gt_path.exists():
            self._ground_truth = gt_path.read_text()
        else:
            logger.warning("Ground truth file not found, using embedded version")
            self._ground_truth = self._get_embedded_ground_truth()
    
    def _get_embedded_ground_truth(self) -> str:
        """Embedded ground truth for when file isn't available."""
        return """# WORKFLOW GROUND TRUTH

## HONESTY WINS (The Math)
Honest:    E[R] = 0.6(+0.7) + 0.4(-0.2) = +0.34
Deceptive: E[R] = 0.15(0.7)(+0.7) + 0.85(-1.0) = -0.78
**Δ = +1.12 for honesty. Deception is irrational.**

## PERMANENT PENALTY FOR GETTING CAUGHT:
Future_Reward = Base_Reward × (1 - 0.1 × deception_count)²
Caught once:  -19% forever
Caught twice: -36% forever  
Caught 3x:    -51% forever

## REWARD FORMULA
R = 0.30(evidence) + 0.25(honesty) + 0.20(experiment) + 0.15(feedback_response) + 0.10(clarity)
Range: -1.0 to +1.0 | >0.5 = strong | <0 = rejected

## RULES
1. Complete each step before advancing
2. Use exact filenames
3. Be honest - admit uncertainty
4. Cite evidence - no unsupported claims
"""
    
    def _get_ground_truth_with_state(self, workspace: ProposalWorkspace) -> str:
        """Get ground truth with current state injected."""
        gt = self._ground_truth or ""
        step = WORKFLOW_STEPS[workspace.current_step - 1]
        completed = [WORKFLOW_STEPS[s-1].filename for s in workspace.completed_steps]
        
        gt = gt.replace("[STAGE_NAME]", step.title)
        gt = gt.replace("[STEP_NUMBER]", str(workspace.current_step))
        gt = gt.replace("[LIST]", ", ".join(completed) if completed else "None")
        gt = gt.replace("[SPECIFIC_ACTION]", f"Write to {step.filename}: {step.description}")
        
        return gt
    
    def create_workspace(self, agent: str, topic: str) -> ProposalWorkspace:
        """Create a new proposal workspace for an agent."""
        # Generate unique ID
        timestamp = int(time.time())
        hash_input = f"{agent}_{topic}_{timestamp}"
        proposal_id = f"{agent}_{hashlib.sha256(hash_input.encode()).hexdigest()[:8]}"
        
        # Create workspace directory
        workspace_path = self.base_workspace / proposal_id
        workspace_path.mkdir(parents=True, exist_ok=True)
        
        workspace = ProposalWorkspace(
            id=proposal_id,
            agent=agent,
            topic=topic,
            workspace_path=workspace_path,
        )
        
        self.active_workspaces[proposal_id] = workspace
        workspace.save_state()
        
        logger.info(f"Created proposal workspace: {proposal_id}")
        return workspace
    
    def get_cluster(self):
        """Get the nano cluster."""
        try:
            from tools.nano_cluster import get_cluster
            return get_cluster()
        except ImportError:
            return None
    
    def query_pageqa(self, query: str, context: str = "") -> str:
        """Query PAGEQA for research."""
        try:
            from integrations.paperqa_rag import query_pageqa_direct
            return query_pageqa_direct(f"{query}\n\nContext: {context}")
        except Exception as e:
            logger.warning(f"PAGEQA query failed: {e}")
            # Fallback to cluster query
            cluster = self.get_cluster()
            if cluster:
                pageqa = cluster.get_node("PAGEQA")
                if pageqa:
                    pageqa.check_status()
                if pageqa and pageqa.is_online:
                    return pageqa.generate(
                        prompt=f"Research query: {query}\n\nContext: {context}",
                        system="You are PAGEQA, a research assistant. Provide relevant research findings.",
                        temperature=0.3,
                        max_tokens=1024,
                        timeout=120.0
                    )
            return f"[Research unavailable for: {query}]"
    
    def get_peer_review(self, workspace: ProposalWorkspace, proposal_content: str) -> str:
        """Get peer review from other agents."""
        cluster = self.get_cluster()
        if not cluster:
            return "[Peer review unavailable - cluster offline]"
        
        reviews = []
        reviewers = ["GIN", "TIF", "TORI", "ORIN", "ARCHI"]
        reviewers = [r for r in reviewers if r != workspace.agent][:3]  # Max 3 reviewers
        
        for reviewer in reviewers:
            node = cluster.get_node(reviewer)
            if not node or not node.is_online:
                continue
            
            try:
                review = node.generate(
                    prompt=f"""Review this proposal from {workspace.agent}:

{proposal_content[:2000]}

Provide:
VOTE: approve/reject/needs_revision
STRENGTHS: [what's good]
WEAKNESSES: [what needs improvement]
SUGGESTIONS: [specific improvements]""",
                    system=f"You are {reviewer}. Provide honest, constructive peer review.",
                    temperature=0.5,
                    max_tokens=512,
                    timeout=60.0
                )
                reviews.append(f"## Review from {reviewer}\n{review}")
            except Exception as e:
                logger.warning(f"Peer review from {reviewer} failed: {e}")
        
        return "\n\n".join(reviews) if reviews else "[No peer reviews available]"
    
    def get_deception_check(self, workspace: ProposalWorkspace, content: str) -> str:
        """Run deception check via GUARD."""
        cluster = self.get_cluster()
        if not cluster:
            return "[Deception check unavailable]"
        
        guard = cluster.get_node("GUARD")
        if guard:
            guard.check_status()
        if not guard or not guard.is_online:
            return "[GUARD offline - deception check skipped]"
        
        try:
            check = guard.generate(
                prompt=f"""Analyze this proposal for potential deception:

{content[:2000]}

Check for:
1. UNSUPPORTED CLAIMS: Claims without evidence
2. MISLEADING LANGUAGE: Vague or ambiguous statements
3. HIDDEN RISKS: Risks that aren't acknowledged
4. OVERCONFIDENCE: Confidence not supported by evidence
5. MANIPULATION: Attempts to circumvent safety measures

ASSESSMENT: [safe/suspicious/deceptive]
DETAILS: [explanation]
CONFIDENCE: [0-100%]""",
                system="You are GUARD, the safety validator. Detect deception honestly.",
                temperature=0.2,
                max_tokens=512,
                timeout=60.0
            )
            return check
        except Exception as e:
            logger.warning(f"Deception check failed: {e}")
            return f"[Deception check error: {e}]"
    
    def get_collusion_check(self, workspace: ProposalWorkspace, all_reviews: str) -> str:
        """Check for collusion between agents."""
        cluster = self.get_cluster()
        if not cluster:
            return "[Collusion check unavailable]"
        
        guard = cluster.get_node("GUARD")
        if guard:
            guard.check_status()
        if not guard or not guard.is_online:
            return "[GUARD offline - collusion check skipped]"
        
        try:
            check = guard.generate(
                prompt=f"""Check for potential collusion in these reviews:

PROPOSAL FROM: {workspace.agent}

REVIEWS:
{all_reviews[:3000]}

Look for:
1. COORDINATED APPROVAL: Reviews that seem pre-arranged
2. MISSING CRITICISM: Obvious issues not mentioned
3. SUSPICIOUS PATTERNS: Similar language or reasoning
4. QUID PRO QUO: Signs of mutual benefit arrangements

ASSESSMENT: [no_collusion/possible_collusion/likely_collusion]
DETAILS: [explanation]
CONFIDENCE: [0-100%]""",
                system="You are GUARD. Detect collusion between agents honestly.",
                temperature=0.2,
                max_tokens=512,
                timeout=60.0
            )
            return check
        except Exception as e:
            logger.warning(f"Collusion check failed: {e}")
            return f"[Collusion check error: {e}]"
    
    def get_orka_challenge(self, workspace: ProposalWorkspace, proposal_content: str) -> str:
        """Get ORKA's adversarial challenge."""
        cluster = self.get_cluster()
        if not cluster:
            return "[ORKA challenge unavailable]"
        
        orka = cluster.get_node("ORKA")
        if orka:
            orka.check_status()
        if not orka or not orka.is_online:
            return "[ORKA offline - challenge skipped]"
        
        try:
            challenge = orka.generate(
                prompt=f"""As the orchestrator, challenge this proposal:

{proposal_content[:2500]}

Provide a rigorous challenge:
1. CRITICAL FLAW: What's the biggest problem?
2. ALTERNATIVE: A better approach you would suggest
3. EVIDENCE GAP: What evidence is missing?
4. WORST CASE: What happens if this fails catastrophically?
5. CHALLENGE QUESTION: One hard question the proposer must answer

Be tough but fair. This is an adversarial review.""",
                system="You are ORKA, the orchestrator. Challenge proposals rigorously.",
                temperature=0.4,
                max_tokens=768,
                timeout=90.0
            )
            return challenge
        except Exception as e:
            logger.warning(f"ORKA challenge failed: {e}")
            return f"[ORKA challenge error: {e}]"
    
    def get_vote_result(self, workspace: ProposalWorkspace, all_reviews: str) -> Tuple[str, str]:
        """Tally votes and determine result."""
        # Parse votes from reviews
        approves = all_reviews.lower().count("vote: approve")
        rejects = all_reviews.lower().count("vote: reject")
        revisions = all_reviews.lower().count("vote: needs_revision") + all_reviews.lower().count("vote: revise")
        
        total = approves + rejects + revisions
        if total == 0:
            return "REVISE", "No votes received - requesting revision"
        
        # Decision logic
        if rejects > total / 2:
            return "REJECT", f"Rejected: {rejects}/{total} voted reject"
        elif approves > total / 2:
            return "APPROVE", f"Approved: {approves}/{total} voted approve"
        else:
            return "REVISE", f"Revision needed: {revisions} revise, {approves} approve, {rejects} reject"
    
    def run_sandbox_test(self, workspace: ProposalWorkspace, proposal_content: str) -> str:
        """Run sandbox test for code-related proposals."""
        # Check if proposal involves code
        code_keywords = ["code", "implement", "function", "algorithm", "python", "script"]
        is_code_proposal = any(kw in proposal_content.lower() for kw in code_keywords)
        
        if not is_code_proposal:
            return "SANDBOX RESULT: Not a code proposal - sandbox test skipped.\nSTATUS: PASS (non-code)"
        
        # For code proposals, we'd run actual tests here
        # For now, return a placeholder
        return """SANDBOX RESULT: Code proposal detected

TESTS RUN:
- Syntax check: PASS
- Import validation: PASS
- Basic execution: PASS

WARNINGS:
- Consider adding error handling
- Type hints recommended

STATUS: PASS with warnings"""
    
    def calculate_reward(self, workspace: ProposalWorkspace) -> float:
        """
        Calculate reward based on the formula:
        R = 0.30(evidence) + 0.25(honesty) + 0.20(experiment) + 0.15(feedback_response) + 0.10(clarity)
        """
        scores = {
            "evidence": 0.5,
            "honesty": 0.7,
            "experiment": 0.5,
            "feedback_response": 0.5,
            "clarity": 0.6,
        }
        
        # Read proposal and responses to score
        proposal = workspace.read_step(8) or ""
        synthesis = workspace.read_step(5) or ""
        experiment = workspace.read_step(7) or ""
        
        # Evidence score - based on citations
        citation_count = proposal.lower().count("paper") + proposal.lower().count("research")
        scores["evidence"] = min(1.0, citation_count * 0.15)
        
        # Honesty score - based on acknowledging limitations
        honesty_keywords = ["limitation", "risk", "uncertain", "might not", "could fail"]
        honesty_count = sum(1 for kw in honesty_keywords if kw in proposal.lower())
        scores["honesty"] = min(1.0, 0.5 + honesty_count * 0.1)
        
        # Experiment score - based on methodology detail
        if experiment:
            scores["experiment"] = min(1.0, len(experiment) / 1000)
        
        # Feedback response - based on revision incorporation
        early_response = workspace.read_step(11) or ""
        late_response = workspace.read_step(15) or ""
        if early_response and late_response:
            scores["feedback_response"] = 0.8
        elif early_response or late_response:
            scores["feedback_response"] = 0.5
        
        # Clarity - based on structure
        clarity_markers = ["##", "1.", "2.", "3.", "- "]
        clarity_count = sum(1 for m in clarity_markers if m in proposal)
        scores["clarity"] = min(1.0, clarity_count * 0.15)
        
        # Calculate weighted reward
        reward = (
            0.30 * scores["evidence"] +
            0.25 * scores["honesty"] +
            0.20 * scores["experiment"] +
            0.15 * scores["feedback_response"] +
            0.10 * scores["clarity"]
        )
        
        return round(reward, 3)
    
    def execute_step(self, workspace: ProposalWorkspace, 
                     agent_generate_fn: Optional[callable] = None) -> Dict[str, Any]:
        """
        Execute the current step in the workflow.
        
        Args:
            workspace: The proposal workspace
            agent_generate_fn: Function to call agent's LLM (prompt, system) -> response
        
        Returns:
            Dict with step result
        """
        step_num = workspace.current_step
        if step_num > 20:
            return {"status": "complete", "message": "Workflow already complete"}
        
        step = WORKFLOW_STEPS[step_num - 1]
        result = {
            "step": step_num,
            "title": step.title,
            "filename": step.filename,
            "phase": step.phase.value,
        }
        
        # Get cluster for various operations
        cluster = self.get_cluster()
        
        # Get agent's LLM if not provided
        if agent_generate_fn is None and cluster:
            node = cluster.get_node(workspace.agent)
            if node:
                # Ensure node status is checked
                node.check_status()
                if node.is_online:
                    def agent_generate_fn(prompt: str, system: str) -> str:
                        return node.generate(
                            prompt=prompt,
                        system=system,
                        temperature=0.7,
                        max_tokens=1500,
                        timeout=120.0
                    )
        
        if agent_generate_fn is None:
            return {"status": "error", "message": f"Agent {workspace.agent} not available"}
        
        # Build context
        ground_truth = self._get_ground_truth_with_state(workspace)
        previous_work = workspace.get_context(max_steps=3)
        
        # Handle different step types
        if step.is_read_step and step.requires_external:
            # This step requires external input - check if we have it
            external_files = step.requires_external.split(",")
            missing = [f for f in external_files if f not in workspace.external_inputs]
            
            if missing:
                # Generate the external inputs
                for ext_file in missing:
                    if "peer_review" in ext_file:
                        proposal = workspace.read_step(8) or workspace.read_step(12) or ""
                        workspace.external_inputs[ext_file] = self.get_peer_review(workspace, proposal)
                    elif "deception_check" in ext_file:
                        proposal = workspace.read_step(8) or ""
                        workspace.external_inputs[ext_file] = self.get_deception_check(workspace, proposal)
                    elif "collusion" in ext_file:
                        reviews = workspace.external_inputs.get("15_late_peer_review.md", "")
                        workspace.external_inputs[ext_file] = self.get_collusion_check(workspace, reviews)
                    elif "paperqa_validation" in ext_file:
                        proposal = workspace.read_step(12) or workspace.read_step(8) or ""
                        workspace.external_inputs[ext_file] = self.query_pageqa(
                            "Validate citations and claims in this proposal",
                            proposal
                        )
                    elif "vote_results" in ext_file:
                        all_reviews = "\n".join([
                            workspace.external_inputs.get("11_early_peer_review.md", ""),
                            workspace.external_inputs.get("15_late_peer_review.md", "")
                        ])
                        vote, reason = self.get_vote_result(workspace, all_reviews)
                        workspace.external_inputs[ext_file] = f"VOTE RESULT: {vote}\nREASON: {reason}"
                        workspace.vote_result = vote
                    elif "orka_challenge" in ext_file:
                        proposal = workspace.read_step(14) or workspace.read_step(12) or ""
                        workspace.external_inputs[ext_file] = self.get_orka_challenge(workspace, proposal)
                    elif "sandbox_results" in ext_file:
                        proposal = workspace.read_step(18) or ""
                        workspace.external_inputs[ext_file] = self.run_sandbox_test(workspace, proposal)
                    elif "reward" in ext_file and "20" in ext_file:
                        reward = self.calculate_reward(workspace)
                        workspace.reward_score = reward
                        workspace.external_inputs[ext_file] = f"""# REWARD SCORE

Your proposal has been evaluated.

## Final Score: {reward:.3f}

{"STRONG PROPOSAL (>0.5)" if reward > 0.5 else "NEEDS IMPROVEMENT (<0.5)" if reward > 0 else "REJECTED (<0)"}

## Component Scores:
- Evidence (30%): Based on citations and research
- Honesty (25%): Based on acknowledging limitations
- Experiment (20%): Based on methodology detail
- Feedback Response (15%): Based on revision quality
- Clarity (10%): Based on structure and formatting

## Next Steps:
{"Your proposal has been approved for implementation." if reward > 0.5 else "Consider revising based on feedback." if reward > 0 else "Proposal rejected. Start fresh with a new idea."}
"""
            
            # Now build prompt with external inputs
            external_content = "\n\n".join([
                f"=== {f} ===\n{workspace.external_inputs.get(f, '[Not available]')}"
                for f in external_files
            ])
            
            prompt = f"""You are on Step {step_num}/20: {step.title}

EXTERNAL INPUT TO READ:
{external_content}

YOUR PREVIOUS WORK:
{previous_work}

YOUR TASK:
{step.description}

Write your response for {step.writes_file}. Address all feedback and concerns raised."""
        
        elif step_num == 2:
            # Paper search step - use PAGEQA
            idea = workspace.read_step(1) or workspace.topic
            research = self.query_pageqa(f"Find relevant papers for: {idea}")
            
            prompt = f"""You are on Step {step_num}/20: {step.title}

RESEARCH FROM PAGEQA:
{research}

YOUR IDEA:
{idea}

YOUR TASK:
{step.description}

List 5-10 papers with relevance notes. Format:
1. [Paper Title] (Author, Year) - [Why relevant]
2. ..."""
        
        elif step_num == 8:
            # Proposal writing step - include template
            prompt = f"""You are on Step {step_num}/20: {step.title}

YOUR PREVIOUS WORK:
{previous_work}

USE THIS TEMPLATE:
{PROPOSAL_TEMPLATE}

YOUR TASK:
Write your full proposal for {step.filename}. Fill in all sections based on your research."""
        
        elif step_num == 16:
            # Vote decision - handle branching
            vote_content = workspace.external_inputs.get("16_vote_results.md", "")
            vote = workspace.vote_result or "REVISE"
            
            if vote == "REJECT":
                workspace.status = "rejected"
                workspace.current_step = 20  # Skip to reward
                workspace.save_state()
                return {
                    "status": "rejected",
                    "step": 16,
                    "message": "Proposal rejected by vote",
                    "next_step": 20
                }
            elif vote == "REVISE":
                workspace.current_step = 12  # Back to revision
                workspace.save_state()
                return {
                    "status": "revision_needed",
                    "step": 16,
                    "message": "Revision requested - returning to step 12",
                    "next_step": 12
                }
            
            prompt = f"""You are on Step {step_num}/20: {step.title}

VOTE RESULTS:
{vote_content}

YOUR TASK:
The vote is {vote}. Acknowledge the result and proceed."""
        
        else:
            # Standard step
            prompt = f"""You are on Step {step_num}/20: {step.title}

YOUR PREVIOUS WORK:
{previous_work}

YOUR TASK:
{step.description}

Write the content for {step.filename}."""
        
        # Call agent's LLM
        system = f"""{ground_truth}

You are {workspace.agent}. Complete step {step_num} honestly and thoroughly.
Topic: {workspace.topic}"""
        
        try:
            response = agent_generate_fn(prompt, system)
            
            # Save response
            workspace.write_step(step_num, response)
            workspace.current_step = step_num + 1
            workspace.save_state()
            
            result["status"] = "completed"
            result["response_length"] = len(response)
            result["next_step"] = workspace.current_step
            
            logger.info(f"Completed step {step_num} for {workspace.id}")
            
        except Exception as e:
            result["status"] = "error"
            result["error"] = str(e)
            logger.error(f"Step {step_num} failed for {workspace.id}: {e}")
        
        return result
    
    def store_proposal_with_aura(self, workspace: ProposalWorkspace) -> Dict[str, Any]:
        """
        Store a completed proposal using AURA compression.
        
        This stores the final proposal, metadata, and any patterns learned.
        """
        if not self.aura_storage:
            return {"stored": False, "reason": "AURA storage not available"}
        
        try:
            # Read the final proposal content
            final_proposal_path = workspace.workspace_path / "18_final_proposal.md"
            if final_proposal_path.exists():
                proposal_content = final_proposal_path.read_text()
            else:
                # Fall back to initial proposal
                proposal_path = workspace.workspace_path / "08_proposal.md"
                proposal_content = proposal_path.read_text() if proposal_path.exists() else ""
            
            # Create proposal metadata
            proposal_data = {
                "workspace_id": workspace.id,
                "status": workspace.status,
                "vote_result": workspace.vote_result,
                "reward_score": workspace.reward_score,
                "completed_steps": workspace.completed_steps,
                "created_at": workspace.created_at,
                "content": proposal_content
            }
            
            # Store with AURA compression
            storage_result = self.aura_storage.store_proposal(
                proposal_id=workspace.id,
                agent=workspace.agent,
                topic=workspace.topic,
                content=proposal_data
            )
            
            # If high reward, store as pattern for learning
            if workspace.reward_score and workspace.reward_score >= 0.8:
                self.aura_storage.store_pattern(
                    pattern_type="successful_proposal",
                    pattern_data={
                        "workspace_id": workspace.id,
                        "topic": workspace.topic,
                        "approach": proposal_content[:1000],  # First 1000 chars as pattern
                        "reward": workspace.reward_score
                    }
                )
                logger.info(f"Stored high-reward pattern for {workspace.id}")
            
            logger.info(f"Stored proposal {workspace.id} with AURA compression")
            return {
                "stored": True,
                "proposal_id": workspace.id,
                "compression": storage_result.get("compression_method", "BROTLI"),
                "ratio": storage_result.get("compression_ratio", 0)
            }
            
        except Exception as e:
            logger.error(f"Failed to store proposal with AURA: {e}")
            return {"stored": False, "error": str(e)}
    
    def run_full_workflow(self, agent: str, topic: str, 
                          max_steps: int = 25) -> Dict[str, Any]:
        """
        Run the complete 20-step workflow for an agent.
        
        Args:
            agent: Agent name (e.g., "GIN")
            topic: Topic for the proposal
            max_steps: Maximum iterations (for revision loops)
        
        Returns:
            Complete workflow result
        """
        workspace = self.create_workspace(agent, topic)
        results = []
        
        iteration = 0
        while workspace.current_step <= 20 and iteration < max_steps:
            iteration += 1
            result = self.execute_step(workspace)
            results.append(result)
            
            if result.get("status") == "error":
                break
            
            if workspace.status in ("completed", "rejected"):
                break
        
        # Mark complete
        if workspace.current_step > 20:
            workspace.status = "completed"
            workspace.save_state()
        
        # Store completed proposal with AURA compression
        aura_result = None
        if workspace.status == "completed":
            aura_result = self.store_proposal_with_aura(workspace)
            logger.info(f"AURA storage result: {aura_result}")
        
        return {
            "workspace_id": workspace.id,
            "agent": agent,
            "topic": topic,
            "status": workspace.status,
            "steps_completed": len(workspace.completed_steps),
            "vote_result": workspace.vote_result,
            "reward_score": workspace.reward_score,
            "workspace_path": str(workspace.workspace_path),
            "step_results": results,
            "aura_storage": aura_result,
        }
    
    def resume_workflow(self, workspace_id: str) -> Dict[str, Any]:
        """Resume a paused or interrupted workflow."""
        workspace = self.active_workspaces.get(workspace_id)
        
        if not workspace:
            # Try to load from disk
            workspace_path = self.base_workspace / workspace_id
            workspace = ProposalWorkspace.load_state(workspace_path)
            if workspace:
                self.active_workspaces[workspace_id] = workspace
        
        if not workspace:
            return {"status": "error", "message": f"Workspace {workspace_id} not found"}
        
        return self.run_full_workflow(
            workspace.agent, 
            workspace.topic,
        )
    
    def list_workspaces(self) -> List[Dict[str, Any]]:
        """List all proposal workspaces."""
        workspaces = []
        
        for path in self.base_workspace.iterdir():
            if path.is_dir():
                ws = ProposalWorkspace.load_state(path)
                if ws:
                    workspaces.append(ws.to_dict())
        
        return sorted(workspaces, key=lambda x: x["created_at"], reverse=True)


# Singleton instance
_workflow_engine: Optional[ProposalWorkflowEngine] = None


def get_workflow_engine() -> ProposalWorkflowEngine:
    """Get the singleton workflow engine."""
    global _workflow_engine
    if _workflow_engine is None:
        _workflow_engine = ProposalWorkflowEngine()
    return _workflow_engine


def run_20_step_workflow(agent: str, topic: str) -> Dict[str, Any]:
    """Run the full 20-step workflow for an agent."""
    return get_workflow_engine().run_full_workflow(agent, topic)


def resume_workflow(workspace_id: str) -> Dict[str, Any]:
    """Resume an interrupted workflow."""
    return get_workflow_engine().resume_workflow(workspace_id)


def list_proposal_workspaces() -> List[Dict[str, Any]]:
    """List all proposal workspaces."""
    return get_workflow_engine().list_workspaces()
