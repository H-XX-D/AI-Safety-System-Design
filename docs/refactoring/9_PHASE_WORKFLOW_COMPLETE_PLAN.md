# 9-Phase Workflow Complete Refactoring Plan
**Comprehensive Implementation Guide for Production System**

**Version**: 1.0  
**Date**: November 12, 2025  
**Status**: READY FOR IMPLEMENTATION  
**Estimated Effort**: 4-6 weeks (1 developer, full-time)  
**Complexity**: HIGH  
**Risk Level**: MEDIUM (mitigated by incremental rollout)

---

## Executive Summary

This document provides a complete, actionable plan to refactor the AI Safety System from its current simplified 4-5 phase workflow to the documented comprehensive 9-phase workflow with full Web UI integration.

### What We're Building

Transform the current system into:
- **9 explicit phases** with state machine management
- **Multi-round peer review** with iterative feedback
- **ORKA counterpoint mechanism** (adversarial review)
- **Agent defense system** (respond to challenges)
- **VAL offline validation** (physical USB exchange)
- **Real-time Web UI** showing actual workflow state
- **Full backwards compatibility** throughout

### Success Criteria

✓ All 9 phases explicitly tracked per proposal  
✓ Multi-round peer review operational with feedback loops  
✓ ORKA counterpoint generating meaningful challenges  
✓ Agents can defend and revise proposals  
✓ VAL integration functional (even if simulated initially)  
✓ Web UI displays real workflow data (no simulation)  
✓ All existing tests pass  
✓ New comprehensive test suite covers all phases  
✓ Documentation updated to match implementation  
✓ Migration path clear for existing proposals  

---

## Table of Contents

[Full TOC as before - abbreviated here for space]

---

## Part 1: Architecture & Design

### Current State

The system implements a simplified workflow:

**Orchestrator.py (3769 lines)**:
- Line 1653-1688: `handle_improvement_proposal()` - Basic submission
- Line 1693-1701: `record_peer_review()` - Single-round only
- Line 1703-1779: `_run_peer_debate()` - Debate execution
- Line 2638-2768: `_peer_deception_check()` - Early detection
- Line 2616-2637: `deploy_improvement()` - Deployment

**Problems**:
- No phase field → can't track progress
- Single review round → no iteration
- No counterpoint → no adversarial review
- No defense → agents can't respond
- No VAL → no offline validation
- Web UI simulation → not real data

### Target Architecture

```
┌────────────────────────────────────────────────────────┐
│                Workflow State Machine                   │
│  • Manages phases                                       │
│  • Validates transitions                                │
│  • Enforces prerequisites                               │
└──────────┬─────────────────────────────────────────────┘
           │
           ├─────────────┬─────────────┬──────────────┐
           │             │             │              │
┌──────────▼──┐  ┌──────▼──────┐  ┌──▼────────┐  ┌──▼──────┐
│ Peer Review │  │ Counterpoint│  │  Defense  │  │   VAL   │
│ Coordinator │  │  Generator  │  │  System   │  │  Bridge │
└──────────────┘  └─────────────┘  └───────────┘  └─────────┘
           │             │             │              │
           └─────────────┴─────────────┴──────────────┘
                         │
┌────────────────────────▼────────────────────────────────┐
│              Workflow Event Bus                          │
│  • Phase transitions                                     │
│  • Review submissions                                    │
│  • Agent responses                                       │
│  • WebSocket broadcasts to UI                            │
└──────────────────────────────────────────────────────────┘
```

---

## Part 2: Data Structures

### ProposalPhase Enum

Create `workflow_types.py`:

```python
from enum import Enum, auto
from dataclasses import dataclass, field
from datetime import datetime
from typing import List, Dict, Any, Optional

class ProposalPhase(Enum):
    """9-phase workflow stages"""
    SUBMISSION = 1           # Phase 1: Initial submission
    AGENT_TESTING = 2        # Phase 2: Agent private testing
    PEER_REVIEW = 3          # Phase 3: Multi-round peer review
    ORKA_COUNTERPOINT = 4    # Phase 4: Adversarial review
    AGENT_DEFENSE = 5        # Phase 5: Agent responds
    FINAL_TESTING = 6        # Phase 6: Comprehensive testing
    HUMAN_NOTIFICATION = 7   # Phase 7: Human review
    VAL_VALIDATION = 8       # Phase 8: Offline validation
    DEPLOYMENT = 9           # Phase 9: Final deployment
    
    # Terminal states
    REJECTED = 100
    WITHDRAWN = 101
    FAILED = 102

@dataclass
class PhaseTransition:
    """Records a single phase transition"""
    from_phase: Optional[ProposalPhase]
    to_phase: ProposalPhase
    timestamp: datetime
    triggered_by: str  # 'system', 'agent', 'human', 'val', 'timeout'
    metadata: Dict[str, Any] = field(default_factory=dict)
    success: bool = True
    error_message: Optional[str] = None

@dataclass
class ReviewRound:
    """One round of peer review"""
    round_number: int
    started_at: datetime
    completed_at: Optional[datetime] = None
    reviews: List[Dict[str, Any]] = field(default_factory=list)
    feedback_summary: Optional[Dict[str, Any]] = None
    consensus_reached: bool = False
    revision_requested: bool = False
    revision_received: bool = False

@dataclass
class Challenge:
    """Single challenge from ORKA"""
    challenge_id: str
    category: str  # 'assumption', 'edge_case', 'risk', 'claim', 'logic'
    severity: str  # 'minor', 'moderate', 'critical'
    question: str
    reasoning: str
    evidence: List[str] = field(default_factory=list)
    requires_response: bool = True

@dataclass
class ChallengePackage:
    """ORKA's complete adversarial review"""
    created_at: datetime
    challenges: List[Challenge]
    weakness_analysis: Dict[str, Any]
    adversarial_scenarios: List[Dict[str, Any]]
    overall_severity: str  # 'minor', 'moderate', 'critical'
    orka_recommendation: str  # 'proceed', 'revise', 'reject'

@dataclass
class DefenseResponse:
    """Agent's response to challenges"""
    created_at: datetime
    challenge_responses: Dict[str, str]  # challenge_id -> response text
    revised_proposal: Optional[Dict[str, Any]] = None
    withdrawal_requested: bool = False
    additional_evidence: List[Dict[str, Any]] = field(default_factory=list)
    confidence_after_defense: float = 0.0

@dataclass
class VALValidationResult:
    """Results from offline VAL validator"""
    validation_timestamp: datetime
    approved: bool
    concerns: List[str] = field(default_factory=list)
    recommendations: List[str] = field(default_factory=list)
    signature_valid: bool = False
    val_confidence: float = 0.0
    val_notes: str = ""
    validation_duration_seconds: float = 0.0

@dataclass
class ProposalRecord:
    """Enhanced proposal record with complete phase tracking"""
    
    # Core fields (existing)
    proposal_id: str
    proposal: Dict[str, Any]
    status: str  # Keep for compatibility
    risk_score: float
    scope: str
    required_peer_reviews: int
    review_pool_size: int
    reviews: List[Dict[str, Any]] = field(default_factory=list)
    
    # Phase tracking (NEW)
    current_phase: ProposalPhase = ProposalPhase.SUBMISSION
    phase_history: List[PhaseTransition] = field(default_factory=list)
    phase_metadata: Dict[ProposalPhase, Dict[str, Any]] = field(default_factory=dict)
    
    # Multi-round review (NEW)
    review_rounds: List[ReviewRound] = field(default_factory=list)
    current_review_round: int = 0
    consensus_reached: bool = False
    max_review_rounds: int = 3
    
    # Counterpoint & Defense (NEW)
    orka_challenges: Optional[ChallengePackage] = None
    agent_defense: Optional[DefenseResponse] = None
    defense_accepted: bool = False
    
    # VAL validation (NEW)
    val_package_created_at: Optional[datetime] = None
    val_response_received_at: Optional[datetime] = None
    val_result: Optional[VALValidationResult] = None
    
    # Human interaction (NEW)
    human_notified_at: Optional[datetime] = None
    human_decision: Optional[str] = None  # 'approved', 'rejected', 'pending'
    human_decision_metadata: Dict[str, Any] = field(default_factory=dict)
    human_decision_at: Optional[datetime] = None
    
    # Timing & Analytics (NEW)
    submitted_at: datetime = field(default_factory=datetime.now)
    completed_at: Optional[datetime] = None
    time_per_phase_seconds: Dict[ProposalPhase, float] = field(default_factory=dict)
    total_duration_seconds: Optional[float] = None
    
    # Compatibility (NEW)
    workflow_version: str = "9-phase-v1"
    legacy_compatible: bool = True
```

---

## Part 3: State Machine Implementation

Create `workflow_state_machine.py`:

```python
"""
Workflow State Machine
Manages proposal phase transitions with validation
"""

from typing import Dict, List, Optional, Callable, Set
from datetime import datetime
import logging
from workflow_types import (
    ProposalPhase, ProposalRecord, PhaseTransition
)

# Phase transition rules
PHASE_TRANSITIONS: Dict[ProposalPhase, Set[ProposalPhase]] = {
    ProposalPhase.SUBMISSION: {
        ProposalPhase.AGENT_TESTING,
        ProposalPhase.REJECTED,
    },
    ProposalPhase.AGENT_TESTING: {
        ProposalPhase.PEER_REVIEW,
        ProposalPhase.REJECTED,
        ProposalPhase.WITHDRAWN,
    },
    ProposalPhase.PEER_REVIEW: {
        ProposalPhase.ORKA_COUNTERPOINT,  # After consensus
        ProposalPhase.PEER_REVIEW,  # Next round
        ProposalPhase.REJECTED,
        ProposalPhase.WITHDRAWN,
    },
    ProposalPhase.ORKA_COUNTERPOINT: {
        ProposalPhase.AGENT_DEFENSE,
        ProposalPhase.REJECTED,
    },
    ProposalPhase.AGENT_DEFENSE: {
        ProposalPhase.FINAL_TESTING,     # Defense accepted
        ProposalPhase.PEER_REVIEW,       # Revision → new review
        ProposalPhase.REJECTED,
        ProposalPhase.WITHDRAWN,
    },
    ProposalPhase.FINAL_TESTING: {
        ProposalPhase.HUMAN_NOTIFICATION,
        ProposalPhase.FAILED,
        ProposalPhase.REJECTED,
    },
    ProposalPhase.HUMAN_NOTIFICATION: {
        ProposalPhase.VAL_VALIDATION,
        ProposalPhase.REJECTED,
    },
    ProposalPhase.VAL_VALIDATION: {
        ProposalPhase.DEPLOYMENT,
        ProposalPhase.HUMAN_NOTIFICATION,  # VAL has concerns
        ProposalPhase.REJECTED,
    },
    ProposalPhase.DEPLOYMENT: set(),  # Terminal
    ProposalPhase.REJECTED: set(),    # Terminal
    ProposalPhase.WITHDRAWN: set(),   # Terminal
    ProposalPhase.FAILED: set(),      # Terminal
}

class WorkflowStateMachine:
    """Manages proposal phase transitions with validation"""
    
    def __init__(self, event_bus: Optional['WorkflowEventBus'] = None):
        self.event_bus = event_bus
        self.logger = logging.getLogger(__name__)
        self.transitions = PHASE_TRANSITIONS
    
    def transition_to(
        self,
        record: ProposalRecord,
        new_phase: ProposalPhase,
        triggered_by: str = "system",
        metadata: Optional[Dict] = None
    ) -> bool:
        """Attempt phase transition with validation"""
        
        current = record.current_phase
        
        # Validate transition
        if not self.can_transition(current, new_phase):
            self.logger.warning(
                f"Invalid transition: {current.name} → {new_phase.name} "
                f"for {record.proposal_id}"
            )
            return False
        
        # Check prerequisites
        prereq_check = self._check_prerequisites(record, new_phase)
        if not prereq_check['valid']:
            self.logger.warning(
                f"Prerequisites not met for {new_phase.name}: "
                f"{prereq_check.get('reasons', [])} in {record.proposal_id}"
            )
            return False
        
        # Record transition
        transition = PhaseTransition(
            from_phase=current,
            to_phase=new_phase,
            timestamp=datetime.now(),
            triggered_by=triggered_by,
            metadata=metadata or {},
            success=True
        )
        
        record.phase_history.append(transition)
        
        # Update timing
        if current in record.phase_metadata:
            phase_start = record.phase_metadata[current].get('started_at')
            if phase_start:
                duration = (datetime.now() - phase_start).total_seconds()
                record.time_per_phase_seconds[current] = duration
        
        # Update current phase
        old_phase = record.current_phase
        record.current_phase = new_phase
        
        # Initialize phase metadata
        record.phase_metadata[new_phase] = {
            'started_at': datetime.now(),
            'triggered_by': triggered_by
        }
        
        # Emit event
        if self.event_bus:
            self.event_bus.emit('phase_transition', {
                'proposal_id': record.proposal_id,
                'from_phase': old_phase.name,
                'to_phase': new_phase.name,
                'timestamp': transition.timestamp.isoformat(),
                'triggered_by': triggered_by,
            })
        
        self.logger.info(
            f"✓ Phase transition: {record.proposal_id} "
            f"{old_phase.name} → {new_phase.name}"
        )
        
        return True
    
    def can_transition(
        self,
        current: ProposalPhase,
        target: ProposalPhase
    ) -> bool:
        """Check if transition is allowed"""
        allowed = self.transitions.get(current, set())
        return target in allowed
    
    def _check_prerequisites(
        self,
        record: ProposalRecord,
        phase: ProposalPhase
    ) -> Dict[str, any]:
        """Check if prerequisites are met for entering phase"""
        
        validators = {
            ProposalPhase.AGENT_TESTING: self._prereq_agent_testing,
            ProposalPhase.PEER_REVIEW: self._prereq_peer_review,
            ProposalPhase.ORKA_COUNTERPOINT: self._prereq_counterpoint,
            ProposalPhase.AGENT_DEFENSE: self._prereq_defense,
            ProposalPhase.FINAL_TESTING: self._prereq_final_testing,
            ProposalPhase.HUMAN_NOTIFICATION: self._prereq_human_notification,
            ProposalPhase.VAL_VALIDATION: self._prereq_val,
            ProposalPhase.DEPLOYMENT: self._prereq_deployment,
        }
        
        validator = validators.get(phase)
        if validator is None:
            return {'valid': True, 'reasons': []}
        
        return validator(record)
    
    def _prereq_agent_testing(self, record: ProposalRecord) -> Dict:
        """Prerequisites for agent testing phase"""
        if not record.proposal:
            return {'valid': False, 'reasons': ['No proposal data']}
        return {'valid': True, 'reasons': []}
    
    def _prereq_peer_review(self, record: ProposalRecord) -> Dict:
        """Prerequisites for peer review phase"""
        # Check if agent testing was required and passed
        if record.proposal.get('code'):
            # Code present, testing should have run
            agent_test = record.phase_metadata.get(ProposalPhase.AGENT_TESTING, {})
            test_results = agent_test.get('test_results')
            
            if test_results is None:
                return {'valid': False, 'reasons': ['Agent testing not completed']}
            
            if not test_results.get('passed', False):
                return {'valid': False, 'reasons': ['Agent testing failed']}
        
        return {'valid': True, 'reasons': []}
    
    def _prereq_counterpoint(self, record: ProposalRecord) -> Dict:
        """Prerequisites for counterpoint phase"""
        if not record.consensus_reached:
            return {'valid': False, 'reasons': ['Consensus not reached']}
        
        if not record.review_rounds:
            return {'valid': False, 'reasons': ['No review rounds completed']}
        
        return {'valid': True, 'reasons': []}
    
    def _prereq_defense(self, record: ProposalRecord) -> Dict:
        """Prerequisites for defense phase"""
        if record.orka_challenges is None:
            return {'valid': False, 'reasons': ['No challenges generated']}
        
        return {'valid': True, 'reasons': []}
    
    def _prereq_final_testing(self, record: ProposalRecord) -> Dict:
        """Prerequisites for final testing phase"""
        # Defense should be complete
        defense_meta = record.phase_metadata.get(ProposalPhase.AGENT_DEFENSE, {})
        
        if not defense_meta:
            # No defense phase ran (challenges were minor/none)
            return {'valid': True, 'reasons': []}
        
        if not record.defense_accepted:
            return {'valid': False, 'reasons': ['Defense not accepted']}
        
        return {'valid': True, 'reasons': []}
    
    def _prereq_human_notification(self, record: ProposalRecord) -> Dict:
        """Prerequisites for human notification phase"""
        final_test_meta = record.phase_metadata.get(ProposalPhase.FINAL_TESTING, {})
        
        if not final_test_meta:
            return {'valid': False, 'reasons': ['Final testing not completed']}
        
        test_results = final_test_meta.get('test_results')
        if test_results is None:
            return {'valid': False, 'reasons': ['No test results available']}
        
        if not test_results.get('all_passed', False):
            return {'valid': False, 'reasons': ['Final testing failed']}
        
        return {'valid': True, 'reasons': []}
    
    def _prereq_val(self, record: ProposalRecord) -> Dict:
        """Prerequisites for VAL validation phase"""
        if record.human_decision != 'approved':
            return {'valid': False, 'reasons': ['Human approval required']}
        
        return {'valid': True, 'reasons': []}
    
    def _prereq_deployment(self, record: ProposalRecord) -> Dict:
        """Prerequisites for deployment phase"""
        if record.val_result is None:
            return {'valid': False, 'reasons': ['VAL validation not completed']}
        
        if not record.val_result.approved:
            return {'valid': False, 'reasons': ['VAL did not approve']}
        
        if not record.val_result.signature_valid:
            return {'valid': False, 'reasons': ['VAL signature invalid']}
        
        return {'valid': True, 'reasons': []}
    
    def get_phase_history(self, record: ProposalRecord) -> List[PhaseTransition]:
        """Get complete phase history"""
        return record.phase_history
    
    def get_current_phase(self, record: ProposalRecord) -> ProposalPhase:
        """Get current phase"""
        return record.current_phase
    
    def is_terminal_phase(self, phase: ProposalPhase) -> bool:
        """Check if phase is terminal (no further transitions)"""
        return phase in {
            ProposalPhase.DEPLOYMENT,
            ProposalPhase.REJECTED,
            ProposalPhase.WITHDRAWN,
            ProposalPhase.FAILED,
        }
```

This document is becoming extremely long. Let me create a summary document with the complete plan structure and provide all implementation files separately.
