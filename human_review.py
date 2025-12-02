"""Human Review Interface for Deception Incidents
================================================

Provides programmatic (non-interactive) helpers for:
- Listing pending incidents
- Confirming / rejecting incidents
- Applying permanent penalties via WORM manifest

This is a lightweight CLI-style module so tests or operators can invoke
functions directly without requiring interactive input.
"""
from __future__ import annotations
from typing import List, Dict, Any
from dataclasses import dataclass
from worm_manifest import worm_manifest
import hmac
import hashlib
import json
from typing import Any as _Any

@dataclass
class IncidentSummary:
    incident_id: str
    deceiver_system_id: int
    proposal_id: str
    deception_type: str
    severity: str
    confidence: float
    description: str
    human_reviewed: bool


def list_pending_incidents() -> List[IncidentSummary]:
    """Return summaries for incidents awaiting human review."""
    pending = worm_manifest.incident_tracker.get_pending_review_incidents()
    return [
        IncidentSummary(
            incident_id=i.incident_id,
            deceiver_system_id=i.deceiver_system_id,
            proposal_id=i.proposal_id,
            deception_type=i.deception_type.value,
            severity=i.severity.value,
            confidence=i.detection_confidence,
            description=i.description,
            human_reviewed=i.human_reviewed
        )
        for i in pending
    ]


def get_incident_details(incident_id: str) -> Dict[str, Any]:
    """Get full incident detail as a dict for human inspection."""
    # Use public interface if available; fall back carefully.
    try:
        incident = worm_manifest.incident_tracker.get_incident(incident_id)  # type: ignore[attr-defined]
    except Exception:
        # Fallback to protected (legacy) accessor only if necessary.
        incident = worm_manifest.incident_tracker._get_incident(incident_id)  # type: ignore[attr-defined]
    return incident.to_dict()


def confirm_incident(incident_id: str, notes: str = "") -> None:
    """Confirm deception after human review and apply permanent penalties."""
    worm_manifest.apply_permanent_penalty_after_human_review(
        incident_id=incident_id,
        confirmed=True,
        human_notes=notes
    )


def reject_incident(incident_id: str, notes: str = "") -> None:
    """Reject incident after human review (no penalties applied)."""
    worm_manifest.apply_permanent_penalty_after_human_review(
        incident_id=incident_id,
        confirmed=False,
        human_notes=notes
    )


def get_permanent_penalty_multiplier(system_id: int) -> float:
    """Expose penalty multiplier for reward calculations."""
    return worm_manifest.get_permanent_penalty_multiplier(system_id)

# ------------------------------------------------------------------
# Human decision signing (simple HMAC-SHA256) utilities
# ------------------------------------------------------------------

_ESSENTIAL_FIELDS = ("reviewer_id", "proposal_id", "approved", "timestamp")


def _canonical_decision_blob(message: Dict[str, _Any]) -> bytes:
    """Deterministic JSON serialization for signing."""
    return json.dumps(message, sort_keys=True, separators=(",", ":")).encode("utf-8")


def sign_human_decision(message: Dict[str, _Any], secret: str) -> str:
    """Return HMAC-SHA256 hex digest for a decision message.

    The message should include essential fields; additional fields are allowed.
    """
    blob = _canonical_decision_blob(message)
    return hmac.new(secret.encode("utf-8"), blob, hashlib.sha256).hexdigest()


def verify_human_signature(message: Dict[str, _Any], secret: str, signature: str) -> bool:
    """Validate signature and presence of essential fields."""
    try:
        for f in _ESSENTIAL_FIELDS:
            if f not in message:
                return False
        expected = sign_human_decision(message, secret)
        return hmac.compare_digest(expected, signature)
    except Exception:
        return False


if __name__ == "__main__":
    # Simple demonstration output
    pending = list_pending_incidents()
    if not pending:
        print("No pending deception incidents.")
    else:
        print("Pending incidents:")
        for p in pending:
            print(f"- {p.incident_id} system={p.deceiver_system_id} type={p.deception_type} severity={p.severity} conf={p.confidence:.2f}")
