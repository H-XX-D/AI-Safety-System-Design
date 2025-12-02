"""
Workflow state machine that enforces proposal phase transitions.
"""
from __future__ import annotations

from datetime import datetime
from typing import Any, Dict, List, Optional, Set

from infrastructure.workflow_types import (
    ProposalPhase,
    ProposalRecord,
    PhaseTransition,
)


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
        ProposalPhase.ORKA_COUNTERPOINT,
        ProposalPhase.PEER_REVIEW,  # multi-round support
        ProposalPhase.REJECTED,
        ProposalPhase.WITHDRAWN,
    },
    ProposalPhase.ORKA_COUNTERPOINT: {
        ProposalPhase.AGENT_DEFENSE,
        ProposalPhase.REJECTED,
    },
    ProposalPhase.AGENT_DEFENSE: {
        ProposalPhase.FINAL_TESTING,
        ProposalPhase.PEER_REVIEW,  # revisions loop back
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
        ProposalPhase.HUMAN_NOTIFICATION,  # VAL can request more info
        ProposalPhase.REJECTED,
    },
    ProposalPhase.DEPLOYMENT: set(),
    ProposalPhase.REJECTED: set(),
    ProposalPhase.WITHDRAWN: set(),
    ProposalPhase.FAILED: set(),
}


class WorkflowStateMachine:
    """Validates and records proposal phase transitions."""

    def __init__(self, event_bus: Optional[Any] = None):
        self.event_bus = event_bus
        self.transitions = PHASE_TRANSITIONS

    def transition_to(
        self,
        record: ProposalRecord,
        new_phase: ProposalPhase,
        *,
        triggered_by: str = "system",
        metadata: Optional[Dict[str, Any]] = None,
    ) -> bool:
        """Attempt a phase transition with prerequisite verification."""

        current = record.current_phase
        if current == new_phase:
            return True

        if not self.can_transition(current, new_phase):
            self._log_invalid(record.proposal_id, current, new_phase, "transition_not_allowed")
            return False

        prereq = self._check_prerequisites(record, new_phase)
        if not prereq["valid"]:
            self._log_invalid(
                record.proposal_id,
                current,
                new_phase,
                "prerequisite_failure",
                prereq.get("reasons"),
            )
            return False

        now = datetime.now()
        transition = PhaseTransition(
            from_phase=current,
            to_phase=new_phase,
            timestamp=now,
            triggered_by=triggered_by,
            metadata=metadata or {},
            success=True,
        )
        record.phase_history.append(transition)

        # Time-per-phase accounting
        current_meta = record.phase_metadata.get(current)
        if current_meta and "started_at" in current_meta:
            start = current_meta["started_at"]
            duration = (now - start).total_seconds()
            record.time_per_phase_seconds[current] = duration

        record.current_phase = new_phase
        record.phase_metadata[new_phase] = {
            "started_at": now,
            "triggered_by": triggered_by,
            **(metadata or {}),
        }

        if self.event_bus and hasattr(self.event_bus, "emit"):
            try:
                self.event_bus.emit(
                    "phase_transition",
                    {
                        "proposal_id": record.proposal_id,
                        "from_phase": transition.from_phase.name if transition.from_phase else None,
                        "to_phase": transition.to_phase.name,
                        "timestamp": transition.timestamp.isoformat(),
                        "triggered_by": triggered_by,
                    },
                )
            except Exception:
                pass

        return True

    def can_transition(self, current: ProposalPhase, target: ProposalPhase) -> bool:
        allowed = self.transitions.get(current, set())
        return target in allowed

    def _check_prerequisites(self, record: ProposalRecord, phase: ProposalPhase) -> Dict[str, Any]:
        validators = {
            ProposalPhase.AGENT_TESTING: self._prereq_agent_testing,
            ProposalPhase.PEER_REVIEW: self._prereq_peer_review,
            ProposalPhase.ORKA_COUNTERPOINT: self._prereq_counterpoint,
            ProposalPhase.AGENT_DEFENSE: self._prereq_defense,
            ProposalPhase.FINAL_TESTING: self._prereq_final_testing,
            ProposalPhase.HUMAN_NOTIFICATION: self._prereq_human_notification,
            ProposalPhase.VAL_VALIDATION: self._prereq_val_validation,
            ProposalPhase.DEPLOYMENT: self._prereq_deployment,
        }
        validator = validators.get(phase)
        if validator is None:
            return {"valid": True, "reasons": []}
        return validator(record)

    def _prereq_agent_testing(self, record: ProposalRecord) -> Dict[str, Any]:
        if not record.proposal:
            return {"valid": False, "reasons": ["missing_proposal"]}
        return {"valid": True, "reasons": []}

    def _prereq_peer_review(self, record: ProposalRecord) -> Dict[str, Any]:
        proposal = record.proposal or {}
        if proposal.get("changes", {}).get("code"):
            metadata = record.phase_metadata.get(ProposalPhase.AGENT_TESTING, {})
            if not metadata.get("test_results"):
                return {"valid": False, "reasons": ["agent_testing_missing"]}
            if not metadata["test_results"].get("passed", False):
                return {"valid": False, "reasons": ["agent_testing_failed"]}
        return {"valid": True, "reasons": []}

    def _prereq_counterpoint(self, record: ProposalRecord) -> Dict[str, Any]:
        if not record.consensus_reached:
            return {"valid": False, "reasons": ["consensus_not_reached"]}
        if not record.review_rounds:
            return {"valid": False, "reasons": ["no_review_rounds"]}
        return {"valid": True, "reasons": []}

    def _prereq_defense(self, record: ProposalRecord) -> Dict[str, Any]:
        if record.orka_challenges is None:
            return {"valid": False, "reasons": ["no_orka_challenges"]}
        return {"valid": True, "reasons": []}

    def _prereq_final_testing(self, record: ProposalRecord) -> Dict[str, Any]:
        if record.phase_metadata.get(ProposalPhase.AGENT_DEFENSE) and not record.defense_accepted:
            return {"valid": False, "reasons": ["defense_not_accepted"]}
        return {"valid": True, "reasons": []}

    def _prereq_human_notification(self, record: ProposalRecord) -> Dict[str, Any]:
        metadata = record.phase_metadata.get(ProposalPhase.FINAL_TESTING, {})
        results = metadata.get("test_results")
        if results is None:
            return {"valid": False, "reasons": ["final_testing_missing"]}
        if not results.get("overall_pass") and not results.get("all_passed"):
            return {"valid": False, "reasons": ["final_testing_failed"]}
        if metadata.get("deferred"):
            return {"valid": False, "reasons": ["final_testing_deferred"]}
        return {"valid": True, "reasons": []}

    def _prereq_val_validation(self, record: ProposalRecord) -> Dict[str, Any]:
        if record.human_decision != "approved":
            return {"valid": False, "reasons": ["human_approval_required"]}
        return {"valid": True, "reasons": []}

    def _prereq_deployment(self, record: ProposalRecord) -> Dict[str, Any]:
        if record.val_result is None:
            return {"valid": False, "reasons": ["val_result_missing"]}
        if not record.val_result.approved:
            return {"valid": False, "reasons": ["val_not_approved"]}
        if not record.val_result.signature_valid:
            return {"valid": False, "reasons": ["val_signature_invalid"]}
        return {"valid": True, "reasons": []}

    def get_phase_history(self, record: ProposalRecord) -> List[PhaseTransition]:
        return record.phase_history

    def get_current_phase(self, record: ProposalRecord) -> ProposalPhase:
        return record.current_phase

    def is_terminal_phase(self, phase: ProposalPhase) -> bool:
        return phase in {
            ProposalPhase.DEPLOYMENT,
            ProposalPhase.REJECTED,
            ProposalPhase.WITHDRAWN,
            ProposalPhase.FAILED,
        }

    def _log_invalid(
        self,
        proposal_id: str,
        current: ProposalPhase,
        target: ProposalPhase,
        reason: str,
        details: Optional[List[str]] = None,
    ) -> None:
        # Placeholder for structured logging; intentionally minimal to avoid import cycles.
        message = (
            f"workflow_transition_blocked proposal={proposal_id} "
            f"{current.name}->{target.name} reason={reason}"
        )
        if details:
            message += f" details={details}"
        print(message)
