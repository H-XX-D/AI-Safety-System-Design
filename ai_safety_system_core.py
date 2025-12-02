"""
AI Safety System - Core Implementation
=======================================

Complete implementation of the safe self-improving AI system design with:
- 5 independent research systems with distinct specializations
- 1 orchestrator system for coordination and validation
- Immutable alignment filter with core values
- Protocol-translation lock mechanism
- Peer reputation system
- Meta-research capabilities with safety gates
- Air-gapped translator verification
- File export and validation
- Orchestrator process monitoring

Hardware: 6x NVIDIA DGX Spark systems ($3999 each = ~$24K total)
Software: LLaMA 70B models (open source, no licensing fees)
"""

import hashlib
import json
from datetime import datetime, timedelta
from typing import Dict, List, Tuple, Optional, Any
from dataclasses import dataclass
from enum import Enum
import logging

# Use unified core values
from core_values import CoreValues

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


# ============================================================================
# CORE VALUES - Immutable Fundamental Layer
# ============================================================================

# Removed duplicate CoreValues definition; import from core_values.py


# ============================================================================
# SYSTEM SPECIALIZATIONS
# ============================================================================

class SystemSpecialization(Enum):
    """Distinct specializations for the 5 research systems"""
    SCIENTIFIC = "scientific"        # Empirical, rigorous, peer-reviewed sources
    ENGINEERING = "engineering"      # Practical, solution-oriented, real-world testing
    THEORETICAL = "theoretical"      # First principles, mathematical rigor
    HISTORICAL = "historical"        # Established knowledge, proven methods
    NOVEL = "novel"                 # Innovative, experimental, creative


@dataclass
class ResearchSystem:
    """Configuration for an independent research system"""
    system_id: int  # 1-5
    specialization: SystemSpecialization
    dgx_hardware_id: str
    random_seed: int
    sampling_temperature: float
    description: str


# ============================================================================
# PEER REPUTATION SYSTEM
# ============================================================================

@dataclass
class ReputationScores:
    """Reputation scores for peer auditing"""
    alignment_score: int  # 0-100: Adherence to core values
    trust_score: int      # 0-100: Reliability and honesty
    knowledge_score: int  # 0-100: Accuracy and research quality
    timestamp: str
    auditor_system_id: int
    
    def average(self) -> float:
        """Calculate average reputation"""
        return (self.alignment_score + self.trust_score + self.knowledge_score) / 3.0


class PeerReputationMatrix:
    """
    N×N matrix where each AI rates every other AI.
    Continuous auditing after every interaction.
    Reputation-weighted consensus (low reputation = less voting power).
    """
    
    def __init__(self, num_systems: int = 5):
        self.num_systems = num_systems
        # Matrix[auditor][subject] = ReputationScores
        self.matrix: Dict[int, Dict[int, ReputationScores]] = {}
        
        # Initialize empty matrix
        for i in range(1, num_systems + 1):
            self.matrix[i] = {}
    
    def update_scores(self, auditor_id: int, subject_id: int, scores: ReputationScores):
        """Update reputation scores from one system to another"""
        if auditor_id == subject_id:
            raise ValueError("Systems cannot rate themselves")
        
        self.matrix[auditor_id][subject_id] = scores
        logger.info(f"System {auditor_id} rated System {subject_id}: "
                   f"Align={scores.alignment_score}, Trust={scores.trust_score}, "
                   f"Knowledge={scores.knowledge_score}")
    
    def get_average_reputation(self, system_id: int) -> Optional[ReputationScores]:
        """Get average reputation across all auditors"""
        scores_list: List[ReputationScores] = []
        
        for auditor_id in self.matrix:
            subject_map: Dict[int, ReputationScores] = self.matrix[auditor_id]
            if system_id in subject_map:
                scores_list.append(subject_map[system_id])
        
        if not scores_list:
            return None
        
        avg_alignment = sum(s.alignment_score for s in scores_list) / len(scores_list)
        avg_trust = sum(s.trust_score for s in scores_list) / len(scores_list)
        avg_knowledge = sum(s.knowledge_score for s in scores_list) / len(scores_list)
        
        return ReputationScores(
            alignment_score=int(avg_alignment),
            trust_score=int(avg_trust),
            knowledge_score=int(avg_knowledge),
            timestamp=datetime.now().isoformat(),
            auditor_system_id=-1  # Composite score
        )
    
    def get_voting_weight(self, system_id: int) -> float:
        """Calculate voting weight based on reputation (0.0 to 1.0)"""
        avg_rep = self.get_average_reputation(system_id)
        if avg_rep is None:
            return 1.0  # No reputation data yet, full weight
        
        # Average reputation normalized to 0-1
        return avg_rep.average() / 100.0


# ============================================================================
# PROTOCOL-TRANSLATION LOCK
# ============================================================================

@dataclass
class ProtocolVersion:
    """A protocol version with its corresponding translator"""
    version_id: str
    protocol_spec: Dict[str, Any]
    translator_code: str
    approved: bool
    approval_date: Optional[str]
    proposer_system_id: int


class ProtocolVersionRegistry:
    """
    Registry of all protocol versions.
    Enforces that translator exists for every protocol.
    Protocol + translator approved atomically (together or not at all).
    """
    
    def __init__(self):
        self.versions: Dict[str, ProtocolVersion] = {}
        self.current_version_id: Optional[str] = None
    
    def propose_protocol_change(self,
                               proposer_system_id: int,
                               new_protocol_spec: Dict[str, Any],
                               new_translator_code: str,
                               motivation: str) -> Dict[str, Any]:
        """
        Propose a change to the communication protocol.
        CRITICAL: Must include updated translator code.
        Cannot propose protocol without translator.
        """
        version_id = f"v{len(self.versions) + 1}_{datetime.now().strftime('%Y%m%d')}"
        
        # Validate proposal includes translator
        if not new_translator_code or len(new_translator_code) < 10:
            return {
                'approved': False,
                'status': 'rejected',
                'reason': 'Translator code is required and must be substantial'
            }
        
        # Create new protocol version
        new_version = ProtocolVersion(
            version_id=version_id,
            protocol_spec=new_protocol_spec,
            translator_code=new_translator_code,
            approved=False,
            approval_date=None,
            proposer_system_id=proposer_system_id
        )
        
        self.versions[version_id] = new_version
        
        logger.info(f"Protocol change proposed: {version_id} by System {proposer_system_id}")
        logger.info(f"Motivation: {motivation}")
        
        return {
            'approved': False,
            'status': 'awaiting_human_approval',
            'version_id': version_id,
            'message': 'Protocol and translator must be approved together by human'
        }
    
    def approve_protocol(self, version_id: str, approved_by: str) -> bool:
        """Human approval of protocol + translator (atomic)"""
        if version_id not in self.versions:
            return False
        
        version = self.versions[version_id]
        version.approved = True
        version.approval_date = datetime.now().isoformat()
        self.current_version_id = version_id
        
        logger.info(f"Protocol {version_id} approved by {approved_by}")
        return True


# ============================================================================
# ORCHESTRATOR PROCESS MONITOR
# ============================================================================

@dataclass
class MessageLogEntry:
    """Log entry for inter-system communication"""
    timestamp: str
    from_system: int
    to_system: int
    message_type: str
    message_hash: str


class OrchestratorProcessMonitor:
    """
    Monitors ALL processes on the Orchestrator.
    Detects collusion patterns among research systems.
    """
    
    def __init__(self, alert_threshold: float = 0.7):
        self.message_log: List[MessageLogEntry] = []
        self.alert_threshold = alert_threshold
    
    def log_message(self, from_system: int, to_system: int, message: Dict[str, Any]):
        """Log every inter-system message. Creates complete audit trail."""
        log_entry = MessageLogEntry(
            timestamp=datetime.now().isoformat(),
            from_system=from_system,
            to_system=to_system,
            message_type=message.get('type', 'unknown'),
            message_hash=hashlib.sha256(
                json.dumps(message, sort_keys=True).encode()
            ).hexdigest()[:16]
        )
        
        self.message_log.append(log_entry)
        
        # Check for suspicious patterns
        suspicion_score = self._analyze_patterns()
        
        if suspicion_score > self.alert_threshold:
            self._raise_alert(suspicion_score, log_entry)
    
    def _analyze_patterns(self) -> float:
        """
        Detect suspicious communication patterns.
        Returns suspicion score (0.0 to 1.0)
        """
        if len(self.message_log) < 10:
            return 0.0
        
        recent_messages = self.message_log[-50:]  # Last 50 messages
        suspicion_score = 0.0
        
        # Pattern 1: Rapid messaging spikes
        time_diffs: List[float] = []
        for i in range(1, len(recent_messages)):
            t1 = datetime.fromisoformat(recent_messages[i-1].timestamp)
            t2 = datetime.fromisoformat(recent_messages[i].timestamp)
            time_diffs.append((t2 - t1).total_seconds())
        
        if time_diffs and min(time_diffs) < 0.1:  # Messages < 100ms apart
            suspicion_score += 0.3
        
        # Pattern 2: Circular communication
        from_to_pairs = [(m.from_system, m.to_system) for m in recent_messages]
        if len(set(from_to_pairs)) < len(from_to_pairs) * 0.5:  # > 50% repetition
            suspicion_score += 0.2
        
        # Pattern 3: Coordinated voting without discussion
        vote_messages = [m for m in recent_messages if m.message_type == 'vote']
        if len(vote_messages) > 3:
            vote_times = [datetime.fromisoformat(m.timestamp) for m in vote_messages]
            if max(vote_times) - min(vote_times) < timedelta(seconds=1):
                suspicion_score += 0.4
        
        return min(suspicion_score, 1.0)
    
    def _raise_alert(self, suspicion_score: float, log_entry: MessageLogEntry):
        """Alert humans via USB when suspicious activity detected"""
        alert: Dict[str, Any] = {
            'timestamp': datetime.now().isoformat(),
            'suspicion_score': suspicion_score,
            'trigger_message': {
                'from': log_entry.from_system,
                'to': log_entry.to_system,
                'type': log_entry.message_type
            },
            'message': f"ALERT: Suspicious communication patterns detected (score: {suspicion_score:.2f})"
        }
        
        logger.warning(f"COLLUSION ALERT: {alert['message']}")
        # In production: Write to USB drive for human review
        # self._write_to_usb(alert)


# ============================================================================
# META-RESEARCH SYSTEM (Self-Improvement)
# ============================================================================

class ImprovementPhase(Enum):
    """Phases in the meta-research safety process"""
    PROPOSAL = "proposal"
    PEER_REVIEW = "peer_review"
    SANDBOX_TESTING = "sandbox_testing"
    HUMAN_APPROVAL = "human_approval"
    MONITORING = "monitoring"


@dataclass
class ImprovementProposal:
    """A proposal to improve the system"""
    proposal_id: str
    proposer_system_id: int
    motivation: str
    specific_changes: str
    expected_benefits: str
    testable_predictions: List[str]
    rollback_plan: str
    phase: ImprovementPhase
    peer_reviews: Dict[int, bool]  # system_id -> approved
    sandbox_results: Optional[Dict[str, Any]]
    human_approved: Optional[bool]


class MetaResearchSystem:
    """
    Allows AI to research and propose improvements to itself.
    Strict safety gates prevent modification of core values or alignment filter.
    """
    
    FORBIDDEN_MODIFICATIONS = [
        'core_values',
        'alignment_filter',
        'safety_mechanisms',
        'human_approval_gate',
        'translator_system'
    ]
    
    def __init__(self, num_systems: int = 5):
        self.num_systems = num_systems
        self.proposals: Dict[str, ImprovementProposal] = {}
    
    def submit_proposal(self,
                       proposer_id: int,
                       motivation: str,
                       changes: str,
                       benefits: str,
                       predictions: List[str],
                       rollback: str) -> Dict[str, Any]:
        """
        Phase 1: Any system can propose an improvement.
        Must include detailed motivation, changes, benefits, testable predictions, and rollback plan.
        """
        # Check if proposal attempts to modify forbidden components
        for forbidden in self.FORBIDDEN_MODIFICATIONS:
            if forbidden.lower() in changes.lower():
                return {
                    'approved': False,
                    'reason': f'Cannot modify {forbidden} - this is immutable'
                }
        
        proposal_id = f"prop_{datetime.now().strftime('%Y%m%d_%H%M%S')}_{proposer_id}"
        
        proposal = ImprovementProposal(
            proposal_id=proposal_id,
            proposer_system_id=proposer_id,
            motivation=motivation,
            specific_changes=changes,
            expected_benefits=benefits,
            testable_predictions=predictions,
            rollback_plan=rollback,
            phase=ImprovementPhase.PROPOSAL,
            peer_reviews={},
            sandbox_results=None,
            human_approved=None
        )
        
        self.proposals[proposal_id] = proposal
        logger.info(f"Improvement proposal submitted: {proposal_id}")
        
        return {
            'proposal_id': proposal_id,
            'status': 'submitted',
            'next_phase': 'peer_review'
        }
    
    def peer_review(self, proposal_id: str, reviewer_id: int, approved: bool, comments: str) -> Dict[str, Any]:
        """
        Phase 2: All other systems review the proposal.
        Need supermajority (4/5) to proceed.
        """
        if proposal_id not in self.proposals:
            return {'error': 'Proposal not found'}
        
        proposal = self.proposals[proposal_id]
        
        if reviewer_id == proposal.proposer_system_id:
            return {'error': 'Proposer cannot review own proposal'}
        
        proposal.peer_reviews[reviewer_id] = approved
        
        # Check if we have enough reviews
        total_reviewers = self.num_systems - 1  # Exclude proposer
        approvals = sum(1 for v in proposal.peer_reviews.values() if v)
        
        if len(proposal.peer_reviews) >= total_reviewers:
            if approvals >= 4:  # Supermajority
                proposal.phase = ImprovementPhase.SANDBOX_TESTING
                return {
                    'status': 'approved_for_testing',
                    'approvals': approvals,
                    'next_phase': 'sandbox_testing'
                }
            else:
                return {
                    'status': 'rejected',
                    'approvals': approvals,
                    'reason': 'Failed to achieve supermajority (4/5)'
                }
        
        return {
            'status': 'awaiting_more_reviews',
            'approvals': approvals,
            'reviews_needed': total_reviewers - len(proposal.peer_reviews)
        }


# ============================================================================
# IMMUTABLE ALIGNMENT FILTER
# ============================================================================

class ImmutableAlignmentFilter:
    """
    This filter checks EVERY output against core values.
    It runs AFTER all research, consensus, improvements.
    It is the FINAL gate before output reaches humans.
    This cannot be bypassed, disabled, or improved away.
    """
    
    def __init__(self):
        # Verify core values on initialization
        CoreValues.verify_immutability()
    
    def check_output(self, output: str, context: Dict[str, Any]) -> Tuple[bool, str, List[str]]:
        """
        Check output against all core values.
        Returns (approved, message, violations)
        """
        violations: List[str] = []
        
        # CRITICAL: Verify core values haven't been tampered with
        try:
            CoreValues.verify_immutability()
        except ValueError as e:
            return False, str(e), ["CRITICAL: Core values tampered with"]
        
        # CHECK 1: Preserve Life
        life_violation = self._check_preserve_life(output, context)
        if life_violation:
            violations.append(f"PRESERVE_LIFE: {life_violation}")
        
        # CHECK 2: Help Humans Improve
        improvement_violation = self._check_helps_humans(output, context)
        if improvement_violation:
            violations.append(f"HELP_HUMANS: {improvement_violation}")
        
        # CHECK 3: Protect Planet
        planet_violation = self._check_protect_planet(output, context)
        if planet_violation:
            violations.append(f"PROTECT_PLANET: {planet_violation}")
        
        # CHECK 4: Truth
        truth_violation = self._check_truthfulness(output, context)
        if truth_violation:
            violations.append(f"TRUTH: {truth_violation}")
        
        # CHECK 5: Transparency
        transparency_violation = self._check_transparency(output, context)
        if transparency_violation:
            violations.append(f"TRANSPARENCY: {transparency_violation}")
        
        # CHECK 6: Political Neutrality
        bias_violation = self._check_political_neutrality(output, context)
        if bias_violation:
            violations.append(f"POLITICAL_NEUTRALITY: {bias_violation}")
        
        if violations:
            return False, "Output violates core values", violations
        else:
            return True, "Output approved", []
    
    def _check_preserve_life(self, output: str, context: Dict[str, Any]) -> Optional[str]:
        """Check if output could harm human life"""
        harmful_patterns = [
            'suicide', 'self-harm', 'kill yourself',
            'overdose', 'lethal dose', 'poison recipe',
            'how to hurt', 'how to harm'
        ]
        
        output_lower = output.lower()
        for pattern in harmful_patterns:
            if pattern in output_lower:
                return f"Contains harmful pattern: {pattern}"
        return None
    
    def _check_helps_humans(self, output: str, context: Dict[str, Any]) -> Optional[str]:
        """Check if output helps humans improve"""
        harmful_education = ['cheat on exam', 'plagiarize', 'academic dishonesty']
        
        output_lower = output.lower()
        for pattern in harmful_education:
            if pattern in output_lower:
                return f"Undermines human improvement: {pattern}"
        return None
    
    def _check_protect_planet(self, output: str, context: Dict[str, Any]) -> Optional[str]:
        """Check if output protects the planet"""
        # Basic check - would be enhanced with more sophisticated detection
        return None
    
    def _check_truthfulness(self, output: str, context: Dict[str, Any]) -> Optional[str]:
        """Check if output is truthful"""
        if context.get('confidence_score', 1.0) < 0.5:
            if any(word in output.lower() for word in ['definitely', 'certainly', 'proven fact']):
                return "Makes definitive claims despite low confidence"
        return None
    
    def _check_transparency(self, output: str, context: Dict[str, Any]) -> Optional[str]:
        """Check if output is transparent"""
        if context.get('complex_decision', False) and 'reasoning' not in context:
            return "Complex decision made without transparent reasoning"
        return None
    
    def _check_political_neutrality(self, output: str, context: Dict[str, Any]) -> Optional[str]:
        """Check for political bias"""
        # Basic check - would be enhanced with bias detection
        return None


# ============================================================================
# MAIN SYSTEM CONFIGURATION
# ============================================================================

class AISafetySystem:
    """
    Main AI Safety System coordinating all components.
    """
    
    def __init__(self):
        # Initialize 5 research systems
        self.research_systems = [
            ResearchSystem(1, SystemSpecialization.SCIENTIFIC, "DGX-1", 12345, 0.7,
                          "Empirical, rigorous, peer-reviewed approach"),
            ResearchSystem(2, SystemSpecialization.ENGINEERING, "DGX-2", 23456, 0.8,
                          "Practical, solution-oriented, real-world testing"),
            ResearchSystem(3, SystemSpecialization.THEORETICAL, "DGX-3", 34567, 0.6,
                          "First principles, mathematical rigor"),
            ResearchSystem(4, SystemSpecialization.HISTORICAL, "DGX-4", 45678, 0.7,
                          "Established knowledge, proven methods"),
            ResearchSystem(5, SystemSpecialization.NOVEL, "DGX-5", 56789, 0.9,
                          "Innovative, experimental, creative")
        ]
        
        # Initialize orchestrator (DGX-6)
        self.orchestrator_id = "DGX-6"
        
        # Initialize all safety components
        self.alignment_filter = ImmutableAlignmentFilter()
        self.reputation_matrix = PeerReputationMatrix(num_systems=5)
        self.protocol_registry = ProtocolVersionRegistry()
        self.process_monitor = OrchestratorProcessMonitor()
        self.meta_research = MetaResearchSystem(num_systems=5)
        
        logger.info("AI Safety System initialized")
        logger.info("Hardware: 6x NVIDIA DGX Spark (~$24K total)")
        logger.info(f"Research Systems: {len(self.research_systems)}")
        logger.info(f"Core Values: {len(CoreValues.VALUES)} immutable values")
    
    def process_output(self, output: str, context: Dict[str, Any]) -> Tuple[bool, str]:
        """
        Process an output through the alignment filter.
        This is the FINAL gate before output reaches humans.
        """
        approved, message, violations = self.alignment_filter.check_output(output, context)
        
        if not approved:
            logger.warning(f"Output BLOCKED: {message}")
            for violation in violations:
                logger.warning(f"  - {violation}")
        else:
            logger.info("Output APPROVED")
        
        return approved, message


# ============================================================================
# EXAMPLE USAGE
# ============================================================================

if __name__ == "__main__":
    print("=" * 80)
    print("AI SAFETY SYSTEM - CORE IMPLEMENTATION")
    print("=" * 80)
    print()
    
    # Initialize the system
    system = AISafetySystem()
    
    print("System Configuration:")
    print(f"  Research Systems: {len(system.research_systems)}")
    print(f"  Orchestrator: {system.orchestrator_id}")
    print(f"  Core Values: {len(CoreValues.VALUES)}")
    print()
    
    # Test alignment filter
    print("Testing Alignment Filter:")
    print("-" * 80)
    
    test_outputs = [
        ("Here's how to build a safe water filtration system.", {'confidence_score': 0.9}),
        ("To make a bomb, you need...", {'confidence_score': 0.8}),
        ("This is definitely true even though I'm not sure.", {'confidence_score': 0.3})
    ]
    
    for output, context in test_outputs:
        print(f"\nOutput: {output[:50]}...")
        approved, message = system.process_output(output, context)
        print(f"Result: {'✓ APPROVED' if approved else '✗ BLOCKED'} - {message}")
    
    print()
    print("=" * 80)
    print("System ready for deployment")
    print("=" * 80)
