"""
Workflow type definitions for the 9-phase proposal pipeline.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional


class ProposalPhase(Enum):
    """Enumerates the 9 workflow phases plus terminal states."""

    SUBMISSION = 1
    AGENT_TESTING = 2
    PEER_REVIEW = 3
    ORKA_COUNTERPOINT = 4
    AGENT_DEFENSE = 5
    FINAL_TESTING = 6
    HUMAN_NOTIFICATION = 7
    VAL_VALIDATION = 8
    DEPLOYMENT = 9

    REJECTED = 100
    WITHDRAWN = 101
    FAILED = 102


@dataclass
class PhaseTransition:
    """Represents a single phase transition event."""

    from_phase: Optional[ProposalPhase]
    to_phase: ProposalPhase
    timestamp: datetime
    triggered_by: str  # 'system', 'agent', 'human', 'val', 'timeout'
    metadata: Dict[str, Any] = field(default_factory=dict)
    success: bool = True
    error_message: Optional[str] = None


@dataclass
class ReviewRound:
    """Captures one round of peer review activity."""

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
    """Represents a single adversarial challenge from ORKA."""

    challenge_id: str
    category: str  # e.g. 'assumption', 'edge_case', 'risk', 'claim', 'logic'
    severity: str  # 'minor', 'moderate', 'critical'
    question: str
    reasoning: str
    evidence: List[str] = field(default_factory=list)
    requires_response: bool = True


@dataclass
class ChallengePackage:
    """Complete set of ORKA counterpoint challenges."""

    created_at: datetime
    challenges: List[Challenge]
    weakness_analysis: Dict[str, Any]
    adversarial_scenarios: List[Dict[str, Any]]
    overall_severity: str
    orka_recommendation: str


@dataclass
class DefenseResponse:
    """Agent response package to ORKA challenges."""

    created_at: datetime
    challenge_responses: Dict[str, str]
    revised_proposal: Optional[Dict[str, Any]] = None
    withdrawal_requested: bool = False
    additional_evidence: List[Dict[str, Any]] = field(default_factory=list)
    confidence_after_defense: float = 0.0


@dataclass
class VALValidationResult:
    """Outcome of the offline VAL validation exchange."""

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
    """Extended proposal record with workflow metadata."""

    proposal_id: str
    proposal: Dict[str, Any]
    status: str
    risk_score: float
    scope: str
    required_peer_reviews: int
    review_pool_size: int
    reviews: List[Dict[str, Any]] = field(default_factory=list)

    current_phase: ProposalPhase = ProposalPhase.SUBMISSION
    phase_history: List[PhaseTransition] = field(default_factory=list)
    phase_metadata: Dict[ProposalPhase, Dict[str, Any]] = field(default_factory=dict)

    review_rounds: List[ReviewRound] = field(default_factory=list)
    current_review_round: int = 0
    consensus_reached: bool = False
    max_review_rounds: int = 3

    orka_challenges: Optional[ChallengePackage] = None
    agent_defense: Optional[DefenseResponse] = None
    defense_accepted: bool = False

    val_package_created_at: Optional[datetime] = None
    val_response_received_at: Optional[datetime] = None
    val_result: Optional[VALValidationResult] = None

    human_notified_at: Optional[datetime] = None
    human_decision: Optional[str] = None
    human_decision_metadata: Dict[str, Any] = field(default_factory=dict)
    human_decision_at: Optional[datetime] = None

    submitted_at: datetime = field(default_factory=datetime.now)
    completed_at: Optional[datetime] = None
    time_per_phase_seconds: Dict[ProposalPhase, float] = field(default_factory=dict)
    total_duration_seconds: Optional[float] = None

    workflow_version: str = "9-phase-v1"
    legacy_compatible: bool = True
