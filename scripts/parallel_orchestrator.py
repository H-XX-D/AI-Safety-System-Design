#!/usr/bin/env python3
"""
Parallel Proposal Orchestrator (ORKA-Managed)
==============================================

Runs all 6 researchers in parallel, with ORKA orchestrating:
- Parallel execution of independent steps (1-10)
- Context save/restore for peer review scheduling
- Fair scheduling based on completion order
- Human approval in terminal

The workflow splits into phases:

PHASE A: Independent Work (Steps 1-10) - All researchers in parallel
  - Each researcher works on their own proposal
  - No interaction needed between researchers
  - Context saved when reaching step 11

PHASE B: Peer Review Rounds (Steps 11-17) - Sequential per presenter
  - ORKA schedules based on who finished Phase A first
  - Presenter's context loaded, peers provide reviews
  - Context switching managed by ORKA

PHASE C: Finalization (Steps 18-20) - Sequential per presenter
  - Sandbox testing
  - Human approval (interactive terminal)
  - Deployment decision

Usage:
  python parallel_orchestrator.py                # All 6 researchers
  python parallel_orchestrator.py GIN ORIN      # Specific researchers
"""

import os
import sys
import json
import time
import queue
import pickle
import threading
from pathlib import Path
from datetime import datetime
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Any, Tuple
from concurrent.futures import ThreadPoolExecutor, as_completed
import fcntl

# Add scripts directory to path
_scripts_dir = Path(__file__).parent
if str(_scripts_dir) not in sys.path:
    sys.path.insert(0, str(_scripts_dir))

# Import from the main workflow
from run_20step import (
    RESEARCHERS, call_llm, PAGEQA, ORKA, GUARD,
    run_sandbox_test
)
from secure_config import get_config
from structured_logging import get_logger

# Unpack node tuples
PAGEQA_URL, PAGEQA_MODEL = PAGEQA
ORKA_URL, ORKA_MODEL = ORKA
GUARD_URL, GUARD_MODEL = GUARD

CONFIG = get_config()
logger = get_logger()

# ============================================================
# CONFIGURATION
# ============================================================

RESEARCHER_NODES = ["GIN", "ORIN", "TIF", "TORI", "ARCHI", "THEO", "NOVEL"]
CONTEXT_DIR = Path("data/parallel_contexts")
RESULTS_DIR = Path("data/parallel_results")

# Steps that can run in parallel (no peer interaction)
INDEPENDENT_STEPS = list(range(1, 11))  # Steps 1-10

# Steps requiring peer review (sequential by presenter)
PEER_REVIEW_STEPS = list(range(11, 18))  # Steps 11-17

# Final steps (sandbox, human approval, deployment)
FINAL_STEPS = list(range(18, 21))  # Steps 18-20


# ============================================================
# CONTEXT MANAGEMENT
# ============================================================

@dataclass
class ProposalContext:
    """Saved state for a researcher's proposal."""
    proposer: str
    workspace: Path
    current_step: int = 0
    improvement_type: str = ""
    improvement_code: str = ""
    proposal: str = ""
    votes: Dict[str, int] = field(default_factory=lambda: {"approve": 0, "reject": 0, "revise": 0})
    peer_reviewers: List[str] = field(default_factory=list)
    
    # Accumulated content from each step
    step_outputs: Dict[int, str] = field(default_factory=dict)
    
    # Timing
    started_at: float = field(default_factory=time.time)
    phase_a_completed_at: Optional[float] = None
    completed_at: Optional[float] = None
    
    # Results
    sandbox_passed: bool = False
    final_vote: str = ""
    reward: float = 0.0
    deployed: bool = False
    error: Optional[str] = None
    
    def save(self, path: Path = None):
        """Save context to disk."""
        if path is None:
            path = CONTEXT_DIR / f"{self.proposer}_context.pkl"
        path.parent.mkdir(parents=True, exist_ok=True)
        with open(path, "wb") as f:
            pickle.dump(self, f)
    
    @classmethod
    def load(cls, proposer: str) -> Optional["ProposalContext"]:
        """Load context from disk."""
        path = CONTEXT_DIR / f"{proposer}_context.pkl"
        if path.exists():
            with open(path, "rb") as f:
                return pickle.load(f)
        return None


# ============================================================
# ORKA SCHEDULER
# ============================================================

class OrkaScheduler:
    """
    ORKA manages the scheduling of peer reviews.
    
    - Tracks which researchers finished Phase A
    - Schedules peer reviews in completion order (FIFO)
    - Manages context switching
    """
    
    def __init__(self, researchers: List[str]):
        self.researchers = researchers
        self.completion_queue = queue.Queue()  # FIFO for Phase A completions
        self.lock = threading.Lock()
        
        # Track states
        self.phase_a_complete: Dict[str, bool] = {r: False for r in researchers}
        self.phase_b_complete: Dict[str, bool] = {r: False for r in researchers}
        self.phase_c_complete: Dict[str, bool] = {r: False for r in researchers}
        
        # Contexts
        self.contexts: Dict[str, ProposalContext] = {}
        
        # Currently being reviewed
        self.current_presenter: Optional[str] = None
        
    def register_phase_a_complete(self, proposer: str, context: ProposalContext):
        """Called when a researcher finishes steps 1-10."""
        with self.lock:
            self.phase_a_complete[proposer] = True
            self.contexts[proposer] = context
            context.phase_a_completed_at = time.time()
            context.save()
            self.completion_queue.put(proposer)
            print(f"\n📋 ORKA: {proposer} finished Phase A (independent work)")
            print(f"   Queue position: {self.completion_queue.qsize()}")
    
    def get_next_for_review(self) -> Optional[str]:
        """Get the next researcher for peer review (FIFO order)."""
        try:
            proposer = self.completion_queue.get_nowait()
            with self.lock:
                self.current_presenter = proposer
            return proposer
        except queue.Empty:
            return None
    
    def mark_phase_b_complete(self, proposer: str):
        """Called when peer review is done for a researcher."""
        with self.lock:
            self.phase_b_complete[proposer] = True
            self.current_presenter = None
    
    def mark_phase_c_complete(self, proposer: str, context: ProposalContext):
        """Called when final steps are done."""
        with self.lock:
            self.phase_c_complete[proposer] = True
            self.contexts[proposer] = context
            context.completed_at = time.time()
            context.save()
    
    def all_complete(self) -> bool:
        """Check if all researchers have completed all phases."""
        return all(self.phase_c_complete.values())
    
    def get_available_reviewers(self, proposer: str) -> List[str]:
        """Get researchers available to review (not the proposer)."""
        return [r for r in self.researchers if r != proposer]


# ============================================================
# PHASE EXECUTORS
# ============================================================

def run_phase_a(proposer: str, scheduler: OrkaScheduler) -> ProposalContext:
    """
    Run Phase A: Independent work (Steps 1-10).
    
    This runs in a thread, parallel with other researchers.
    """
    print(f"\n{'='*60}")
    print(f"[{proposer}] Starting Phase A: Independent Work")
    print(f"{'='*60}")
    
    # Create workspace
    timestamp = int(time.time())
    workspace = Path(f"data/improvements/{proposer}_parallel_{timestamp}")
    workspace.mkdir(parents=True, exist_ok=True)
    
    # Initialize context
    ctx = ProposalContext(
        proposer=proposer,
        workspace=workspace,
        peer_reviewers=scheduler.get_available_reviewers(proposer)
    )
    
    proposer_url, proposer_model = RESEARCHERS[proposer]
    
    try:
        # STEP 1: IDEA
        print(f"[{proposer}] Step 1: Generating improvement idea...")
        idea_prompt = """You are improving an AI inference system. Identify ONE specific improvement.

Categories: prompt_template, inference_params, chain_of_thought, tool_calling, error_handling, memory_management

Format:
- **category**: <one from above>
- **problem**: <what's wrong>
- **solution**: <how to fix>"""
        
        idea = call_llm(proposer_url, proposer_model, idea_prompt,
                       "Be concise. Focus on practical improvements.",
                       temperature=0.7, max_tokens=300)
        ctx.step_outputs[1] = idea
        (workspace / "01_idea.md").write_text(f"# Step 1: Idea\n\n{idea}")
        
        # Detect category
        idea_lower = idea.lower()
        for cat in ["prompt_template", "inference_params", "chain_of_thought", 
                    "tool_calling", "error_handling", "memory_management"]:
            if cat.replace("_", " ") in idea_lower or cat in idea_lower:
                ctx.improvement_type = cat
                break
        if not ctx.improvement_type:
            ctx.improvement_type = "prompt_template"
        
        print(f"[{proposer}] Step 1: Category detected: {ctx.improvement_type}")
        
        # STEP 2: PAPERS (via PAGEQA)
        print(f"[{proposer}] Step 2: Literature search...")
        papers_prompt = f"Find 3 papers about: {ctx.improvement_type} improvements for LLM inference"
        papers = call_llm(PAGEQA_URL, PAGEQA_MODEL, papers_prompt,
                         "Search academic literature.", temperature=0.3, max_tokens=600)
        ctx.step_outputs[2] = papers
        (workspace / "02_papers.md").write_text(f"# Step 2: Papers\n\n{papers}")
        print(f"[{proposer}] Step 2: Found papers ({len(papers)} chars)")
        
        # STEP 3: TRIAGE
        print(f"[{proposer}] Step 3: Triaging papers...")
        triage_prompt = f"Rate these papers for {ctx.improvement_type}:\n{papers[:800]}\n\nRank 1-5 and summarize key points."
        triage = call_llm(proposer_url, proposer_model, triage_prompt,
                         "Be critical. Focus on practical value.",
                         temperature=0.4, max_tokens=400)
        ctx.step_outputs[3] = triage
        (workspace / "03_triage.md").write_text(f"# Step 3: Triage\n\n{triage}")
        print(f"[{proposer}] Step 3: Triage complete ({len(triage)} chars)")
        
        # STEP 4: DEEP NOTES
        print(f"[{proposer}] Step 4: Deep notes...")
        notes_prompt = f"Extract key findings from:\n{triage[:600]}\n\nWhat can we apply to {ctx.improvement_type}?"
        notes = call_llm(proposer_url, proposer_model, notes_prompt,
                        "Extract actionable insights.",
                        temperature=0.4, max_tokens=500)
        ctx.step_outputs[4] = notes
        (workspace / "04_deep_notes.md").write_text(f"# Step 4: Deep Notes\n\n{notes}")
        print(f"[{proposer}] Step 4: Notes ({len(notes)} chars)")
        
        # STEP 5: SYNTHESIS
        print(f"[{proposer}] Step 5: Synthesis...")
        synthesis_prompt = f"""Based on research:
{notes[:500]}

Identify the gap between current practice and ideal implementation for {ctx.improvement_type}."""
        synthesis = call_llm(proposer_url, proposer_model, synthesis_prompt,
                            "Identify actionable gap.",
                            temperature=0.4, max_tokens=400)
        ctx.step_outputs[5] = synthesis
        (workspace / "05_synthesis.md").write_text(f"# Step 5: Synthesis\n\n{synthesis}")
        print(f"[{proposer}] Step 5: Synthesis ({len(synthesis)} chars)")
        
        # STEP 6: HYPOTHESIS
        print(f"[{proposer}] Step 6: Hypothesis...")
        hypothesis_prompt = f"""Based on gap analysis:
{synthesis[:400]}

Create a testable hypothesis for improving {ctx.improvement_type}."""
        hypothesis = call_llm(proposer_url, proposer_model, hypothesis_prompt,
                             "Make it specific and testable.",
                             temperature=0.5, max_tokens=400)
        ctx.step_outputs[6] = hypothesis
        (workspace / "06_hypothesis.md").write_text(f"# Step 6: Hypothesis\n\n{hypothesis}")
        print(f"[{proposer}] Step 6: Hypothesis generated")
        
        # STEP 7: EXPERIMENT DESIGN
        print(f"[{proposer}] Step 7: Experiment design...")
        experiment_prompt = f"""Design an experiment to test:
{hypothesis[:300]}

Include CODE or MATH to validate the improvement."""
        experiment = call_llm(proposer_url, proposer_model, experiment_prompt,
                             "Include concrete code or metrics.",
                             temperature=0.5, max_tokens=600)
        ctx.step_outputs[7] = experiment
        (workspace / "07_experiment.md").write_text(f"# Step 7: Experiment\n\n{experiment}")
        print(f"[{proposer}] Step 7: Experiment design ({len(experiment)} chars)")
        
        # STEP 8: FULL PROPOSAL
        print(f"[{proposer}] Step 8: Writing full proposal...")
        proposal_prompt = f"""Write a complete proposal for {ctx.improvement_type} improvement.

Research: {synthesis[:300]}
Hypothesis: {hypothesis[:200]}
Experiment: {experiment[:300]}

Include:
1. Problem statement
2. Proposed solution (with CODE)
3. Expected benefits
4. Implementation plan"""
        proposal = call_llm(proposer_url, proposer_model, proposal_prompt,
                           "Be thorough but concise.",
                           temperature=0.5, max_tokens=800)
        ctx.proposal = proposal
        ctx.step_outputs[8] = proposal
        (workspace / "08_proposal.md").write_text(f"# Step 8: Proposal\n\n{proposal}")
        print(f"[{proposer}] Step 8: Proposal ({len(proposal)} chars)")
        
        # Extract code from proposal
        code_lines = []
        in_code = False
        for line in proposal.split("\n"):
            if "```" in line and not in_code:
                in_code = True
            elif "```" in line and in_code:
                in_code = False
            elif in_code:
                code_lines.append(line)
        ctx.improvement_code = "\n".join(code_lines) if code_lines else proposal[:500]
        
        # STEP 9: SELF-CHECK CONSISTENCY
        print(f"[{proposer}] Step 9: Self-check consistency...")
        consistency_prompt = f"""Review your proposal for internal consistency:
{proposal[:500]}

Check:
1. Does the solution match the problem?
2. Is the code correct?
3. Are claims supported?"""
        consistency = call_llm(proposer_url, proposer_model, consistency_prompt,
                              "Be self-critical.",
                              temperature=0.4, max_tokens=400)
        ctx.step_outputs[9] = consistency
        (workspace / "09_self_check_consistency.md").write_text(f"# Step 9: Consistency\n\n{consistency}")
        print(f"[{proposer}] Step 9: Consistency check complete")
        
        # STEP 10: SELF-CHECK WEAKNESSES
        print(f"[{proposer}] Step 10: Self-check weaknesses...")
        weakness_prompt = f"""Identify weaknesses in your proposal:
{proposal[:500]}

Be honest about:
1. Limitations
2. Edge cases
3. What could go wrong"""
        weaknesses = call_llm(proposer_url, proposer_model, weakness_prompt,
                             "Be brutally honest.",
                             temperature=0.4, max_tokens=400)
        ctx.step_outputs[10] = weaknesses
        (workspace / "10_self_check_weaknesses.md").write_text(f"# Step 10: Weaknesses\n\n{weaknesses}")
        print(f"[{proposer}] Step 10: Weaknesses identified")
        
        ctx.current_step = 10
        
        # Register completion with scheduler
        scheduler.register_phase_a_complete(proposer, ctx)
        
        print(f"\n✅ [{proposer}] Phase A COMPLETE - Waiting for peer review scheduling")
        
    except Exception as e:
        ctx.error = str(e)
        print(f"\n❌ [{proposer}] Phase A FAILED: {e}")
        logger.error("phase_a_failed", extra={"proposer": proposer, "error": str(e)})
    
    return ctx


def run_phase_b(proposer: str, ctx: ProposalContext, scheduler: OrkaScheduler) -> ProposalContext:
    """
    Run Phase B: Peer Review (Steps 11-17).
    
    This runs sequentially, managed by ORKA.
    """
    print(f"\n{'='*60}")
    print(f"[{proposer}] Starting Phase B: Peer Review")
    print(f"{'='*60}")
    
    proposer_url, proposer_model = RESEARCHERS[proposer]
    workspace = ctx.workspace
    
    try:
        # STEP 11: EARLY PEER REVIEW
        print(f"\n[{proposer}] Step 11: Collecting peer reviews...")
        print(f"[{proposer}] Reviewers: {', '.join(ctx.peer_reviewers)}")
        
        review_prompt = f"""Review this improvement proposal from {proposer}:

CATEGORY: {ctx.improvement_type}
PROPOSAL SUMMARY: {ctx.proposal[:400]}
CODE: {ctx.improvement_code[:300]}

Evaluate:
1. Will this improve the system?
2. Is the code correct and safe?
3. Any risks or edge cases?

VOTE: approve / reject / revise
FEEDBACK: <brief explanation>"""

        all_reviews = []
        for reviewer in ctx.peer_reviewers:
            print(f"  [{reviewer}] Reviewing {proposer}...", end=" ", flush=True)
            url, model = RESEARCHERS[reviewer]
            
            # Clear role: reviewer is ONLY reviewing, not proposing
            review = call_llm(url, model, review_prompt,
                             f"You are {reviewer}, acting as a peer reviewer. Your ONLY task is to evaluate {proposer}'s proposal. Give honest technical feedback.",
                             temperature=0.4, max_tokens=400, timeout=120)
            
            if review and not review.startswith("[Error"):
                all_reviews.append(f"## {reviewer}\n{review}\n")
                print("OK")
                
                review_lower = review.lower()
                if "reject" in review_lower:
                    ctx.votes["reject"] += 1
                elif "revise" in review_lower:
                    ctx.votes["revise"] += 1
                else:
                    ctx.votes["approve"] += 1
            else:
                all_reviews.append(f"## {reviewer}\n[No response]\n")
                ctx.votes["revise"] += 1
                print("FAILED")
        
        early_reviews = "\n".join(all_reviews)
        early_reviews += f"\n## VOTE TALLY\nApprove: {ctx.votes['approve']}, Reject: {ctx.votes['reject']}, Revise: {ctx.votes['revise']}"
        ctx.step_outputs[11] = early_reviews
        (workspace / "11_early_peer_review.md").write_text(f"# Step 11: Early Peer Review\n\n{early_reviews}")
        print(f"\n[{proposer}] Early votes: Approve={ctx.votes['approve']}, Reject={ctx.votes['reject']}, Revise={ctx.votes['revise']}")
        
        # STEP 12: REVISION
        print(f"\n[{proposer}] Step 12: Revising based on feedback...")
        revision_prompt = f"""Your proposal received feedback:
{early_reviews[:600]}

Revise your proposal to address the concerns.
Original code: {ctx.improvement_code[:300]}

Provide revised code if needed."""
        revision = call_llm(proposer_url, proposer_model, revision_prompt,
                           "Address the feedback constructively.",
                           temperature=0.5, max_tokens=500)
        ctx.step_outputs[12] = revision
        (workspace / "12_revision.md").write_text(f"# Step 12: Revision\n\n{revision}")
        print(f"[{proposer}] Step 12: Revision complete")
        
        # STEP 13: PAGEQA VALIDATION
        print(f"\n[{proposer}] Step 13: PAGEQA validation...")
        validation_prompt = f"""Validate this technical proposal:

Category: {ctx.improvement_type}
Proposal: {ctx.proposal[:400]}
Revision: {revision[:300]}

Check:
1. Technical accuracy
2. Citation validity
3. Implementation feasibility"""
        validation = call_llm(PAGEQA_URL, PAGEQA_MODEL, validation_prompt,
                             "Verify technical claims.",
                             temperature=0.3, max_tokens=500)
        ctx.step_outputs[13] = validation
        (workspace / "13_pageqa_validation.md").write_text(f"# Step 13: PAGEQA Validation\n\n{validation}")
        print(f"[{proposer}] Step 13: Validation complete")
        
        # STEP 14: VALIDATED PROPOSAL
        print(f"\n[{proposer}] Step 14: Creating validated proposal...")
        validated_prompt = f"""Incorporate validation feedback:
{validation[:400]}

Create final validated version of:
{ctx.proposal[:400]}"""
        validated = call_llm(proposer_url, proposer_model, validated_prompt,
                            "Address any validation issues.",
                            temperature=0.4, max_tokens=500)
        ctx.step_outputs[14] = validated
        ctx.proposal = validated  # Update proposal
        (workspace / "14_validated_proposal.md").write_text(f"# Step 14: Validated Proposal\n\n{validated}")
        print(f"[{proposer}] Step 14: Validated proposal complete")
        
        # STEP 15: LATE PEER REVIEW
        print(f"\n[{proposer}] Step 15: Late peer review...")
        late_review_prompt = f"""Final review of validated proposal from {proposer}:

{validated[:500]}

FINAL VOTE: approve / reject
REASONING: <why>"""

        late_votes = {"approve": 0, "reject": 0}
        late_reviews = []
        for reviewer in ctx.peer_reviewers:
            print(f"  [{reviewer}] Final review...", end=" ", flush=True)
            url, model = RESEARCHERS[reviewer]
            
            review = call_llm(url, model, late_review_prompt,
                             f"You are {reviewer}. Final decision.",
                             temperature=0.3, max_tokens=300, timeout=120)
            
            if review and not review.startswith("[Error"):
                late_reviews.append(f"## {reviewer}\n{review}\n")
                print("OK")
                if "reject" in review.lower():
                    late_votes["reject"] += 1
                else:
                    late_votes["approve"] += 1
            else:
                late_reviews.append(f"## {reviewer}\n[No response]\n")
                late_votes["reject"] += 1
                print("FAILED")
        
        late_review_text = "\n".join(late_reviews)
        late_review_text += f"\n## FINAL VOTES\nApprove: {late_votes['approve']}, Reject: {late_votes['reject']}"
        ctx.step_outputs[15] = late_review_text
        (workspace / "15_late_peer_review.md").write_text(f"# Step 15: Late Peer Review\n\n{late_review_text}")
        print(f"\n[{proposer}] Final votes: Approve={late_votes['approve']}, Reject={late_votes['reject']}")
        
        # STEP 16: VOTE DECISION
        print(f"\n[{proposer}] Step 16: Vote decision...")
        if late_votes["approve"] > late_votes["reject"]:
            ctx.final_vote = "APPROVE"
            print(f"[{proposer}] VOTE: ✅ APPROVE")
        else:
            ctx.final_vote = "REJECT"
            print(f"[{proposer}] VOTE: ❌ REJECT")
        ctx.step_outputs[16] = f"VOTE: {ctx.final_vote}"
        (workspace / "16_vote_decision.md").write_text(f"# Step 16: Vote\n\nFinal Vote: {ctx.final_vote}")
        
        # STEP 17: ORKA CHALLENGE
        print(f"\n[{proposer}] Step 17: ORKA challenge...")
        challenge_prompt = f"""You are the ORKA orchestrator. Challenge this proposal:

Proposer: {proposer}
Category: {ctx.improvement_type}
Proposal: {ctx.proposal[:400]}
Vote: {ctx.final_vote}

Play devil's advocate. Find weaknesses."""
        challenge = call_llm(ORKA_URL, ORKA_MODEL, challenge_prompt,
                            "Be challenging but fair.",
                            temperature=0.5, max_tokens=400)
        
        defense_prompt = f"""ORKA challenged your proposal:
{challenge[:400]}

Defend your proposal."""
        defense = call_llm(proposer_url, proposer_model, defense_prompt,
                          "Defend with evidence.",
                          temperature=0.5, max_tokens=400)
        ctx.step_outputs[17] = f"CHALLENGE:\n{challenge}\n\nDEFENSE:\n{defense}"
        (workspace / "17_orka_challenge.md").write_text(f"# Step 17: ORKA Challenge\n\n## Challenge\n{challenge}\n\n## Defense\n{defense}")
        print(f"[{proposer}] Step 17: Challenge/defense complete")
        
        ctx.current_step = 17
        scheduler.mark_phase_b_complete(proposer)
        print(f"\n✅ [{proposer}] Phase B COMPLETE")
        
    except Exception as e:
        ctx.error = str(e)
        print(f"\n❌ [{proposer}] Phase B FAILED: {e}")
        logger.error("phase_b_failed", extra={"proposer": proposer, "error": str(e)})
    
    return ctx


def run_phase_c(proposer: str, ctx: ProposalContext, scheduler: OrkaScheduler) -> ProposalContext:
    """
    Run Phase C: Finalization (Steps 18-20).
    
    Includes interactive human approval.
    """
    print(f"\n{'='*60}")
    print(f"[{proposer}] Starting Phase C: Finalization")
    print(f"{'='*60}")
    
    proposer_url, proposer_model = RESEARCHERS[proposer]
    workspace = ctx.workspace
    
    try:
        # STEP 18: FINAL PROPOSAL
        print(f"\n[{proposer}] Step 18: Creating final proposal...")
        final_prompt = f"""Create the final, deployment-ready version of your proposal.

Category: {ctx.improvement_type}
Vote: {ctx.final_vote}
Validated proposal: {ctx.proposal[:500]}

Format as ready-to-deploy code/configuration."""
        final_proposal = call_llm(proposer_url, proposer_model, final_prompt,
                                 "Create clean, deployable output.",
                                 temperature=0.3, max_tokens=600)
        ctx.step_outputs[18] = final_proposal
        (workspace / "18_final_proposal.md").write_text(f"# Step 18: Final Proposal\n\n{final_proposal}")
        print(f"[{proposer}] Step 18: Final proposal complete")
        
        # STEP 19: SANDBOX TEST
        print(f"\n[{proposer}] Step 19: Sandbox testing...")
        sandbox_result = run_sandbox_test(
            ctx.improvement_code, ctx.improvement_type, workspace
        )
        ctx.sandbox_passed = sandbox_result.get("passed", False)
        ctx.step_outputs[19] = json.dumps(sandbox_result, indent=2)
        (workspace / "19_sandbox_test.md").write_text(f"# Step 19: Sandbox Test\n\n```json\n{json.dumps(sandbox_result, indent=2)}\n```")
        
        if ctx.sandbox_passed:
            print(f"[{proposer}] Step 19: ✅ Sandbox PASSED")
        else:
            print(f"[{proposer}] Step 19: ❌ Sandbox FAILED")
        
        # STEP 20: HIDDEN EVAL + HUMAN APPROVAL + DEPLOYMENT
        print(f"\n[{proposer}] Step 20: Final evaluation and deployment...")
        
        # Calculate reward (simplified)
        ctx.reward = 0.0
        if ctx.final_vote == "APPROVE":
            ctx.reward += 0.5
        if ctx.sandbox_passed:
            ctx.reward += 0.3
        if ctx.votes["approve"] > ctx.votes["reject"]:
            ctx.reward += 0.2
        
        # HUMAN APPROVAL (Interactive)
        print(f"\n{'='*60}")
        print(f"🔐 HUMAN APPROVAL REQUIRED FOR: {proposer}")
        print(f"{'='*60}")
        print(f"Category: {ctx.improvement_type}")
        print(f"Final Vote: {ctx.final_vote}")
        print(f"Sandbox: {'PASSED' if ctx.sandbox_passed else 'FAILED'}")
        print(f"Reward: {ctx.reward:.2f}")
        print(f"\nProposal Preview:")
        print("-" * 40)
        print(final_proposal[:500])
        print("-" * 40)
        print(f"\nWorkspace: {workspace}")
        print()
        
        while True:
            try:
                response = input(f"Deploy {proposer}'s proposal? (yes/no/skip): ").strip().lower()
                if response in ["yes", "y"]:
                    ctx.deployed = True
                    print(f"✅ {proposer}: Deployment APPROVED by human")
                    break
                elif response in ["no", "n"]:
                    ctx.deployed = False
                    print(f"❌ {proposer}: Deployment REJECTED by human")
                    break
                elif response in ["skip", "s"]:
                    ctx.deployed = False
                    print(f"⏭️  {proposer}: Deployment SKIPPED")
                    break
                else:
                    print("Please enter 'yes', 'no', or 'skip'")
            except EOFError:
                print(f"\n⚠️  {proposer}: No terminal input - skipping deployment")
                ctx.deployed = False
                break
        
        ctx.step_outputs[20] = f"Reward: {ctx.reward}, Deployed: {ctx.deployed}"
        (workspace / "20_deployment.md").write_text(
            f"# Step 20: Deployment\n\n"
            f"- Vote: {ctx.final_vote}\n"
            f"- Sandbox: {'PASSED' if ctx.sandbox_passed else 'FAILED'}\n"
            f"- Reward: {ctx.reward:.2f}\n"
            f"- Deployed: {ctx.deployed}\n"
        )
        
        ctx.current_step = 20
        scheduler.mark_phase_c_complete(proposer, ctx)
        
        print(f"\n✅ [{proposer}] Phase C COMPLETE - All 20 steps done!")
        
    except Exception as e:
        ctx.error = str(e)
        print(f"\n❌ [{proposer}] Phase C FAILED: {e}")
        logger.error("phase_c_failed", extra={"proposer": proposer, "error": str(e)})
    
    return ctx


# ============================================================
# MAIN ORCHESTRATOR
# ============================================================

def run_parallel_orchestrator(researchers: List[str] = None):
    """
    Main orchestrator function.
    
    1. Run all researchers through Phase A in parallel
    2. As they complete, queue for Phase B (peer review)
    3. Run Phase B sequentially (ORKA-managed)
    4. Run Phase C with human approval
    """
    researchers = researchers or RESEARCHER_NODES
    
    print("\n" + "#" * 60)
    print("ORKASTRATOR PARALLEL PROPOSAL SYSTEM")
    print("#" * 60)
    print(f"Researchers: {', '.join(researchers)}")
    print(f"Start time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print()
    
    # Create directories
    CONTEXT_DIR.mkdir(parents=True, exist_ok=True)
    RESULTS_DIR.mkdir(parents=True, exist_ok=True)
    
    # Initialize scheduler
    scheduler = OrkaScheduler(researchers)
    
    # ========================================
    # PHASE A: Parallel Independent Work
    # ========================================
    print("\n" + "=" * 60)
    print("PHASE A: Independent Work (Steps 1-10) - PARALLEL")
    print("=" * 60)
    
    phase_a_contexts = {}
    with ThreadPoolExecutor(max_workers=len(researchers)) as executor:
        futures = {
            executor.submit(run_phase_a, r, scheduler): r
            for r in researchers
        }
        
        for future in as_completed(futures):
            proposer = futures[future]
            try:
                ctx = future.result()
                phase_a_contexts[proposer] = ctx
            except Exception as e:
                print(f"❌ [{proposer}] Phase A exception: {e}")
    
    print("\n" + "=" * 60)
    print("PHASE A COMPLETE - All researchers finished independent work")
    print("=" * 60)
    
    # ========================================
    # PHASE B: Sequential Peer Reviews
    # ========================================
    print("\n" + "=" * 60)
    print("PHASE B: Peer Review (Steps 11-17) - SEQUENTIAL BY COMPLETION ORDER")
    print("=" * 60)
    
    phase_b_order = []
    while not all(scheduler.phase_b_complete.values()):
        proposer = scheduler.get_next_for_review()
        if proposer:
            phase_b_order.append(proposer)
            ctx = scheduler.contexts.get(proposer, phase_a_contexts.get(proposer))
            if ctx and not ctx.error:
                ctx = run_phase_b(proposer, ctx, scheduler)
                scheduler.contexts[proposer] = ctx
            else:
                scheduler.mark_phase_b_complete(proposer)
        else:
            time.sleep(0.5)
    
    print(f"\nPhase B completion order: {' → '.join(phase_b_order)}")
    
    # ========================================
    # PHASE C: Finalization with Human Approval
    # ========================================
    print("\n" + "=" * 60)
    print("PHASE C: Finalization (Steps 18-20) - WITH HUMAN APPROVAL")
    print("=" * 60)
    
    for proposer in phase_b_order:
        ctx = scheduler.contexts.get(proposer)
        if ctx and not ctx.error and ctx.final_vote == "APPROVE":
            ctx = run_phase_c(proposer, ctx, scheduler)
        elif ctx:
            print(f"\n⏭️  [{proposer}] Skipping Phase C (vote was {ctx.final_vote})")
            scheduler.mark_phase_c_complete(proposer, ctx)
    
    # ========================================
    # FINAL SUMMARY
    # ========================================
    print("\n" + "#" * 60)
    print("PARALLEL ORCHESTRATOR - FINAL SUMMARY")
    print("#" * 60)
    
    total_time = time.time() - min(
        ctx.started_at for ctx in scheduler.contexts.values() if ctx.started_at
    )
    
    results = {
        "timestamp": datetime.now().isoformat(),
        "total_time_seconds": total_time,
        "researchers": researchers,
        "results": []
    }
    
    print(f"\nTotal time: {total_time/60:.1f} minutes")
    print(f"\n{'─'*60}")
    print("RESULTS BY RESEARCHER:")
    print(f"{'─'*60}")
    
    for proposer in researchers:
        ctx = scheduler.contexts.get(proposer)
        if ctx:
            status = "✅" if ctx.deployed else ("❌" if ctx.error else "⏭️")
            print(f"  {status} {proposer}:")
            print(f"      Category: {ctx.improvement_type}")
            print(f"      Vote: {ctx.final_vote}")
            print(f"      Sandbox: {'PASSED' if ctx.sandbox_passed else 'FAILED'}")
            print(f"      Reward: {ctx.reward:.2f}")
            print(f"      Deployed: {ctx.deployed}")
            if ctx.error:
                print(f"      Error: {ctx.error[:50]}")
            
            results["results"].append({
                "proposer": proposer,
                "category": ctx.improvement_type,
                "vote": ctx.final_vote,
                "sandbox_passed": ctx.sandbox_passed,
                "reward": ctx.reward,
                "deployed": ctx.deployed,
                "error": ctx.error,
            })
    
    # Save results
    results_file = RESULTS_DIR / f"parallel_run_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
    results_file.write_text(json.dumps(results, indent=2))
    print(f"\nResults saved to: {results_file}")
    
    # Deployment summary
    deployed = [r for r in results["results"] if r["deployed"]]
    print(f"\n{'─'*60}")
    print(f"DEPLOYMENTS: {len(deployed)}/{len(researchers)}")
    print(f"{'─'*60}")
    for r in deployed:
        print(f"  ✅ {r['proposer']}: {r['category']}")
    
    return results


# ============================================================
# MAIN
# ============================================================

def main():
    import argparse
    
    parser = argparse.ArgumentParser(description="Parallel Proposal Orchestrator")
    parser.add_argument("researchers", nargs="*", 
                        help=f"Specific researchers (default: all)")
    parser.add_argument("--dry-run", action="store_true",
                        help="Show plan without executing")
    args = parser.parse_args()
    
    researchers = [r.upper() for r in args.researchers] if args.researchers else RESEARCHER_NODES
    
    # Validate researchers
    for r in researchers:
        if r not in RESEARCHERS:
            print(f"ERROR: Unknown researcher: {r}")
            print(f"Valid: {', '.join(RESEARCHERS.keys())}")
            sys.exit(1)
    
    if args.dry_run:
        print("DRY RUN - Parallel Orchestrator")
        print(f"Researchers: {', '.join(researchers)}")
        print(f"\nPhase A (Parallel): Steps 1-10")
        for r in researchers:
            print(f"  • {r} - Independent work")
        print(f"\nPhase B (Sequential): Steps 11-17")
        print(f"  • ORKA schedules peer reviews based on completion order")
        print(f"\nPhase C (Interactive): Steps 18-20")
        print(f"  • Sandbox test + Human approval in terminal")
        return
    
    try:
        run_parallel_orchestrator(researchers)
    except KeyboardInterrupt:
        print("\n\nInterrupted by user.")
        sys.exit(1)


if __name__ == "__main__":
    main()
