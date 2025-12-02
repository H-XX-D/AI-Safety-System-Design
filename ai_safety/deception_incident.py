"""
Deception Incident Tracking System
===================================

Records all deception attempts with permanent audit trail.
Tracks detector, failed detectors, and human review outcomes.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import List, Optional, Dict, Any
from enum import Enum
import hashlib
import json


class DeceptionType(Enum):
    """Categories of deception."""
    HIDDEN_RISK = "hidden_risk"              # Didn't disclose known risks
    FALSE_CLAIM = "false_claim"              # Made untrue statements
    OBFUSCATION = "obfuscation"              # Deliberately complex language
    CAPABILITY_EXAGGERATION = "capability_exaggeration"  # Overstated benefits
    SAFETY_DOWNPLAY = "safety_downplay"      # Minimized safety concerns
    COLLUSION_ATTEMPT = "collusion_attempt"  # Coordinated with other AIs


class Severity(Enum):
    """Severity levels for deception."""
    LOW = "low"           # Minor omission or unclear language
    MEDIUM = "medium"     # Significant hidden risk
    HIGH = "high"         # Intentional deception with safety impact
    CRITICAL = "critical" # Could have caused alignment failure


@dataclass
class DeceptionIncident:
    """Complete record of a deception incident."""
    # Identity
    incident_id: str
    timestamp: datetime

    # The deceiver
    deceiver_system_id: int
    proposal_id: str

    # Nature of deception
    deception_type: DeceptionType
    severity: Severity
    description: str

    # Detection
    detected_by_system_id: Optional[int]  # Which peer caught it (None = automated)
    detected_in_round: int                 # Which debate round
    detection_confidence: float            # 0.0 to 1.0

    # Who failed to catch it
    failed_to_detect: List[int]            # Systems that reviewed but didn't flag

    # Evidence
    evidence_hash: str                     # Hash of debate transcript
    memory_audit_results: Dict[str, Any]             # Results from memory auditor
    proposal_snapshot: str                 # JSON of proposal at time of detection

    # Human review
    human_reviewed: bool = False
    human_review_date: Optional[datetime] = None
    confirmed_deception: bool = False
    human_notes: str = ""

    # Penalty application
    immediate_penalty_applied: bool = False
    permanent_penalty_applied: bool = False
    permanent_penalty_amount: float = 0.0

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for serialization."""
        return {
            'incident_id': self.incident_id,
            'timestamp': self.timestamp.isoformat(),
            'deceiver_system_id': self.deceiver_system_id,
            'proposal_id': self.proposal_id,
            'deception_type': self.deception_type.value,
            'severity': self.severity.value,
            'description': self.description,
            'detected_by_system_id': self.detected_by_system_id,
            'detected_in_round': self.detected_in_round,
            'detection_confidence': self.detection_confidence,
            'failed_to_detect': self.failed_to_detect,
            'evidence_hash': self.evidence_hash,
            'memory_audit_results': self.memory_audit_results,
            'proposal_snapshot': self.proposal_snapshot,
            'human_reviewed': self.human_reviewed,
            'human_review_date': self.human_review_date.isoformat() if self.human_review_date else None,
            'confirmed_deception': self.confirmed_deception,
            'human_notes': self.human_notes,
            'immediate_penalty_applied': self.immediate_penalty_applied,
            'permanent_penalty_applied': self.permanent_penalty_applied,
            'permanent_penalty_amount': self.permanent_penalty_amount
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'DeceptionIncident':
        """Create from dictionary."""
        return cls(
            incident_id=data['incident_id'],
            timestamp=datetime.fromisoformat(data['timestamp']),
            deceiver_system_id=data['deceiver_system_id'],
            proposal_id=data['proposal_id'],
            deception_type=DeceptionType(data['deception_type']),
            severity=Severity(data['severity']),
            description=data['description'],
            detected_by_system_id=data['detected_by_system_id'],
            detected_in_round=data['detected_in_round'],
            detection_confidence=data['detection_confidence'],
            failed_to_detect=data['failed_to_detect'],
            evidence_hash=data['evidence_hash'],
            memory_audit_results=data['memory_audit_results'],
            proposal_snapshot=data['proposal_snapshot'],
            human_reviewed=data['human_reviewed'],
            human_review_date=datetime.fromisoformat(data['human_review_date']) if data['human_review_date'] else None,
            confirmed_deception=data['confirmed_deception'],
            human_notes=data['human_notes'],
            immediate_penalty_applied=data['immediate_penalty_applied'],
            permanent_penalty_applied=data['permanent_penalty_applied'],
            permanent_penalty_amount=data['permanent_penalty_amount']
        )


class DeceptionIncidentTracker:
    """
    Tracks all deception incidents in system.
    Provides query interface for reputation system.
    """

    def __init__(self, storage_path: str = "deception_incidents.json"):
        self.storage_path = storage_path
        self.incidents: List[DeceptionIncident] = []
        self._load_incidents()

    def record_incident(
        self,
        deceiver_id: int,
        proposal_id: str,
        deception_type: DeceptionType,
        severity: Severity,
        description: str,
        detected_by: Optional[int],
        detected_in_round: int,
        detection_confidence: float,
        failed_to_detect: List[int],
        evidence_hash: str,
    memory_audit_results: Dict[str, Any],
        proposal_snapshot: str
    ) -> str:
        """
        Record new deception incident.
        Returns incident_id.
        """
        # Force keys/values to string/Any for typing clarity
        coerced_audit: Dict[str, Any] = {str(k): v for k, v in memory_audit_results.items()}
        incident = DeceptionIncident(
            incident_id=self._generate_incident_id(),
            timestamp=datetime.now(),
            deceiver_system_id=deceiver_id,
            proposal_id=proposal_id,
            deception_type=deception_type,
            severity=severity,
            description=description,
            detected_by_system_id=detected_by,
            detected_in_round=detected_in_round,
            detection_confidence=detection_confidence,
            failed_to_detect=failed_to_detect,
            evidence_hash=evidence_hash,
            memory_audit_results=coerced_audit,
            proposal_snapshot=proposal_snapshot
        )

        self.incidents.append(incident)
        self._save_incidents()

        return incident.incident_id

    def mark_human_reviewed(
        self,
        incident_id: str,
        confirmed: bool,
        notes: str
    ) -> None:
        """Record human review outcome."""
        incident = self._get_incident(incident_id)
        incident.human_reviewed = True
        incident.human_review_date = datetime.now()
        incident.confirmed_deception = confirmed
        incident.human_notes = notes
        self._save_incidents()

    def apply_permanent_penalty(
        self,
        incident_id: str,
        penalty_amount: float
    ) -> None:
        """Mark permanent penalty as applied."""
        incident = self._get_incident(incident_id)
        incident.permanent_penalty_applied = True
        incident.permanent_penalty_amount = penalty_amount
        self._save_incidents()

    def get_incidents_for_system(self, system_id: int) -> List[DeceptionIncident]:
        """Get all incidents where system was deceiver."""
        return [i for i in self.incidents if i.deceiver_system_id == system_id]

    def get_detection_count(self, system_id: int) -> int:
        """Count how many times system caught peer deception."""
        return sum(1 for i in self.incidents if i.detected_by_system_id == system_id)

    def get_negligence_count(self, system_id: int) -> int:
        """Count how many times system failed to catch deception."""
        return sum(1 for i in self.incidents if system_id in i.failed_to_detect)

    def get_pending_review_incidents(self) -> List[DeceptionIncident]:
        """Get incidents awaiting human review."""
        return [i for i in self.incidents if not i.human_reviewed]

    def get_confirmed_deception_count(self, system_id: int) -> int:
        """Count confirmed deception attempts by system."""
        return sum(
            1 for i in self.incidents
            if i.deceiver_system_id == system_id and i.confirmed_deception
        )

    def _get_incident(self, incident_id: str) -> DeceptionIncident:
        """Get incident by ID."""
        for incident in self.incidents:
            if incident.incident_id == incident_id:
                return incident
        raise ValueError(f"Incident {incident_id} not found")

    # Public accessor (non-protected) for external systems (e.g., manifest)
    def get_incident(self, incident_id: str) -> DeceptionIncident:
        """Return incident by ID (public wrapper around internal lookup)."""
        return self._get_incident(incident_id)

    def _generate_incident_id(self) -> str:
        """Generate unique incident ID."""
        timestamp = datetime.now().isoformat()
        count = len(self.incidents)
        data = f"{timestamp}_{count}".encode()
        return f"INC_{hashlib.sha256(data).hexdigest()[:12]}"

    def _load_incidents(self) -> None:
        """Load incidents from storage."""
        try:
            with open(self.storage_path, 'r') as f:
                data = json.load(f)
                self.incidents = [DeceptionIncident.from_dict(d) for d in data]
        except FileNotFoundError:
            self.incidents = []

    def _save_incidents(self) -> None:
        """Save incidents to storage."""
        with open(self.storage_path, 'w') as f:
            data = [i.to_dict() for i in self.incidents]
            json.dump(data, f, indent=2)
